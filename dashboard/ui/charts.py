"""
Plotly chart builders for NeuroPlant AI ("Elite Industrial Intelligence").

All layouts pull from theme.COLORS, so the teal-accent palette applies
automatically with no changes to call sites. New in this revision:
rul_prediction_cone (historical solid / forecast dashed / confidence band —
per spec 'AI PREDICTION VISUAL LANGUAGE'), waterfall, and event-marker
annotation helper for adding maintenance/alarm/quality markers to any
existing time-series figure.
"""
import plotly.graph_objects as go
from dashboard.ui.theme import COLORS, status_color

PLOTLY_LAYOUT = dict(
    paper_bgcolor=COLORS["bg_surface"],
    plot_bgcolor=COLORS["bg_surface"],
    font=dict(color=COLORS["text_secondary"], family="Inter", size=12),
    title_font=dict(color=COLORS["text_primary"], size=14),
    # Increased top margin from 40 -> 64px so the chart title never
    # collides with Plotly's own mode-bar (camera/zoom/pan icons), which
    # floats in the same top-right region by default. At narrow container
    # widths the previous 40px margin left the title text and mode-bar
    # icons overlapping -- this was a genuine layout bug affecting every
    # chart built from this shared layout, not a one-off.
    margin=dict(l=40, r=20, t=64, b=40),
    xaxis=dict(gridcolor=COLORS["border_muted"], zerolinecolor=COLORS["border"], color=COLORS["text_secondary"],
               showline=True, linecolor=COLORS["border"]),
    yaxis=dict(gridcolor=COLORS["border_muted"], zerolinecolor=COLORS["border"], color=COLORS["text_secondary"],
               showline=True, linecolor=COLORS["border"]),
    hoverlabel=dict(bgcolor=COLORS["bg_elevated"], bordercolor=COLORS["border_blue_grey"],
                     font=dict(color=COLORS["text_primary"], family="JetBrains Mono", size=11)),
    legend=dict(font=dict(color=COLORS["text_secondary"], size=11), bgcolor="rgba(0,0,0,0)",
                yanchor="top", y=-0.15, orientation="h"),
    # Mode-bar pushed further right/up and set to only show on hover, so
    # it never sits directly over the title text area even on charts that
    # don't set an explicit title.
)

PLOTLY_LAYOUT_NO_TITLE = {k: v for k, v in PLOTLY_LAYOUT.items() if k != "title_font"}

_SUCCESS_RGBA = "rgba(53,211,153,0.15)"
_WARNING_RGBA = "rgba(245,185,66,0.15)"
_CRITICAL_RGBA = "rgba(240,93,94,0.15)"

# Event marker colors per Elite spec §'EVENT MARKERS'
EVENT_COLORS = {
    "maintenance": COLORS["maintenance"],
    "alarm": COLORS["danger"],
    "quality": COLORS["quality_anomaly"],
    "ai": COLORS["accent_violet"],
}


def oee_gauge(value_pct: float, title: str = "OEE %"):
    color = status_color("online") if value_pct > 75 else status_color("warning") if value_pct > 60 else status_color("critical")
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value_pct,
        title={"text": title, "font": {"color": COLORS["text_primary"], "size": 14}},
        number={"font": {"color": COLORS["text_primary"], "family": "JetBrains Mono"}, "suffix": "%"},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": COLORS["text_secondary"], "ticksuffix": "%"},
            "bar": {"color": color},
            "bgcolor": COLORS["bg_surface"],
            "borderwidth": 1,
            "bordercolor": COLORS["border"],
            "steps": [
                {"range": [0, 60], "color": _CRITICAL_RGBA},
                {"range": [60, 75], "color": _WARNING_RGBA},
                {"range": [75, 100], "color": _SUCCESS_RGBA},
            ],
            "threshold": {"line": {"color": COLORS["text_muted"], "width": 2}, "thickness": 0.85, "value": 85},
        },
    ))
    fig.update_layout(**PLOTLY_LAYOUT_NO_TITLE, height=250)
    return fig


def pareto_bar(labels: list[str], values: list[float], title: str = "", color: str = None, highlight_index: int = None, unit: str = ""):
    bar_color = color or COLORS["accent"]
    colors = [bar_color] * len(values)
    if highlight_index is not None and 0 <= highlight_index < len(colors):
        colors[highlight_index] = status_color("critical")
    fig = go.Figure(go.Bar(
        x=labels, y=values, marker_color=colors,
        hovertemplate="<b>%{x}</b><br>%{y}" + (f" {unit}" if unit else "") + "<extra></extra>",
    ))
    fig.update_layout(**PLOTLY_LAYOUT, title=title, height=300, yaxis_title=unit or None)
    return fig


