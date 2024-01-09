"""Code for filtering the ICSD for unique reference structures.
Some of this code is borrowed from AutoXRD package, courtesy Nathan Szymanski.
"""
import math
import os
from functools import reduce

import numpy as np
from pymatgen.analysis import structure_matcher
from pymatgen.analysis.diffraction.xrd import XRDCalculator
from pymatgen.core import PeriodicSite, Structure
from pyts import metrics
from scipy.ndimage import gaussian_filter1d
from scipy.signal import filtfilt
from tqdm import tqdm

PATH_TO_ICSD = "/Users/mcdermott/Documents/ICSD"


def calc_std_dev(two_theta, tau):
    """Calculate standard deviation based on angle (two theta) and domain size (tau).

    Args:
        two_theta: angle in two theta space
        tau: domain size in nm
    Returns:
        standard deviation for gaussian kernel
    """
    ## Calculate FWHM based on the Scherrer equation
    K = 0.9  ## shape factor
    wavelength = XRDCalculator().wavelength * 0.1  ## angstrom to nm
    theta = np.radians(two_theta / 2.0)  ## Bragg angle in radians
    beta = (K * wavelength) / (np.cos(theta) * tau)  # in radians

    ## Convert FWHM to std deviation of gaussian
    sigma = np.sqrt(1 / (2 * np.log(2))) * 0.5 * np.degrees(beta)
    return sigma**2


def remap_pattern(angles, intensities):
    steps = np.linspace(10, 100, 4501)
    signals = np.zeros([len(angles), steps.shape[0]])

    for i, ang in enumerate(angles):
        # Map angle to closest datapoint step
        idx = np.argmin(np.abs(ang - steps))
        signals[i, idx] = intensities[i]
    domain_size = 25.0
    step_size = (100 - 10) / 4501

    for i in range(signals.shape[0]):
        row = signals[i, :]
        ang = steps[np.argmax(row)]
        std_dev = calc_std_dev(ang, domain_size)
        # Gaussian kernel expects step size 1 -> adapt std_dev
        signals[i, :] = gaussian_filter1d(row, np.sqrt(std_dev) * 1 / step_size, mode="constant")

    # Combine signals
    signal = np.sum(signals, axis=0)
    # Normalize signal
    norm_signal = 100 * signal / max(signal)
    # Combine signals
    signal = np.sum(signals, axis=0)
    # Normalize signal
    norm_signal = 100 * signal / max(signal)

    return norm_signal


def smooth_spectrum(spectrum, n=20):
    """
    Process and remove noise from the spectrum.

    Args:
        spectrum: list of intensities as a function of 2-theta
        n: parameters used to control smooth. Larger n means greater smoothing.
            20 is typically a good number such that noise is reduced while
            still retaining minor diffraction peaks.

    Returns
    -------
        smoothed_ys: processed spectrum after noise removal
    """
    # Smoothing parameters defined by n
    b = [1.0 / n] * n
    a = 1

    # Filter noise
    smoothed_ys = filtfilt(b, a, spectrum)

    return smoothed_ys


def strip_spectrum(warped_spectrum, orig_y):
    """
    Subtract one spectrum from another. Note that when subtraction produces
    negative intensities, those values are re-normalized to zero. This way,
    the CNN can handle the spectrum reliably.

    Args:
        warped_spectrum: spectrum associated with the identified phase
        orig_y: original (measured) spectrum
    Returns:
        fixed_y: resulting spectrum from the subtraction of warped_spectrum
            from orig_y
    """
    # Subtract predicted spectrum from measured spectrum
    stripped_y = orig_y - warped_spectrum

    # Normalize all negative values to 0.0
    fixed_y = []
    for val in stripped_y:
        if val < 0:
            fixed_y.append(0.0)
        else:
            fixed_y.append(val)

    return fixed_y


