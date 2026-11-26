"""
Layer 9 - Automated Sustainability (ESG) Report Generator.

FIX: added os.makedirs() -- same fix as the other two report generators.
"""
from fpdf import FPDF, XPos, YPos
from datetime import datetime
import os


def generate_sustainability_report(
    month: str,
    total_co2_kg: float,
    energy_cost_per_unit: float,
    prev_month_co2_kg: float,
    energy_intensity_index: float,
    top_opportunities: list[str],
    output_path: str = "outputs/reports/sustainability_report.pdf",
):
    co2_change_pct = round(((total_co2_kg - prev_month_co2_kg) / prev_month_co2_kg * 100), 1) if prev_month_co2_kg else 0

    # FIX: create the output folder before fpdf2 writes to it.
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    # Replace em dash with hyphen to avoid latin-1 encoding error
    pdf.cell(0, 10, f"NeuroPlant AI - Sustainability Report ({month})",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", size=11)
    pdf.ln(5)

    sign = "+" if co2_change_pct > 0 else ""
    pdf.cell(0, 8, f"Total CO2 Emissions: {total_co2_kg} kg ({sign}{co2_change_pct}% vs prev month)",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 8, f"Energy Cost per Unit: Rs {energy_cost_per_unit}",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 8, f"Energy Intensity Index: {energy_intensity_index}",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(5)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Top Energy Saving Opportunities:",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", size=11)
    for i, opp in enumerate(top_opportunities, 1):
        pdf.cell(0, 7, f"{i}. {opp}",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.output(output_path)
    print(f"Report saved: {output_path}")
    return output_path


if __name__ == "__main__":
    generate_sustainability_report(
        month="July 2026",
        total_co2_kg=11250.5,
        energy_cost_per_unit=4.85,
        prev_month_co2_kg=12100.0,
        energy_intensity_index=0.92,
        top_opportunities=[
            "Fix compressed air leak on Machine 7 - save 340 kWh/month",
            "Shift Line 2 non-critical processes to off-peak hours",
            "Upgrade Line 1 motor to IE3 efficiency class",
        ],
    )