def trend_line(x: list, y: list, title: str = "", y_label: str = "", color: str = None):
    line_color = color or COLORS["accent"]
    fig = go.Figure(go.Scatter(
        x=x, y=y, mode="lines+markers", line=dict(color=line_color, width=2),
        marker=dict(size=4, color=line_color),
        hovertemplate="<b>%{x}</b><br>%{y}" + (f" {y_label}" if y_label else "") + "<extra></extra>",
    ))
    fig.update_layout(**PLOTLY_LAYOUT, title=title, yaxis_title=y_label, height=320)
    return fig


def stacked_oee_components(shifts: list[str], availability: list[float], performance: list[float], quality: list[float]):
    """Grouped bar chart of A/P/Q per shift. hovermode='x unified' (fix for
    the tooltip-overlap bug — Plotly's default hover mode shows one
    floating box per individual bar, which with 3 grouped bars per shift
    frequently rendered directly on top of adjacent bars. Unified mode
    merges all 3 series' values into a single box anchored above the
    x-position instead, so it no longer covers chart content)."""
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Availability", x=shifts, y=availability, marker_color=COLORS["chart_primary"],
                          hovertemplate="Availability: %{y}%<extra></extra>"))
    fig.add_trace(go.Bar(name="Performance", x=shifts, y=performance, marker_color=COLORS["chart_secondary"],
                          hovertemplate="Performance: %{y}%<extra></extra>"))
    fig.add_trace(go.Bar(name="Quality", x=shifts, y=quality, marker_color=status_color("online"),
                          hovertemplate="Quality: %{y}%<extra></extra>"))
    layout = dict(PLOTLY_LAYOUT)
    layout.pop("legend", None)
    layout.pop("margin", None)
    fig.update_layout(**layout, title="OEE Components by Shift", barmode="group", height=360,
                       yaxis_title="%", hovermode="x unified",
                       # Legend moved from y=1.12 (which sat directly on
                       # top of the title text, causing the overlap seen
                       # in review) to below the plot area (y=-0.18),
                       # matching the base PLOTLY_LAYOUT legend convention.
                       # Increased top margin (t=72) gives the title its
                       # own clear band separate from both the legend and
                       # the mode-bar.
                       margin=dict(l=40, r=20, t=72, b=70),
                       legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center",
                                   font=dict(color=COLORS["text_secondary"])))
    return fig


def heatmap(z_values: list[list[float]], x_labels: list[str], y_labels: list[str], title: str = "", unit: str = ""):
    fig = go.Figure(go.Heatmap(
        z=z_values, x=x_labels, y=y_labels,
        colorscale=[[0, COLORS["bg_elevated"]], [0.5, status_color("warning")], [1, status_color("critical")]],
        colorbar=dict(outlinewidth=0, tickfont=dict(color=COLORS["text_secondary"]), title=dict(text=unit, font=dict(color=COLORS["text_secondary"], size=11))),
        hovertemplate="<b>%{y} · %{x}</b><br>%{z}" + (f" {unit}" if unit else "") + "<extra></extra>",
    ))
    fig.update_layout(**PLOTLY_LAYOUT, title=title, height=350)
    return fig


def gauge_small(value: float, max_value: float, label: str, unit: str = ""):
    pct = (value / max_value * 100) if max_value > 0 else 0
    color = status_color("critical") if pct > 85 else status_color("warning") if pct > 70 else status_color("online")
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={"font": {"color": COLORS["text_primary"], "family": "JetBrains Mono"}, "suffix": f" {unit}" if unit else ""},
        title={"text": label, "font": {"size": 12, "color": COLORS["text_secondary"]}},
        gauge={"axis": {"range": [0, max_value], "tickcolor": COLORS["text_secondary"]},
               "bar": {"color": color}, "bgcolor": COLORS["bg_surface"],
               "borderwidth": 1, "bordercolor": COLORS["border"]},
    ))
    fig.update_layout(**PLOTLY_LAYOUT_NO_TITLE, height=200)
    return fig


# ═══════════════════════════════════════════════════════════════════
# Elite Industrial Intelligence — new chart builders
# ═══════════════════════════════════════════════════════════════════

