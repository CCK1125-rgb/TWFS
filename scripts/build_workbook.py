import argparse
import json
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


COLORS = {
    "navy": "17324D",
    "teal": "0F766E",
    "pale_blue": "EAF3F8",
    "blue_text": "0000FF",
    "black": "000000",
    "gray": "64748B",
    "light_gray": "F3F6F8",
    "border": "CBD5E1",
    "white": "FFFFFF",
}


def fill(color):
    return PatternFill("solid", fgColor=color)


def thin_border(top=False, bottom=False):
    side = Side(style="thin", color=COLORS["border"])
    return Border(top=side if top else None, bottom=side if bottom else None)


def set_widths(ws, widths):
    for idx, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = max(10, width / 7)


def style_title(ws, title, subtitle, last_col):
    ws.sheet_view.showGridLines = False
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_col)
    ws.cell(1, 1, title)
    ws.cell(1, 1).fill = fill(COLORS["navy"])
    ws.cell(1, 1).font = Font(color=COLORS["white"], bold=True, size=15)
    ws.row_dimensions[1].height = 24

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=last_col)
    ws.cell(2, 1, subtitle)
    ws.cell(2, 1).fill = fill(COLORS["pale_blue"])
    ws.cell(2, 1).font = Font(color=COLORS["black"], italic=True)
    ws.row_dimensions[2].height = 20


def find_row(rows, labels):
    for label in labels:
        for idx, row in enumerate(rows):
            if row[0] == label:
                return idx
    return -1


def is_expense_label(label):
    lower = label.lower()
    return (
        any(token in lower for token in ["cost", "expense", "finance costs", "impairment loss"])
        and "income and expenses" not in lower
        and "income (expenses)" not in lower
        and "expense (income)" not in lower
    )


def is_revenue_label(label):
    lower = label.lower()
    return any(token in lower for token in ["revenue", "interest income", "other income"]) and "expenses" not in lower and "losses" not in lower


def income_value(label, value):
    if value is None:
        return None
    lower = label.lower()
    if "expense (income)" in lower or "tax expense" in lower:
        return -abs(value) if value >= 0 else abs(value)
    if is_expense_label(label):
        return -abs(value)
    if is_revenue_label(label):
        return abs(value)
    return value


def display_label(label):
    replacements = {
        "Net other income (expenses)": "Other operating income (expenses), net",
        "Total non-operating income and expenses": "Total non-operating income (expenses), net",
    }
    return replacements.get(label, label)


def is_key_line(label):
    lower = label.lower()
    if lower.startswith("total interest income") or lower.startswith("total other income"):
        return False
    return lower.startswith(("total", "net operating income", "net increase", "net cash", "cash and cash equivalents at end", "profit (loss)", "basic earnings", "total basic"))


def statement_rows(statement, statement_key):
    if statement_key != "income_statement":
        return [[row["item"], *[row["values"].get(period) for period in statement["periods"]]] for row in statement["rows"]]

    rows = []
    source_labels = [row["item"] for row in statement["rows"]]
    gross_idx = source_labels.index("Gross profit (loss) from operations") if "Gross profit (loss) from operations" in source_labels else -1
    operating_idx = source_labels.index("Net operating income (loss)") if "Net operating income (loss)" in source_labels else -1
    profit_idx = next((idx for idx, label in enumerate(source_labels) if label in {
        "Profit (loss)",
        "Profit (loss), attributable to owners of parent",
        "Profit (loss) from continuing operations",
    }), -1)

    for idx, row in enumerate(statement["rows"]):
        rows.append([display_label(row["item"]), *[income_value(row["item"], row["values"].get(period)) for period in statement["periods"]]])
        if idx == gross_idx:
            rows.append(["Gross profit %", *[None for _ in statement["periods"]]])
        if idx == operating_idx:
            rows.append(["Net operating profit %", *[None for _ in statement["periods"]]])
        if idx == profit_idx:
            rows.append(["Net profit %", *[None for _ in statement["periods"]]])
    return rows


def style_header_row(ws, row, last_col):
    for col in range(1, last_col + 1):
        cell = ws.cell(row, col)
        cell.fill = fill(COLORS["teal"])
        cell.font = Font(color=COLORS["white"], bold=True)
        cell.alignment = Alignment(horizontal="center")


def style_number_row(ws, row, first_col, last_col, number_format):
    for col in range(first_col, last_col + 1):
        cell = ws.cell(row, col)
        cell.font = Font(color=COLORS["blue_text"])
        cell.number_format = number_format
        cell.alignment = Alignment(horizontal="right")