def get_reduced_pattern(y1, y2, last_normalization=1.0):
    """
    Subtract y1 from y2 using dynamic time warping (DTW) and return the new spectrum.

    Returns
    -------
        stripped_y: new spectrum obtained by subtrating the peaks of the identified phase
    """
    # Convert to numpy arrays
    pred_y = np.array(y1)
    orig_y = np.array(y2)

    # # Downsample spectra (helps reduce time for DTW)
    # downsampled_res = 0.1  # new resolution: 0.1 degrees
    # num_pts = int((100 - 10) / downsampled_res)
    # orig_y = resample(orig_y, num_pts)
    # pred_y = resample(pred_y, num_pts)
    num_pts = len(orig_y)

    # Calculate window size for DTW
    allow_shifts = 0.75  # Allow shifts up to 0.75 degrees
    window_size = int(allow_shifts * num_pts / (100 - 10))

    # Get warped spectrum (DTW)
    distance, path = metrics.dtw(
        pred_y,
        orig_y,
        method="sakoechiba",
        options={"window_size": window_size},
        return_path=True,
    )
    index_pairs = path.transpose()
    warped_spectrum = orig_y.copy()
    for ind1, ind2 in index_pairs:
        distance = abs(ind1 - ind2)
        # if distance <= window_size:
        warped_spectrum[ind2] = pred_y[ind1]
        # else:
        #     warped_spectrum[ind2] = 0.0

    # Now, upsample spectra back to their original size (4501)
    # warped_spectrum = resample(warped_spectrum, 4501)
    # orig_y = resample(orig_y, 4501)

    # Scale warped spectrum so y-values match measured spectrum
    # scaled_spectrum, scaling_constant = scale_spectrum(warped_spectrum, orig_y)

    # Subtract scaled spectrum from measured spectrum
    stripped_y = strip_spectrum(warped_spectrum, orig_y)
    # stripped_y = smooth_spectrum(stripped_y)
    # stripped_y = np.array(stripped_y) - min(stripped_y)

    return stripped_y


def round_dict_values(data):
    """Round coefficients of highly complex formulae."""
    for key, value in data.items():
        if value > 1e5:
            data[key] = round(value, -3)
        elif value > 1e4:
            data[key] = round(value, -2)
        elif value > 1e3:
            data[key] = round(value, -1)

    # Reduce coefficients by gcd
    gcd = reduce(math.gcd, list(data.values()))
    for key in data:
        data[key] = int(data[key] / gcd)

    return data


