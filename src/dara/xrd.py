"""Load and process XRD data files (.xrdml, .xy)."""

from __future__ import annotations

import struct
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xmltodict
from dict2xml import dict2xml
from monty.json import MSONable


class XRDData(MSONable):
    """General XRD data class; this is the base class for XRDMLFile, XYFile and other
    XRD data formats. This class ensures that all XRD data can be serialized.
    """

    def __init__(
        self,
        angles: list | np.ndarray,
        intensities: list | np.ndarray,
        errors: list | np.ndarray | None = None,
    ):
        """Initialize XRD data from angles (2-theta values) and intensities/counts."""
        self._angles = np.array(angles)
        self._intensities = np.array(intensities)
        self._errors = np.array(errors) if errors is not None else None

    @property
    def angles(self) -> np.ndarray:
        """2-theta values."""
        return self._angles

    @property
    def intensities(self) -> np.ndarray:
        """Intensity values (counts)."""
        return self._intensities

    @property
    def errors(self) -> np.ndarray | None:
        """Errors in intensity values."""
        return self._errors

    def plot(self, style="line", ax=None, **kwargs):
        """Plot XRD data.

        Args:
            ax: existing matplotlib axis to plot on
            style: either "points" or "line"
            kwargs: keyword arguments to pass to matplotlib.pyplot.plot

        Returns
        -------
            matplotlib axis
        """
        if ax is None:
            _, ax = plt.subplots(figsize=(8, 5))

        if style == "points":
            ax.plot(self.angles, self.intensities, "+", ls="", ms=2, **kwargs)
        elif style == "line":
            ax.plot(self.angles, self.intensities, lw=1, **kwargs)
        else:
            raise ValueError(f"Invalid style {style}")

        ax.set_xlabel(r"$2\theta$ (deg)")
        ax.set_ylabel("Intensity (counts)")
        return ax

    @classmethod
    def from_file(cls, path: str | Path):
        """Load data from file. To be implemented in subclasses."""
        raise NotImplementedError

    def to_xy_file(self, fn: str | Path = "xrd_data.xy") -> None:
        """Save as a .xy file.

        Args:
            fn: filename to save to. Defaults to "xrd_data.xy".

        Returns
        -------
            filename of saved file
        """
        if self.errors is not None:
            np.savetxt(
                Path(fn).as_posix(),
                np.column_stack((self.angles, self.intensities, self.errors)),
                fmt="%f",
            )
        else:
            np.savetxt(
                Path(fn).as_posix(),
                np.column_stack((self.angles, self.intensities)),
                fmt="%f",
            )


class RawFile(XRDData):
    """Load Rigaku RAW file data format."""

    def __init__(self, angles, intensities, binary_data: bytes | None = None):
        super().__init__(angles, intensities)
        self._binary_data = binary_data

    @classmethod
    def from_file(cls, path: str | Path) -> RawFile:
        """Load data from a raw file."""
        path = Path(path)
        (angles, intensities), binary_data = load_raw(path)
        return cls(angles, intensities, binary_data)

    @property
    def binary_data(self) -> bytes | None:
        """Binary data."""
        return self._binary_data

    def to_raw_file(self, fn: str | Path = "xrd_data.raw") -> None:
        """Save as a raw file.

        Args:
            fn: filename to save to. Defaults to "xrd_data.raw".
        """
        with open(Path(fn), "wb") as f:
            f.write(self.binary_data)


class XRDMLFile(XRDData):
    """XRDML file class, useful for loading .xrdml data. This is the file type used by
    the Aeris instrument.
    """

    def __init__(self, angles, intensities, xrdml_dict: dict | None = None):
        """Initialize an XRDMLFile object; providing dictionary allows one to serialize
        and deserialize the XRDML file.
        """
        super().__init__(angles, intensities)
        self._xrdml_dict = xrdml_dict

    @property
    def xrdml_dict(self) -> dict | None:
        """Dictionary representation of the XRDML file."""
        return self._xrdml_dict

    @classmethod
    def from_file(cls, path: str | Path) -> XRDMLFile:
        """Load data from an XRDML file."""
        xrdml_dict = load_xrdml(Path(path))
        angles, intensities = get_xrdml_data(xrdml_dict)
        return cls(angles=angles, intensities=intensities, xrdml_dict=xrdml_dict)

    def to_xrdml_file(self, fn: str | Path = "xrd_data.xrdml") -> None:
        """Save as an XRDML file.

        Args:
            fn: filename to save to. Defaults to "xrd_data.xrdml".
        """
        with open(Path(fn), "w") as f:
            f.write(dict2xml(self.xrdml_dict))


