"""CSV and PDF export for saved Reports — both read ONLY from `Report.results` (the frozen
snapshot), never recomputing, matching the frozen-snapshot design `report_calculations.py` and
`whatif_calculations.py` (via `Scenario`) already established. No fake numbers are ever
generated here — an export with no data for a section says so, it never fabricates a figure.

CSV reuses the exact `io.StringIO` + `csv.writer` + generator pattern from
`routers/production.py`'s `/production/export` (this codebase's only prior export endpoint).
PDF is built with `fpdf2` (pure-Python, no system/apt dependencies) — the first new backend
dependency added in this build. PDF v1 deliberately stays tabular/text plus at most 1-2 simple
native bar charts (drawn with fpdf2's own rect/line primitives) — the full interactive chart set
from the module spec stays on the frontend preview; this is a disclosed scope line, not an
omission.
"""

import csv
import io
from collections.abc import Iterator
from typing import Any

from fpdf import FPDF

from app.models.reporting import Report

SECTION_LABELS = {
    "production": "Production",
    "equipment": "Equipment",
    "maintenance": "Maintenance",
    "production_loss": "Production Loss",
    "economics": "Economics",
    "alerts": "Alerts",
    "ai_insights": "AI Insights",
    "production_trend": "Production Trend",
    "production_by_scope": "Production by Scope",
    "actual_vs_target": "Actual vs. Target",
    "executive_summary": "Executive Summary",
    "scenario": "What-If Scenario",
}


def _flatten_filters(filters: dict) -> str:
    if not filters:
        return "None"
    return "; ".join(f"{k}={v}" for k, v in filters.items())


# ----- CSV -----


def build_csv_export(report: Report) -> Iterator[str]:
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    def flush():
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)

    writer.writerow([report.name])
    writer.writerow(["Report type", report.report_type])
    writer.writerow(["Generated", report.last_generated_at.isoformat() if report.last_generated_at else ""])
    writer.writerow(["Filters", _flatten_filters(report.filters or {})])
    writer.writerow([])
    yield from flush()

    results = report.results or {}
    sections: dict[str, Any] = results.get("sections", {})
    for key, section in sections.items():
        writer.writerow([f"== {SECTION_LABELS.get(key, key)} =="])
        yield from flush()
        _write_section_rows(writer, section)
        yield from flush()
        writer.writerow([])
        yield from flush()

    writer.writerow(["Disclaimer", results.get("disclaimer_text", "")])
    writer.writerow(["Synthetic data", results.get("synthetic_data_disclaimer", "")])
    yield from flush()


def _write_section_rows(writer, section: Any) -> None:
    if not isinstance(section, dict):
        writer.writerow([str(section)])
        return
    for key, value in section.items():
        if key == "_traceability":
            continue
        if isinstance(value, list) and value and isinstance(value[0], dict):
            columns = sorted({k for row in value for k in row.keys()})
            writer.writerow([key])
            writer.writerow(columns)
            for row in value:
                writer.writerow([row.get(c, "") for c in columns])
        elif isinstance(value, dict):
            writer.writerow([key])
            for sub_key, sub_value in value.items():
                writer.writerow(["", sub_key, sub_value])
        elif isinstance(value, list):
            writer.writerow([key, "; ".join(str(v) for v in value)])
        else:
            writer.writerow([key, value])

    traceability = section.get("_traceability") if isinstance(section, dict) else None
    if traceability:
        writer.writerow(["Source", traceability.get("source_module", "")])
        writer.writerow(["Methodology", traceability.get("methodology", "")])
        if traceability.get("record_count") is not None:
            writer.writerow(["Record count", traceability["record_count"]])


# ----- PDF -----