class StructureFilter:
    """
    Class used to parse a list of CIFs and choose unique,
    stoichiometric reference phases that were measured
    under (or nearest to) ambient conditions.
    """

    def __init__(self, cif_directory, enforce_order):
        """
        Args:
            cif_directory: path to directory containing the CIF files to be considered
            as possible reference phases.
        """
        self.cif_dir = cif_directory
        self.enforce_order = enforce_order

    @property
    def stoichiometric_info(self):
        """
        Filter strucures to include only those which do not have
        fraction occupancies and are ordered. For those phases, tabulate
        the measurement conditions of the associated CIFs.

        Returns
        -------
            stoich_strucs: a list of ordered pymatgen Structure objects
            temps: temperatures that each were measured at
            dates: dates the measurements were reported
        """
        strucs, temps, dates = [], [], []
        for cmpd in os.listdir(self.cif_dir):
            struc = Structure.from_file("%s/%s" % (self.cif_dir, cmpd))
            if self.enforce_order:
                if struc.is_ordered:
                    strucs.append(struc)
                    t, d = self.parse_measurement_conditions(cmpd)
                    temps.append(t)
                    dates.append(d)
            else:
                strucs.append(struc)
                t, d = self.parse_measurement_conditions(cmpd)
                temps.append(t)
                dates.append(d)

        return strucs, temps, dates

    def parse_measurement_conditions(self, filename):
        """
        Parse the temperature and date from a CIF file.

        Args:
            filename: filename of CIF to be parsed
        Returns:
            temp: temperature at which measurement was conducted
            date: date which measurement was reported
        """
        temp, date = 0.0, None
        with open("%s/%s" % (self.cif_dir, filename)) as entry:
            for line in entry.readlines():
                if "_audit_creation_date" in line:
                    date = line.split()[-1]
                if "_cell_measurement_temperature" in line:
                    temp = float(line.split()[-1])
        return temp, date

    @property
    def unique_struc_info(self):
        """
        Create distinct lists of Structure objects where each
        list is associated with a unique strucural prototype.

        Returns
        -------
            grouped_strucs: a list of sub-lists containing pymatgen
                Structure objects organize by the strucural prototype
            grouped_temps and grouped_dates: similarly grouped temperatures and dates
                associated with the corresponding measurements
        """
        stoich_strucs, temps, dates = self.stoichiometric_info

        matcher = structure_matcher.StructureMatcher(scale=True, attempt_supercell=True, primitive_cell=False)

        XRD_calculator = XRDCalculator(wavelength="CuKa", symprec=0.0)

        unique_frameworks = []
        for struc_1 in stoich_strucs:
            unique = True
            for struc_2 in unique_frameworks:
                # Check if structures are identical. If so, exclude.
                if matcher.fit(struc_1, struc_2):
                    unique = False

                # Check if compositions are similar If so, check structural framework.
                temp_struc_1 = struc_1.copy()
                reduced_comp_1_dict = temp_struc_1.composition.remove_charges().reduced_composition.to_reduced_dict
                divider_1 = 1

                for key in reduced_comp_1_dict:
                    divider_1 = max(divider_1, reduced_comp_1_dict[key])

                reduced_comp_1 = temp_struc_1.composition.remove_charges().reduced_composition / divider_1
                temp_struc_2 = struc_2.copy()
                reduced_comp_2_dict = temp_struc_2.composition.remove_charges().reduced_composition.to_reduced_dict
                divider_2 = 1

                for key in reduced_comp_2_dict:
                    divider_2 = max(divider_2, reduced_comp_2_dict[key])
                reduced_comp_2 = temp_struc_2.composition.remove_charges().reduced_composition / divider_2

                if reduced_comp_1.almost_equals(reduced_comp_2, atol=0.5):
                    # Replace with dummy species (H) for structural framework check.
                    temp_struc_1 = struc_1.copy()
                    for index, site in enumerate(temp_struc_1.sites):
                        site_dict = site.as_dict()
                        site_dict["species"] = []
                        site_dict["species"].append(
                            {"element": "H", "oxidation_state": 0.0, "occu": 1.0}
                        )  # dummy species
                        temp_struc_1[index] = PeriodicSite.from_dict(site_dict)
                    temp_struc_2 = struc_2.copy()
                    for index, site in enumerate(temp_struc_2.sites):
                        site_dict = site.as_dict()
                        site_dict["species"] = []
                        site_dict["species"].append(
                            {"element": "H", "oxidation_state": 0.0, "occu": 1.0}
                        )  # dummy species
                        temp_struc_2[index] = PeriodicSite.from_dict(site_dict)

                    # Checking structural framework.
                    if matcher.fit(temp_struc_1, temp_struc_2):
                        # Before excluding, check if their XRD patterns differ.
                        """
                        This check is necessary as sometimes materials with identical compositions can adopt the
                        same structural framework but still differ in their XRD, e.g., when individual site
                        occupancies differ between them. For example, site inversion in spinels.

                        Accordingly, we still include identical structures/compositions in the cases
                        where their XRD patterns differ by some predefined amount.
                        """
                        y_1 = remap_pattern(
                            XRD_calculator.get_pattern(struc_1, scaled=True, two_theta_range=(10, 100)).x,
                            XRD_calculator.get_pattern(struc_1, scaled=True, two_theta_range=(10, 100)).y,
                        )
                        y_2 = remap_pattern(
                            XRD_calculator.get_pattern(struc_2, scaled=True, two_theta_range=(10, 100)).x,
                            XRD_calculator.get_pattern(struc_2, scaled=True, two_theta_range=(10, 100)).y,
                        )
                        reduced_pattern = np.array(get_reduced_pattern(y_1, y_2))

                        # If 20% peak intensity remains after subtracting one pattern from the other.
                        diff_threshold = 20.0
                        if (reduced_pattern < diff_threshold).all():
                            unique = False

            if unique:
                unique_frameworks.append(struc_1)

        grouped_strucs, grouped_temps, grouped_dates = [], [], []
        for framework in unique_frameworks:
            struc_class, temp_class, date_class = [], [], []
            for struc, t, d in zip(stoich_strucs, temps, dates):
                if matcher.fit(framework, struc):
                    struc_class.append(struc)
                    temp_class.append(t)
                    date_class.append(d)

            grouped_strucs.append(struc_class)
            grouped_temps.append(temp_class)
            grouped_dates.append(date_class)

        return grouped_strucs, grouped_temps, grouped_dates

    @property
    def filtered_refs(self):
        """
        For each list of strucures associated with a strucural prototype,
        choose that which was measured under (or nearest to) ambient conditions
        and which was reported most recently. Priority is given to the former.

        Returns
        -------
            filtered_cmpds: a list of unique pymatgen Structure objects
        """
        grouped_strucs, grouped_temps, grouped_dates = self.unique_struc_info

        filtered_cmpds = []
        for struc_class, temp_class, date_class in zip(grouped_strucs, grouped_temps, grouped_dates):
            normalized_temps = abs(np.array(temp_class) - 293.0)  # Difference from RT
            zipped_info = list(zip(struc_class, normalized_temps, date_class))
            sorted_info = sorted(zipped_info, key=lambda x: x[1])  # Sort by temperature
            best_entry = sorted_info[0]  # Take the entry measured at the temperature closest to RT
            candidate_strucs, candidate_dates = [], []
            for entry in sorted_info:
                if entry[1] == best_entry[1]:  # If temperature matches best entry
                    candidate_strucs.append(entry[0])
                    candidate_dates.append(entry[2])
            zipped_info = list(zip(candidate_strucs, candidate_dates))
            try:
                sorted_info = sorted(zipped_info, key=lambda x: x[1])  ## Sort by date
                final_struc = sorted_info[-1][0]  # Take the entry that was measured most recently
            # If no dates available
            except TypeError:
                final_struc = zipped_info[-1][0]
            filtered_cmpds.append(final_struc)

        return filtered_cmpds


