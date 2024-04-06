from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import plotly.graph_objects as go

if TYPE_CHECKING:
    from dara.result import RefinementResult


def visualize(
    result: RefinementResult,
    diff_offset: bool = False,
    missing_peaks: list[list[float]] | np.ndarray | None = None,
    extra_peaks: list[list[float]] | np.ndarray | None = None,
):
    """Visualize the result from the refinement. It uses plotly as the backend engine."""
    colormap = [
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
        "#17becf",
    ]

    plot_data = result.plot_data

    # Create a Plotly figure with size 800x600
    fig = go.Figure()

    # fix the size of the box
    fig.update_layout(
        autosize=True, xaxis=dict(range=[min(plot_data.x), max(plot_data.x)])
    )

    # Adding scatter plot for observed data
    fig.add_trace(
        go.Scatter(
            x=plot_data.x,
            y=plot_data.y_obs,
            mode="markers",
            marker=dict(color="blue", size=3, symbol="cross-thin-open"),
            name="Observed",
        )
    )

    # Adding line plot for calculated data
    fig.add_trace(
        go.Scatter(
            x=plot_data.x,
            y=plot_data.y_calc,
            mode="lines",
            line=dict(color="green", width=2),
            name="Calculated",
        )
    )

    # Adding line plot for background
    fig.add_trace(
        go.Scatter(
            x=plot_data.x,
            y=plot_data.y_bkg,
            mode="lines",
            line=dict(color="#FF7F7F", width=2),
            name="Background",
            opacity=0.5,
        )
    )

    diff = np.array(plot_data.y_obs) - np.array(plot_data.y_calc)
    diff_offset_val = 1.1 * max(diff) if diff_offset else 0  # 10 percent below

    # Adding line plot for difference
    fig.add_trace(
        go.Scatter(
            x=plot_data.x,
            y=diff - diff_offset_val,
            mode="lines",
            line=dict(color="#808080", width=1),
            name="Difference",
            opacity=0.7,
        )
    )

    weight_fractions = result.get_phase_weights()
    # Adding dashed lines for phases
    for i, (phase_name, phase) in enumerate(plot_data.structs.items()):
        # add area under the curve between the curve and the plot_data["y_bkg"]
        if i >= len(colormap) - 1:
            i = i % (len(colormap) - 1)
        fig.add_trace(
            go.Scatter(
                x=plot_data.x,
                y=plot_data.y_bkg,
                mode="lines",
                line=dict(color=colormap[i], width=0),
                fill=None,
                showlegend=False,
                hoverinfo="none",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=plot_data.x,
                y=np.array(phase) + np.array(plot_data.y_bkg),
                mode="lines",
                line=dict(color=colormap[i], width=1.5),
                fill="tonexty",
                name=f"{phase_name}"
                + (
                    f" ({weight_fractions[phase_name] * 100:.2f} %)"
                    if len(weight_fractions) > 1
                    else ""
                ),
                visible="legendonly",
            )
        )

    if missing_peaks is not None:
        missing_peaks = np.array(result.missing_peaks).reshape(-1, 2)
        fig.add_trace(
            go.Scatter(
                x=missing_peaks[:, 0],
                y=np.zeros_like(missing_peaks[:, 0]),
                mode="markers",
                marker=dict(color="#f9726a", symbol=53, size=10, opacity=0.8),
                name="Missing peaks",
                visible="legendonly",
                text=[f"{x:.2f}, {y:.2f}" for x, y in missing_peaks],
            )
        )

    if extra_peaks is not None:
        extra_peaks = np.array(result.extra_peaks).reshape(-1, 2)
        fig.add_trace(
            go.Scatter(
                x=extra_peaks[:, 0],
                y=np.zeros_like(extra_peaks[:, 0]),
                mode="markers",
                marker=dict(color="#335da0", symbol=53, size=10, opacity=0.8),
                name="Extra peaks",
                visible="legendonly",
                text=[f"{x:.2f}, {y:.2f}" for x, y in extra_peaks],
                hovertemplate="%{text}",
            )
        )

    title = f"{result.lst_data.pattern_name} (Rwp={result.lst_data.rwp:.2f}%)"

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