# fpdf2's core "Helvetica" font only supports latin-1 — but disclaimer/methodology/insight text
# throughout this codebase freely uses em-dashes, curly quotes, etc. Rather than hunting down
# every string literal across every module that might end up embedded in a report (disclaimers,
# guardrail messages, insight titles...), every piece of text is normalized to ASCII at this one
# boundary, right before it reaches fpdf2 — the correct place to fix an encoding mismatch, not
# scattered edits to source strings that were never written with a latin-1 constraint in mind.
_ASCII_REPLACEMENTS = {
    "—": "-", "–": "-",  # em dash, en dash
    "‘": "'", "’": "'",  # curly single quotes
    "“": '"', "”": '"',  # curly double quotes
    "…": "...",  # ellipsis
    "×": "x",  # multiplication sign
    "→": "->", "←": "<-",  # arrows
    "≥": ">=", "≤": "<=",
}


def _ascii_safe(text: Any) -> str:
    value = str(text)
    for char, replacement in _ASCII_REPLACEMENTS.items():
        value = value.replace(char, replacement)
    return value.encode("latin-1", errors="replace").decode("latin-1")


class _ReportPDF(FPDF):
    def header(self) -> None:  # noqa: D102 - fpdf2 lifecycle hook
        pass

    def cell(self, *args, **kwargs):  # noqa: D102
        if "text" in kwargs:
            kwargs["text"] = _ascii_safe(kwargs["text"])
        elif len(args) >= 3:
            args = (*args[:2], _ascii_safe(args[2]), *args[3:])
        return super().cell(*args, **kwargs)

    def multi_cell(self, *args, **kwargs):  # noqa: D102
        if "text" in kwargs:
            kwargs["text"] = _ascii_safe(kwargs["text"])
        elif len(args) >= 3:
            args = (*args[:2], _ascii_safe(args[2]), *args[3:])
        return super().multi_cell(*args, **kwargs)