def write_cifs(unique_strucs, dir, include_elems):
    """
    Write structures to CIF files.

    Args:
        strucs: list of pymatgen Structure objects
        dir: path to directory where CIF files will be written
    """
    if not os.path.isdir(dir):
        os.mkdir(dir)

    for struc in unique_strucs:
        num_elems = struc.composition.elements
        if num_elems == 1 and not include_elems:
            continue
        f = struc.composition.reduced_formula
        try:
            sg = struc.get_space_group_info()[1]
            filepath = "%s/%s_%s.cif" % (dir, f, sg)
            struc.to(filename=filepath, fmt="cif")
        except:
            try:
                print("%s Space group cannot be determined, lowering tolerance" % str(f))
                sg = struc.get_space_group_info(symprec=0.1, angle_tolerance=5.0)[1]
                filepath = "%s/%s_%s.cif" % (dir, f, sg)
                struc.to(filename=filepath, fmt="cif")
            except:
                print("%s Space group cannot be determined even after lowering tolerance, Setting to None" % str(f))

    assert len(os.listdir(dir)) > 0, "Something went wrong. No reference phases were found."


def clean_cifs(
    cif_directory,
    ref_directory,
    include_elems=True,
    enforce_order=False,
):
    """Clean CIFs and write to reference directory."""
    # Get unique structures
    struc_filter = StructureFilter(cif_directory, enforce_order)
    final_refs = struc_filter.filtered_refs

    # Write unique structures (as CIFs) to reference directory
    write_cifs(final_refs, ref_directory, include_elems)


if __name__ == "main":
    struct_dict = {}
    for filename in tqdm(sorted(os.listdir(PATH_TO_ICSD))):
        file_path = os.path.join(PATH_TO_ICSD, filename)

        try:
            struct = Structure.from_file(file_path, merge_tol=0.01, occupancy_tolerance=100)
        except Exception as e:
            print("Error:", filename, e)
            continue

        entry = int(filename.strip(".cif"))

        chemsys = struct.composition.chemical_system
        formula = struct.composition.reduced_formula

        if chemsys in struct_dict:
            if formula in struct_dict[chemsys]:
                struct_dict[chemsys][formula].append(entry)
            else:
                struct_dict[chemsys][formula] = [entry]
        else:
            struct_dict[chemsys] = {formula: [entry]}
