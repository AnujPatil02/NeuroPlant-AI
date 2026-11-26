"""
Layer 10 - Automated Executive Report Generator.

FIX: added os.makedirs() so the output folder is created before fpdf2
writes to it -- .output() does not create missing parent directories,
which was throwing on a fresh clone and looked like "fpdf is broken".
"""
from fpdf import FPDF, XPos, YPos
from datetime import datetime
import os


def generate_executive_report(
    period_label: str,
    oee_trend_summary: str,
    top_root_causes: list,
    maintenance_completed_vs_planned: str,
    energy_cost_trend: str,
    recommended_actions: list,
    output_path: str = None,
):
    if output_path is None:
        safe_period = "".join(c if c.isalnum() else "_" for c in period_label)[:40]
        output_path = f"outputs/reports/executive_report_{safe_period}.pdf"

    # FIX: fpdf2's .output() does NOT create missing parent folders -- on
    # a fresh clone/run, "outputs/reports/" doesn't exist yet and .output()
    # throws, which looked like "fpdf is broken" but was actually a
    # missing directory.
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "NeuroPlant AI - Weekly Executive Report",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", size=10)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, f"Generated {datetime.now().strftime('%d %b %Y %H:%M')}",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"Reporting Period: {period_label}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    def section(title: str):
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(20, 90, 85)
        pdf.cell(0, 9, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", size=11)

    section("OEE Trend (7-Day):")
    pdf.multi_cell(0, 6, oee_trend_summary)
    pdf.ln(2)

    section("Top 3 Root Causes of Performance Loss:")
    for cause in top_root_causes[:3]:
        pdf.cell(0, 7, f"- {cause}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    section("Maintenance: Completed vs Planned:")
    pdf.multi_cell(0, 6, maintenance_completed_vs_planned)
    pdf.ln(2)

    section("Energy Cost per Unit Trend:")
    pdf.multi_cell(0, 6, energy_cost_trend)
    pdf.ln(2)

    section("Recommended Priority Actions - Next Week:")
    for action in recommended_actions[:3]:
        pdf.cell(0, 7, f"- {action}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.output(output_path)
    print(f"Executive report saved: {output_path}")
    return output_path


if __name__ == "__main__":
    generate_executive_report(
        period_label="Week of 8-12 Sep 2026",
        oee_trend_summary="Fleet OEE trended from 74% to 78.3% over the week, still 6.7 points below the 85% target.",
        top_root_causes=[
            "Unplanned coolant pump stoppages on Component Machining line",
            "Cycle time drift on CNC-06 (Bearing Housing) - 9% above design",
            "Elevated defect rate on SKU-118 tied to spindle RPM deviation",
        ],
        maintenance_completed_vs_planned="4 of 6 planned maintenance windows completed on schedule.",
        energy_cost_trend="Energy cost per unit down 3.2% week-over-week to Rs 4.85/unit.",
        recommended_actions=[
            "Inspect CNC-02 cooling system before next production cycle",
            "Schedule CNC-07 bearing replacement within next low-production window",
            "Fix compressed air coupling leak on Line 01 network",
        ],
    )