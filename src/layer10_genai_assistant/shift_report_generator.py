"""
Layer 10 - Automated Shift Report Generator.

FIX: added os.makedirs() -- same fix as executive_report_generator.py.
"""
from fpdf import FPDF, XPos, YPos
from datetime import datetime
import os


def generate_shift_report(
    line_id: str,
    shift_label: str,
    summary_text: str,
    oee_pct: float = None,
    top_downtime_cause: str = None,
    active_maintenance_flags: list = None,
    output_path: str = None,
):
    if output_path is None:
        safe_shift = "".join(c if c.isalnum() else "_" for c in shift_label)[:40]
        output_path = f"outputs/reports/shift_report_{line_id}_{safe_shift}.pdf"

    # FIX: see executive_report_generator.py -- .output() needs the parent
    # folder to already exist.
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"NeuroPlant AI - Shift Report",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", size=10)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, f"Generated {datetime.now().strftime('%d %b %Y %H:%M')}",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"Line: {line_id}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 8, f"Shift: {shift_label}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)

    if oee_pct is not None:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, f"Shift OEE: {oee_pct:.1f}%", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Summary:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 6, summary_text)
    pdf.ln(3)

    if top_downtime_cause:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Top Downtime Cause:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", size=11)
        pdf.multi_cell(0, 6, top_downtime_cause)
        pdf.ln(3)

    if active_maintenance_flags:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Active Maintenance Flags:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", size=11)
        for flag in active_maintenance_flags:
            pdf.cell(0, 7, f"- {flag}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.output(output_path)
    print(f"Shift report saved: {output_path}")
    return output_path


if __name__ == "__main__":
    generate_shift_report(
        line_id="LINE01",
        shift_label="Evening Shift - 12 Sep 2026",
        summary_text=(
            "Production ran at 78.3% fleet OEE. Top downtime cause: unplanned stop on "
            "CNC-02 (coolant pump alarm, 47 min). Active maintenance flag on CNC-07 "
            "(RUL 3.5 days, bearing wear). Energy intensity 0.42 kWh/unit, +6% vs baseline."
        ),
        oee_pct=78.3,
        top_downtime_cause="CNC-02 coolant pump alarm - 47 min unplanned stop",
        active_maintenance_flags=["CNC-07 - bearing wear, RUL 3.5 days"],
    )