def build_pdf_export(report: Report) -> bytes:
    pdf = _ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 10, report.name, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(0, 6, f"Report type: {report.report_type}", new_x="LMARGIN", new_y="NEXT")
    generated = report.last_generated_at.strftime("%Y-%m-%d %H:%M UTC") if report.last_generated_at else "-"
    pdf.cell(0, 6, f"Generated: {generated}", new_x="LMARGIN", new_y="NEXT")
    pdf.multi_cell(0, 6, f"Filters: {_flatten_filters(report.filters or {})}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_text_color(0, 0, 0)

    results = report.results or {}
    sections: dict[str, Any] = results.get("sections", {})

    if "executive_summary" in sections:
        _pdf_executive_summary(pdf, sections["executive_summary"])

    for key, section in sections.items():
        if key == "executive_summary":
            continue
        _pdf_section(pdf, SECTION_LABELS.get(key, key), section)

    _pdf_bar_chart_if_available(pdf, sections)

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.multi_cell(0, 5, results.get("disclaimer_text", ""), new_x="LMARGIN", new_y="NEXT")
    synthetic = results.get("synthetic_data_disclaimer")
    if synthetic:
        pdf.ln(1)
        pdf.multi_cell(0, 5, synthetic, new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())


def _pdf_executive_summary(pdf: FPDF, summary: dict) -> None:
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 8, "Executive Summary", new_x="LMARGIN", new_y="NEXT")
    labels = {
        "what_happened": "What Happened?",
        "why_it_matters": "Why It Matters",
        "biggest_risks": "Biggest Risks",
        "biggest_opportunities": "Biggest Opportunities",
        "recommended_investigations": "Recommended Investigations",
    }
    for key, label in labels.items():
        value = summary.get(key)
        if not value:
            continue
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, label, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        if isinstance(value, list):
            for item in value:
                pdf.multi_cell(0, 5, f"- {item}", new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.multi_cell(0, 5, str(value), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
    pdf.ln(2)


def _pdf_section(pdf: FPDF, label: str, section: Any) -> None:
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 8, label, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)

    if not isinstance(section, dict):
        pdf.multi_cell(0, 5, str(section), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        return

    for key, value in section.items():
        if key == "_traceability":
            continue
        if isinstance(value, list) and value and isinstance(value[0], dict):
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 5, f"{key}:", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            for row in value[:15]:
                line = ", ".join(f"{k}={v}" for k, v in row.items() if v is not None)
                pdf.multi_cell(0, 5, f"  - {line}", new_x="LMARGIN", new_y="NEXT")
        elif isinstance(value, dict):
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 5, f"{key}:", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            for sub_key, sub_value in value.items():
                pdf.multi_cell(0, 5, f"  {sub_key}: {sub_value}", new_x="LMARGIN", new_y="NEXT")
        elif isinstance(value, list):
            pdf.multi_cell(0, 5, f"{key}: {', '.join(str(v) for v in value)}", new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.multi_cell(0, 5, f"{key}: {value}", new_x="LMARGIN", new_y="NEXT")

    traceability = section.get("_traceability")
    if traceability:
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(120, 120, 120)
        pdf.multi_cell(
            0, 4,
            f"Source: {traceability.get('source_module', '')} - {traceability.get('methodology', '')}"
            + (f" ({traceability['record_count']} record(s))" if traceability.get("record_count") is not None else ""),
            new_x="LMARGIN", new_y="NEXT",
        )
        pdf.set_text_color(0, 0, 0)
    pdf.ln(2)


# ----- Daily Brief (Shift Briefing) -----

# The Daily Brief has no persisted `Report`/`Scenario`-style DB row to build from — it's computed
# live on every request (see routers/ai_insights.py's `get_daily_brief`) — so this takes plain
# already-computed values rather than a model instance, unlike `build_pdf_export` above.


def build_daily_brief_pdf(
    *,
    generated_at: Any,
    period_label: str,
    sections: list[dict],
    narrative: str | None,
    disclaimer_text: str,
) -> bytes:
    pdf = _ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 10, "OG-PIOS Daily Operations Intelligence", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(0, 6, f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M UTC')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Period: {period_label}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_text_color(0, 0, 0)

    if narrative:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Narrative Summary", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, narrative, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    for section in sections:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 7, section["title"], new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, section["summary"], new_x="LMARGIN", new_y="NEXT")
        if section.get("items"):
            pdf.set_font("Helvetica", "", 9)
            for item in section["items"]:
                pdf.multi_cell(0, 5, f"- {item}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.multi_cell(0, 5, disclaimer_text, new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())


def _pdf_bar_chart_if_available(pdf: FPDF, sections: dict) -> None:
    """One simple native bar chart, drawn with fpdf2's own rect primitives — no charting
    library. Only rendered when relevant data is actually present in this report."""
    by_field = (sections.get("production_by_scope") or {}).get("by_field")
    alerts_by_severity = (sections.get("alerts") or {}).get("by_severity")

    bars: list[tuple[str, float]] | None = None
    title = ""
    if by_field:
        bars = [(b.get("label", b.get("key", "")), b.get("oil_bopd", 0)) for b in by_field[:8]]
        title = "Oil Production by Field (bopd)"
    elif alerts_by_severity:
        bars = list(alerts_by_severity.items())
        title = "Alerts by Severity"

    if not bars:
        return

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")

    max_value = max((v for _, v in bars), default=0) or 1
    chart_width = 170.0
    bar_height = 6.0
    start_x = pdf.get_x() + 30
    y = pdf.get_y()

    pdf.set_font("Helvetica", "", 8)
    for label, value in bars:
        pdf.set_xy(pdf.l_margin, y)
        pdf.cell(28, bar_height, str(label)[:14], align="R")
        width = (value / max_value) * chart_width if max_value else 0
        pdf.set_fill_color(42, 120, 214)
        pdf.rect(start_x, y, max(width, 0.5), bar_height - 1, style="F")
        pdf.set_xy(start_x + width + 2, y)
        pdf.cell(30, bar_height, f"{value:,.1f}")
        y += bar_height
    pdf.set_y(y + 4)
