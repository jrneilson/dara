import re
from pathlib import Path
from typing import Any, Union

import numpy as np
import plotly.graph_objects as go


def get_result(control_file: Path):
    """
    Get the result from the refinement.

    :param control_file: the path to the control file (.sav)
    """
    lst_path = control_file.parent / f"{control_file.stem}.lst"
    dia_path = control_file.parent / f"{control_file.stem}.dia"

    result = {
        **parse_lst(lst_path),
        "plot_data": parse_dia(dia_path),
    }

    return result


def parse_lst(lst_path: Path):
    """
    Get results from the .lst file. This file mainly contains some numbers for the refinement.

    Example of the .lst file:
    Rietveld refinement to file(s) Mg3MnNi3O8.xy
    BGMN version 4.2.23, 8301 measured points, 78 peaks, 20 parameters
    Start: Mon Dec 18 11:43:20 2023; End: Mon Dec 18 11:43:21 2023
    43 iteration steps

    Rp=4.14%  Rpb=50.39%  R=13.55%  Rwp=8.98% Rexp=1.47%
    Durbin-Watson d=0.06
    1-rho=13.6%

    Global parameters and GOALs
    ****************************
    QMg3MnNi3O8166sym=0.0700+-0.0046
    QNiO=0.9300+-0.0046
    EPS2=-0.001657+-0.000033

    Local parameters and GOALs for phase Mg3MnNi3O8166sym
    ******************************************************
    SpacegroupNo=166
    HermannMauguin=R-32/m
    XrayDensity=4.943
    Rphase=26.64%
    UNIT=NM
    A=0.5898+-0.0013
    C=1.4449+-0.0062
    k1=1.00000
    B1=0.00492+-0.00076
    GEWICHT=0.0288+-0.0019
    GrainSize(1,1,1)=64.7+-10.0
    Atomic positions for phase Mg3MnNi3O8166sym
    ---------------------------------------------
      9     0.5000  0.0000  0.0000     E=(MG(1.0000))
      3     0.0000  0.0000  0.0000     E=(MN(1.0000))
      9     0.5000  0.0000  0.5000     E=(NI(1.0000))
     18     0.0268 -0.0268  0.7429     E=(O(1.0000))
      6     0.0000  0.0000  0.2511     E=(O(1.0000))

    Local parameters and GOALs for phase NiO
    ******************************************************
    SpacegroupNo=225
    HermannMauguin=F4/m-32/m
    XrayDensity=6.760
    Rphase=11.31%
    UNIT=NM
    A=0.418697+-0.000027
    k1=0
    B1=0.00798+-0.00022
    GEWICHT=0.3827+-0.0049
    GrainSize(1,1,1)=53.2+-1.5
    Atomic positions for phase NiO
    ---------------------------------------------
      4     0.0000  0.0000  0.0000     E=(NI+2(1.0000))
      4     0.5000  0.5000  0.5000     E=(O-2(1.0000))

    Args:
        lst_path:

    Returns
    -------
        phase_results: a dictionary of the results for each phase

    """

    def parse_values(v_: str) -> Union[float, tuple[float, float], None, str, int]:
        try:
            v_ = v_.strip("%")
            if v_ == "ERROR" or v_ == "UNDEF":
                return None
            if "+-" in v_:
                v_ = (float(v_.split("+-")[0]), float(v_.split("+-")[1]))
            else:
                v_ = float(v_)
                if v_.is_integer():
                    v_ = int(v_)
        except ValueError:
            pass
        return v_

    def parse_section(text: str) -> dict[str, Any]:
        section = dict(re.findall(r"^(\w+)=(.+?)$", text, re.MULTILINE))
        section = {k: parse_values(v) for k, v in section.items()}
        return section

    if not lst_path.exists():
        raise FileNotFoundError(f"Cannot find the .lst file from {lst_path}")

    with lst_path.open() as f:
        texts = f.read()

    pattern_name = re.search(r"Rietveld refinement to file\(s\) (.+?)\n", texts).group(
        1
    )
    result = {"raw_lst": texts, "pattern_name": pattern_name}

    num_steps = int(re.search(r"(\d+) iteration steps", texts).group(1))
    result["num_steps"] = num_steps

    for var in ["Rp", "Rpb", "R", "Rwp", "Rexp"]:
        result[var] = float(re.search(rf"{var}=(\d+\.\d+)%", texts).group(1))
    result["d"] = float(re.search(r"Durbin-Watson d=(\d+\.\d+)", texts).group(1))
    result["1-rho"] = float(re.search(r"1-rho=(\d+\.\d+)%", texts).group(1))

    # global goals
    global_parameters_text = re.search(
        r"Global parameters and GOALs\n(.*?)\n(?:\n|\Z)", texts, re.DOTALL
    ).group(1)
    global_parameters = parse_section(global_parameters_text)
    result.update(global_parameters)

    phases_results = dict(
        re.findall(
            r"Local parameters and GOALs for phase (.+?)\n(.*?)\n(?:\n|\Z)",
            texts,
            re.DOTALL,
        )
    )

    phases_results = {k: parse_section(v) for k, v in phases_results.items()}

    result["phases_results"] = phases_results
    return result


