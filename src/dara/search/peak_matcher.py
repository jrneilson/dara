import numpy as np


ANGLE_TOLERANCE = 0.75  # maximum difference in angle
INTENSITY_TOLERANCE = 2  # maximum ratio of the intensities
MAX_INTENSITY_TOLERANCE = (
    10  # maximum ratio of the intensities to be considered as missing or extra
)


def distance_matrix(peaks1: np.ndarray, peaks2: np.ndarray) -> np.ndarray:
    """
    Return the distance matrix between two sets of peaks.

    The distance is defined as the maximum of the distance in position and the distance in intensity.
    The position distance is the absolute difference in position.
    The intensity distance is the absolute difference in log intensity.

    Args:
        peaks1: (n, 2) array of peaks with [position, intensity]
        peaks2: (m, 2) array of peaks with [position, intensity]

    Returns:
        (n, m) distance matrix
    """
    position_distance = np.abs(
        peaks1[:, 0].reshape(-1, 1) - peaks2[:, 0].reshape(1, -1)
    )
    intensity_distance = np.abs(
        np.log(peaks1[:, 1]).reshape(-1, 1) - np.log(peaks2[:, 1]).reshape(1, -1)
    )

    return np.max(np.array([position_distance, intensity_distance]), axis=0)


def find_best_match(
    peak_calc: np.ndarray, peak_obs: np.ndarray
) -> tuple[list, list, list, list]:
    """
    Find the best match between two sets of peaks.

    Args:
        peak_calc: the calculated peaks, (n, 2) array of peaks with [position, intensity]
        peak_obs: the observed peaks, (m, 2) array of peaks with [position, intensity]

    Returns:
        missing[j]: the indices of the missing peaks in the `obs peaks`
        matched[i, j]: the indices of both the matched peaks in the `calculated peaks` and the `observed peaks`
        extra[i]: the indices of the extra peaks in the `calculated peaks`
        wrong_intens[i, j]: the indices of the peaks with wrong intensities in both the
          `calculated peaks` and the `observed peaks`

    """
    matched = []
    extra = []
    wrong_intens = []

    distance = distance_matrix(peak_calc, peak_obs)
    peak_obs_acc = np.zeros(len(peak_obs))

    for peak_idx in np.argsort(peak_calc[:, 1])[::-1]:  # sort by intensity
        peak = peak_calc[peak_idx]
        best_match_idx = np.argmin(distance[peak_idx])

        best_match_peak = peak_obs[best_match_idx]

        if np.abs(peak[0] - best_match_peak[0]) > ANGLE_TOLERANCE or np.log(
            best_match_peak[1]
        ) - np.log(peak[0]) > np.log(MAX_INTENSITY_TOLERANCE):
            extra.append(peak_idx)
            continue

        matched.append((peak_idx, best_match_idx))
        peak_obs_acc[best_match_idx] += peak[1]
        updated_obs_peak = np.array(
            [
                best_match_peak[0],
                np.clip(
                    best_match_peak[1] - peak_obs_acc[best_match_idx],
                    a_min=1e-6,
                    a_max=None,
                ),
            ]
        )  # [position, intensity]
        distance[:, best_match_idx] = distance_matrix(
            peak_calc, updated_obs_peak.reshape(1, -1)
        )[:, 0]
    all_assigned = set([m[1] for m in matched])
    missing = [i for i in range(len(peak_obs)) if i not in all_assigned]

    # tell if a peak has wrong intensity by the sum of the intensities of the matched peaks
    to_be_deleted = set()
    for i in range(len(matched)):
        peak_idx = matched[i][1]
        if np.log(peak_obs[peak_idx][1]) - np.log(peak_obs_acc[peak_idx]) > np.log(
            MAX_INTENSITY_TOLERANCE
        ):
            missing.append(peak_idx)
            to_be_deleted.add(i)
        elif np.abs(
            np.log(peak_obs[peak_idx][1]) - np.log(peak_obs_acc[peak_idx])
        ) > np.log(INTENSITY_TOLERANCE):
            wrong_intens.append(matched[i])
            to_be_deleted.add(i)

    matched = [m for i, m in enumerate(matched) if i not in to_be_deleted]

    return missing, matched, extra, wrong_intens