class XYFile(XRDData):
    """XY file class, useful for loading .xy data."""

    def __init__(self, angles, intensities, errors: list | np.ndarray | None = None):
        super().__init__(angles, intensities, errors)

    @classmethod
    def from_file(cls, path: str | Path) -> XYFile:
        """Load data from a .xy file."""
        path = Path(path)
        try:
            data = np.loadtxt(path, unpack=True)
        except ValueError:
            # Try to load the file with a comma delimiter
            data = np.loadtxt(path, unpack=True, delimiter=",")
        if len(data) == 2:
            angles, intensities = data
            errors = None
        else:
            angles, intensities, errors = data  # if it is xye data
        return cls(angles, intensities, errors)


def load_xrdml(file: Path) -> dict:
    """Load an XRDML file and returns a dictionary using xmltodict."""
    with file.open("r", encoding="utf-8") as f:
        return xmltodict.parse(f.read())


def get_xrdml_data(xrd_dict: dict) -> tuple[np.ndarray, np.ndarray]:
    """Get angles and intensities from an XRDML dictionary."""
    min_angle = float(
        xrd_dict["xrdMeasurements"]["xrdMeasurement"]["scan"]["dataPoints"][
            "positions"
        ][0]["startPosition"]
    )
    max_angle = float(
        xrd_dict["xrdMeasurements"]["xrdMeasurement"]["scan"]["dataPoints"][
            "positions"
        ][0]["endPosition"]
    )

    intensities = xrd_dict["xrdMeasurements"]["xrdMeasurement"]["scan"]["dataPoints"][
        "counts"
    ]["#text"]
    intensities = np.array([float(val) for val in intensities.split()])
    angles = np.linspace(min_angle, max_angle, len(intensities))
    return angles, intensities


def xrdml2xy(fn: str | Path, target_folder: Path = None) -> Path:
    """Convert .xrdml file to .xy file (and save)."""
    fn = Path(fn)
    if target_folder is None:
        target_folder = fn.parent
    target_path = target_folder / fn.with_suffix(".xy").name

    XRDMLFile.from_file(fn).to_xy_file(target_path)
    return target_path


def hex2float(hex_string: bytes) -> float:
    # Assuming hex_string is a bytes object representing a float in hex
    return struct.unpack("f", hex_string)[0]


def hex2int(hex_string: bytes) -> int:
    # Assuming hex_string is a bytes object representing an int in hex
    return struct.unpack("i", hex_string)[0]


def load_raw(file: Path | str) -> tuple[tuple[np.ndarray, np.ndarray], bytes]:
    """Convert raw file to xy data."""
    with open(file, "rb") as f:
        content = f.read()
    size_float = 4  # Assuming 4 bytes for a float
    size_int = 4  # Assuming 4 bytes for an int

    # Extracting start angle, end angle, and step size from binary content
    start_ang = hex2float(content[2962 : 2962 + size_float])
    end_ang = hex2float(content[2966 : 2966 + size_float])
    count = hex2int(content[3154 : 3154 + size_int])
    start_idx = 3158
    angles = np.zeros(count)
    intensities = np.zeros(count)

    for j in range(count):
        ang = start_ang + (j / (count - 1)) * (end_ang - start_ang)
        its = hex2float(
            content[start_idx + j * size_float : start_idx + (j + 1) * size_float]
        )
        angles[j] = ang
        intensities[j] = its

    return (angles, intensities), content


def raw2xy(fn: str | Path, target_folder: Path = None) -> Path:
    """Convert .raw file to .xy file (and save)."""
    fn = Path(fn)
    if target_folder is None:
        target_folder = fn.parent
    target_path = target_folder / fn.with_suffix(".xy").name

    RawFile.from_file(fn).to_xy_file(target_path)
    return target_path