def write_statement(wb, data, sheet_name, statement_key):
    statement = data["statements"][statement_key]
    periods = statement["periods"]
    last_col = len(periods) + 1
    ws = wb.create_sheet(sheet_name)

    style_title(
        ws,
        f"{data['company_code']}.TW {statement['title']}",
        f"{data.get('company_name') or ''} | {data['report_basis']} | Unit: {statement['unit']}",
        last_col,
    )
    set_widths(ws, [330, *[96 for _ in periods]])
    ws.freeze_panes = "B5"

    headers = ["Accounting Title", *periods]
    for col, value in enumerate(headers, start=1):
        ws.cell(4, col, value)
    style_header_row(ws, 4, last_col)

    rows = statement_rows(statement, statement_key)
    for row_idx, row in enumerate(rows, start=5):
        for col_idx, value in enumerate(row, start=1):
            ws.cell(row_idx, col_idx, value)
        ws.cell(row_idx, 1).alignment = Alignment(wrap_text=True)
        style_number_row(ws, row_idx, 2, last_col, "#,##0;[Red](#,##0);-")
        if is_key_line(row[0]):
            for col in range(1, last_col + 1):
                cell = ws.cell(row_idx, col)
                cell.fill = fill(COLORS["light_gray"] if row[0].startswith("Total") or row[0].startswith("Net operating income") else COLORS["white"])
                cell.font = Font(bold=True, color=COLORS["blue_text"] if col > 1 else COLORS["black"])
                cell.border = thin_border(top=True)
            style_number_row(ws, row_idx, 2, last_col, "0.00;[Red](0.00);-" if "per share" in row[0].lower() else "#,##0;[Red](#,##0);-")

    if statement_key == "income_statement":
        apply_margin_rows(ws, rows, periods, last_col)

    note_row = len(rows) + 7
    ws.merge_cells(start_row=note_row, start_column=1, end_row=note_row + 1, end_column=last_col)
    ws.cell(note_row, 1, f"Source: {data['source_name']}. Data downloaded {data['as_of_utc']}.")
    ws.cell(note_row, 1).fill = fill(COLORS["pale_blue"])
    ws.cell(note_row, 1).font = Font(color=COLORS["gray"])
    ws.cell(note_row, 1).alignment = Alignment(wrap_text=True)


def apply_margin_rows(ws, rows, periods, last_col):
    revenue_row = find_row(rows, ["Total operating revenue"]) + 5
    if revenue_row < 5:
        return
    margin_rows = [
        ("Gross profit %", ["Gross profit (loss) from operations"]),
        ("Net operating profit %", ["Net operating income (loss)"]),
        ("Net profit %", ["Profit (loss)", "Profit (loss), attributable to owners of parent", "Profit (loss) from continuing operations"]),
    ]
    for label, source_labels in margin_rows:
        margin_row = find_row(rows, [label]) + 5
        source_row = find_row(rows, source_labels) + 5
        if margin_row < 5 or source_row < 5:
            continue
        for idx, _period in enumerate(periods, start=2):
            col = get_column_letter(idx)
            cell = ws.cell(margin_row, idx)
            cell.value = f'=IFERROR({col}{source_row}/{col}{revenue_row},"")'
            cell.font = Font(bold=True, color=COLORS["blue_text"])
            cell.number_format = "0.0%;[Red](0.0%);-"
            cell.alignment = Alignment(horizontal="right")
        for col in range(1, last_col + 1):
            cell = ws.cell(margin_row, col)
            cell.fill = fill(COLORS["pale_blue"])
            cell.border = thin_border(top=True)
            if col == 1:
                cell.font = Font(bold=True, color=COLORS["black"])


