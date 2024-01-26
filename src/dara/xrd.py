"""Load and process XRD data files (.xrdml, .xy)."""
from __future__ import annotations

from pathlib import Path

import dict2xml
import matplotlib.pyplot as plt
import numpy as np
import xmltodict
from monty.json import MSONable


class XRDData(MSONable):
    """General XRD data class; this is the base class for XRDMLFile and XYFile."""

    def __init__(self, angles: np.ndarray, intensities: np.ndarray):
        """Initialize XRD data from angles (2-theta values) and intensities/counts."""
        self.angles = angles
        self.intensities = intensities

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

    def to_xy_file(self, fn: str | Path = "xrd_data.xy"):
        """Save as a .xy file."""
        np.savetxt(
            Path(fn).as_posix(),
            np.column_stack((self, self.angles, self.intensities)),
            fmt="%f",
        )


class XRDMLFile(XRDData):
    """XRDML file class, useful for loading .xrdml data."""

    def __init__(self, angles, intensities, xrdml_dict: dict | None = None):
        """Initialize andXRDML file; providing dictionary allows one to serialize and deserialize the XRDML file."""
        super().__init__(angles, intensities)
        self.xrdml_dict = xrdml_dict

    @classmethod
    def from_file(cls, path: str | Path) -> XRDMLFile:
        """Load data from an XRDML file."""
        xrdml_dict = load_xrdml(Path(path))
        angles, intensities = get_xrdml_data(xrdml_dict)
        return cls(angles=angles, intensities=intensities, xrdml_dict=xrdml_dict)

    def to_file(self, fn: str | Path = "xrd_data.xrdml"):
        """Save as an XRDML file."""
        with open(Path(fn), "w") as f:
            f.write(dict2xml(self.xrd_dict))


class XYFile(XRDData):
    """XY file class, useful for loading .xy data."""

    def __init__(self, angles, intensities):
        super().__init__(angles, intensities)

    @classmethod
    def from_file(cls, path: str | Path) -> XYFile:
        """Load data from a .xy file."""
        path = Path(path)
        angles, intensities = np.loadtxt(Path(path), unpack=True)
        return cls(angles, intensities)

    def to_file(self, fn: str | Path = "xrd_data.xy"):
        """Save as a .xy file."""
        return self.to_xy_file(fn)


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
    """Convert xrdml file to .xy file."""
    fn = Path(fn)
    if target_folder is None:
        target_folder = fn.parent
    target_path = target_folder / fn.with_suffix(".xy").name

    XRDMLFile.from_file(fn).to_xy_file(target_path)
    return target_path
