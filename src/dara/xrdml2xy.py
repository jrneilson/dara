"""Convert xrdml file to x and y arrays."""

from pathlib import Path

import numpy as np
import xmltodict


def xrdml2xy(file: Path, target_folder: Path = None) -> Path:
    """Convert xrdml file to x and y arrays."""
    if target_folder is None:
        target_folder = file.parent
    target_path = target_folder / (file.stem + ".xy")

    with file.open("r", encoding="utf-8") as f:
        xrd_dict = xmltodict.parse(f.read())
        min_angle = float(
            xrd_dict["xrdMeasurements"]["xrdMeasurement"]["scan"]["dataPoints"]["positions"][0]["startPosition"]
        )
        max_angle = float(
            xrd_dict["xrdMeasurements"]["xrdMeasurement"]["scan"]["dataPoints"]["positions"][0]["endPosition"]
        )

        intensities = xrd_dict["xrdMeasurements"]["xrdMeasurement"]["scan"]["dataPoints"]["counts"]["#text"]
        intensities = np.array([float(val) for val in intensities.split()])
        angles = np.linspace(min_angle, max_angle, len(intensities))
        np.savetxt(target_path.as_posix(), np.column_stack((angles, intensities)), fmt="%f")

        return target_path