def write_summary(wb, data):
    periods = data["statements"]["balance_sheet"]["periods"]
    last_col = len(periods) + 2
    cagr_col = get_column_letter(last_col)
    ws = wb.active
    ws.title = "Summary"

    style_title(
        ws,
        f"{data['company_code']}.TW Financial Statements",
        f"{data.get('company_name') or 'Taiwan listed company'} | Annual statements | {periods[0]}-{periods[-1]}",
        last_col,
    )
    set_widths(ws, [260, *[96 for _ in periods], 118])
    ws.freeze_panes = "A5"

    headers = ["Metric", *periods, f"{periods[0]}-{periods[-1]} CAGR"]
    for col, value in enumerate(headers, start=1):
        ws.cell(4, col, value)
    style_header_row(ws, 4, last_col)

    rows = [
        ("Total operating revenue", "Income Statement", "Total operating revenue", "#,##0;[Red](#,##0);-"),
        ("Gross profit", "Income Statement", "Gross profit (loss) from operations", "#,##0;[Red](#,##0);-"),
        ("Operating income", "Income Statement", "Net operating income (loss)", "#,##0;[Red](#,##0);-"),
        ("Net income to parent", "Income Statement", "Profit (loss), attributable to owners of parent", "#,##0;[Red](#,##0);-"),
        ("EPS", "Income Statement", "Total basic earnings per share", "0.00;[Red](0.00);-"),
        ("Total assets", "Balance Sheet", "Total assets", "#,##0;[Red](#,##0);-"),
        ("Total liabilities", "Balance Sheet", "Total liabilities", "#,##0;[Red](#,##0);-"),
        ("Total equity", "Balance Sheet", "Total equity", "#,##0;[Red](#,##0);-"),
        ("Cash and equivalents", "Balance Sheet", "Cash and cash equivalents", "#,##0;[Red](#,##0);-"),
        ("Operating cash flow", "Cash Flow", "Net cash flows from (used in) operating activities", "#,##0;[Red](#,##0);-"),
        ("Investing cash flow", "Cash Flow", "Net cash flows from (used in) investing activities", "#,##0;[Red](#,##0);-"),
        ("Financing cash flow", "Cash Flow", "Net cash flows from (used in) financing activities", "#,##0;[Red](#,##0);-"),
    ]
    last_value_col = get_column_letter(1 + len(periods))
    years = max(1, len(periods) - 1)
    for row_idx, (label, source_sheet, lookup_label, number_format) in enumerate(rows, start=5):
        ws.cell(row_idx, 1, label)
        ws.cell(row_idx, 1).alignment = Alignment(wrap_text=True)
        for period_idx, _period in enumerate(periods, start=2):
            col = get_column_letter(period_idx)
            ws.cell(row_idx, period_idx, f'=INDEX(\'{source_sheet}\'!$B$5:${last_value_col}$180,MATCH("{lookup_label}",\'{source_sheet}\'!$A$5:$A$180,0),MATCH({col}$4,\'{source_sheet}\'!$B$4:${last_value_col}$4,0))')
            ws.cell(row_idx, period_idx).number_format = number_format
            ws.cell(row_idx, period_idx).font = Font(color=COLORS["blue_text"])
            ws.cell(row_idx, period_idx).alignment = Alignment(horizontal="right")
        ws.cell(row_idx, last_col, f'=IF(OR(B{row_idx}="",{last_value_col}{row_idx}="",B{row_idx}<=0,{last_value_col}{row_idx}<=0),"",({last_value_col}{row_idx}/B{row_idx})^(1/{years})-1)')
        ws.cell(row_idx, last_col).number_format = "0.0%;[Red](0.0%);-"
        ws.cell(row_idx, last_col).alignment = Alignment(horizontal="right")
        for col in range(1, last_col + 1):
            ws.cell(row_idx, col).border = thin_border(bottom=True)

    note_start = len(rows) + 8
    ws.merge_cells(start_row=note_start, start_column=1, end_row=note_start, end_column=last_col)
    ws.cell(note_start, 1, "Source and conventions")
    ws.cell(note_start, 1).fill = fill(COLORS["navy"])
    ws.cell(note_start, 1).font = Font(color=COLORS["white"], bold=True)
    notes = [
        f"Source: {data['source_name']} English eMOPS single-company statement pages.",
        "Amounts are in NT$ thousand except EPS. Blue numbers are source inputs; summary values are formulas linked to statement tabs.",
        f"Generated from MOPS data downloaded {data['as_of_utc']}.",
        f"Report basis: {data['report_basis']}.",
    ]
    for idx, note in enumerate(notes, start=note_start + 1):
        ws.merge_cells(start_row=idx, start_column=1, end_row=idx, end_column=last_col)
        ws.cell(idx, 1, note)
        ws.cell(idx, 1).fill = fill(COLORS["pale_blue"])
        ws.cell(idx, 1).alignment = Alignment(wrap_text=True)


def write_sources(wb, data):
    periods = data["statements"]["balance_sheet"]["periods"]
    ws = wb.create_sheet("Sources")
    style_title(ws, "Sources", "eMOPS source URLs used in this workbook", 4)
    set_widths(ws, [170, 90, 210, 680])
    for col, value in enumerate(["Statement", "Year", "Source", "URL"], start=1):
        ws.cell(4, col, value)
    style_header_row(ws, 4, 4)

    row_idx = 5
    for statement in data["statements"].values():
        for period in periods:
            ws.cell(row_idx, 1, statement["title"])
            ws.cell(row_idx, 2, period)
            ws.cell(row_idx, 3, data["source_name"])
            ws.cell(row_idx, 4, statement["source_urls"].get(period, ""))
            ws.cell(row_idx, 4).alignment = Alignment(wrap_text=True)
            row_idx += 1
    ws.freeze_panes = "A5"


def build_workbook(input_path, output_path):
    with open(input_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    wb = Workbook()
    write_summary(wb, data)
    write_statement(wb, data, "Income Statement", "income_statement")
    write_statement(wb, data, "Balance Sheet", "balance_sheet")
    write_statement(wb, data, "Cash Flow", "cash_flow")
    write_sources(wb, data)
    wb.save(output_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    build_workbook(args.input, args.output)
    print(args.output)


if __name__ == "__main__":
    main()