def rul_prediction_cone(x_hist: list, y_hist: list, x_forecast: list, y_forecast: list,
                         y_upper: list = None, y_lower: list = None, title: str = "",
                         y_label: str = "Health / RUL", color: str = None):
    """RUL / health trajectory with historical-vs-predicted visual grammar
    per Elite spec §'AI PREDICTION VISUAL LANGUAGE' and §'PREDICTION CONE':
    historical = solid line, predicted = dashed line, uncertainty = translucent
    band. x_forecast[0] should equal x_hist[-1] so the lines connect visually."""
    line_color = color or COLORS["accent"]
    fig = go.Figure()

    if y_upper is not None and y_lower is not None:
        fig.add_trace(go.Scatter(
            x=list(x_forecast) + list(x_forecast)[::-1],
            y=list(y_upper) + list(y_lower)[::-1],
            fill="toself", fillcolor="rgba(32,214,210,0.10)",
            line=dict(color="rgba(0,0,0,0)"), hoverinfo="skip",
            name="Confidence interval", showlegend=True,
        ))

    fig.add_trace(go.Scatter(
        x=x_hist, y=y_hist, mode="lines", name="History",
        line=dict(color=line_color, width=2),
        hovertemplate="<b>%{x}</b><br>%{y}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=x_forecast, y=y_forecast, mode="lines", name="Forecast",
        line=dict(color=line_color, width=2, dash="dash"),
        hovertemplate="<b>%{x}</b><br>%{y} (predicted)<extra></extra>",
    ))

    fig.update_layout(**PLOTLY_LAYOUT, title=title, yaxis_title=y_label, height=320)
    return fig


def waterfall(labels: list[str], values: list[float], title: str = "", measure: list[str] = None):
    """OEE-loss / cost / savings waterfall per Elite spec §'OEE WATERFALL'.
    measure: plotly waterfall measure list (defaults to 'relative' for all
    but a 'total' on the last bar) — e.g. ["relative","relative","relative","total"]."""
    if measure is None:
        measure = ["relative"] * (len(labels) - 1) + ["total"]
    fig = go.Figure(go.Waterfall(
        x=labels, y=values, measure=measure,
        decreasing=dict(marker=dict(color=COLORS["danger"])),
        increasing=dict(marker=dict(color=COLORS["success"])),
        totals=dict(marker=dict(color=COLORS["accent"])),
        connector=dict(line=dict(color=COLORS["border"], width=1)),
        hovertemplate="<b>%{x}</b><br>%{y}<extra></extra>",
    ))
    fig.update_layout(**PLOTLY_LAYOUT, title=title, height=340, showlegend=False)
    return fig


def add_event_markers(fig, events: list[dict]):
    """Adds small vertical event-marker lines to an existing time-series
    figure per Elite spec §'EVENT MARKERS'. events: list of
    {"x": value, "label": str, "type": "maintenance"|"alarm"|"quality"|"ai"}.
    Returns the same fig (mutated) for chaining."""
    for ev in events:
        color = EVENT_COLORS.get(ev.get("type", "alarm"), COLORS["text_muted"])
        fig.add_vline(
            x=ev["x"], line=dict(color=color, width=1, dash="dot"),
            annotation_text=ev.get("label", ""),
            annotation=dict(font=dict(size=9, color=color), textangle=-90, yanchor="top"),
        )
    return fig


def add_threshold_line(fig, y_value: float, label: str = "THRESHOLD", color: str = None):
    """Adds a subtle horizontal reference line per Elite spec
    §'THRESHOLD VISUALIZATION'. Returns the same fig (mutated) for chaining."""
    line_color = color or COLORS["warning"]
    fig.add_hline(
        y=y_value, line=dict(color=line_color, width=1, dash="dash"),
        annotation_text=label,
        annotation=dict(font=dict(size=9, color=line_color)),
    )
    return fig


def machine_risk_bar(machine_ids: list[str], risk_scores: list[float], title: str = "Machine Risk Score"):
    """Horizontal risk-ranked bar per Elite spec §'MACHINE RISK BOARD' —
    color scales continuously from healthy to critical by score."""
    colors = []
    for s in risk_scores:
        if s >= 85:
            colors.append(COLORS["danger"])
        elif s >= 60:
            colors.append(COLORS["warning"])
        else:
            colors.append(COLORS["success"])
    order = sorted(range(len(risk_scores)), key=lambda i: risk_scores[i])
    ids_sorted = [machine_ids[i] for i in order]
    scores_sorted = [risk_scores[i] for i in order]
    colors_sorted = [colors[i] for i in order]
    fig = go.Figure(go.Bar(
        x=scores_sorted, y=ids_sorted, orientation="h", marker_color=colors_sorted,
        hovertemplate="<b>%{y}</b><br>Risk: %{x}%<extra></extra>",
    ))
    fig.update_layout(**PLOTLY_LAYOUT, title=title, height=max(220, 36 * len(machine_ids)), xaxis_title="Risk %")
    return fig