def parse_dia(dia_path: Path):
    """
    Get the results from the .dia file. This file mainly contains curves for the refinement.

    // layout of the scanHeap:
    // [0] = 2theta
    // [1] = iObs
    // [2] = iCalc
    // [3] = iBkgr
    // [4...n] = strucs
    """
    if not dia_path.exists():
        raise FileNotFoundError(f"Cannot find the .dia file from {dia_path}")

    # read first line to get the keys
    dia_text = dia_path.read_text().split("\n")
    metadata = dia_text[0]

    struct_names = re.findall(r"STRUC\[\d+]=([\w()]+)", metadata)

    raw_data = np.loadtxt(dia_text[1:])
    data = {
        "x": raw_data[:, 0],
        "y_obs": raw_data[:, 1],
        "y_calc": raw_data[:, 2],
        "y_bkg": raw_data[:, 3],
        "structs": {name: raw_data[:, i + 4] for i, name in enumerate(struct_names)},
    }

    return data


def visualize(result_dict: dict[str, Any]):
    """
    Visualize the result from the refinement.

    Args:
        result_dict: the result from the refinement
    """
    colormap = [
        "#1f77b4",
        "#aec7e8",
        "#ff7f0e",
        "#2ca02c",
        "#98df8a",
        "#d62728",
        "#9467bd",
        "#c5b0d5",
        "#8c564b",
        "#e377c2",
        "#f7b6d2",
        "#7f7f7f",
        "#bcbd22",
        "#dbdb8d",
        "#17becf",
        "#9edae5",
    ]

    if "plot_data" not in result_dict:
        raise ValueError("No plot data in the result dict!")

    if any(
        x not in result_dict["plot_data"]
        for x in ["x", "y_obs", "y_calc", "y_bkg", "structs"]
    ):
        raise ValueError("Missing data in the plot data!")

    plot_data = result_dict["plot_data"]

    # Create a Plotly figure with size 800x600
    fig = go.Figure()

    # fix the size of the box
    fig.update_layout(
        autosize=True, xaxis=dict(range=[plot_data["x"].min(), plot_data["x"].max()])
    )

    # Adding scatter plot for observed data
    fig.add_trace(
        go.Scatter(
            x=plot_data["x"],
            y=plot_data["y_obs"],
            mode="markers",
            marker=dict(color="blue", size=5, symbol="cross-thin-open"),
            name="Observed",
        )
    )

    # Adding line plot for calculated data
    fig.add_trace(
        go.Scatter(
            x=plot_data["x"],
            y=plot_data["y_calc"],
            mode="lines",
            line=dict(color="green", width=2),
            name="Calculated",
        )
    )

    # Adding line plot for background
    fig.add_trace(
        go.Scatter(
            x=plot_data["x"],
            y=plot_data["y_bkg"],
            mode="lines",
            line=dict(color="red", width=2),
            name="Background",
        )
    )

    # Adding line plot for difference
    fig.add_trace(
        go.Scatter(
            x=plot_data["x"],
            y=plot_data["y_obs"] - plot_data["y_calc"],
            mode="lines",
            line=dict(color="#17becf", width=2),
            name="Difference",
        )
    )

    # Adding dashed lines for phases
    for i, (phase_name, phase) in enumerate(plot_data["structs"].items()):
        # add area under the curve between the curve and the plot_data["y_bkg"]
        if i >= len(colormap) - 1:
            i = i % (len(colormap) - 1)
        fig.add_trace(
            go.Scatter(
                x=plot_data["x"],
                y=plot_data["y_bkg"],
                mode="lines",
                line=dict(color=colormap[i], width=0),
                fill=None,
                showlegend=False,
                hoverinfo="none",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=plot_data["x"],
                y=phase + plot_data["y_bkg"],
                mode="lines",
                line=dict(color=colormap[i], width=1.5),
                fill="tonexty",
                name=phase_name,
                visible="legendonly",
            )
        )

    title = f"{result_dict['pattern_name']} (Rwp={result_dict['Rwp']:.2f}%)"

    # Updating layout with titles and labels
    fig.update_layout(
        title=title,
        xaxis_title="2θ [°]",
        yaxis_title="Intensity",
        legend_title="",
        font=dict(family="Arial, sans-serif", color="RebeccaPurple"),
    )

    # white background
    fig.update_layout(plot_bgcolor="white")
    fig.add_hline(y=0, line_width=1)

    # add tick
    fig.update_xaxes(ticks="outside", tickwidth=1, tickcolor="black", ticklen=10)
    fig.update_yaxes(ticks="outside", tickwidth=1, tickcolor="black", ticklen=10)

    # add border to the plot
    fig.update_layout(
        xaxis=dict(showline=True, linewidth=1, linecolor="black", mirror=True),
        yaxis=dict(showline=True, linewidth=1, linecolor="black", mirror=True),
    )

    return fig
