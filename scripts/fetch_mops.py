import argparse
import json
import math
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser


sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://emops.twse.com.tw/server-java"
RATE_LIMIT_MARKERS = ["\u67e5\u8a62\u904e\u91cf", "\u8acb\u7a0d\u5f8c\u518d\u67e5\u8a62", "too many"]
STATEMENTS = {
    "balance_sheet": {
        "endpoint": "t164sb03_e",
        "title": "Balance Sheet",
        "period_suffix": "/12/31",
    },
    "income_statement": {
        "endpoint": "t164sb04_e",
        "title": "Income Statement",
        "period_suffix": "/4th",
    },
    "cash_flow": {
        "endpoint": "t164sb05_e",
        "title": "Statements of Cash Flows",
        "period_suffix": "/4th",
    },
}


def clean_label(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\u3000", " ")).strip()


def to_number(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if text in {"", "-", "nan", "NaN"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def fetch_html(company_code, endpoint, year, report_basis):
    url = (
        f"{BASE}/{endpoint}?TYPEK=sii&step=show&co_id={company_code}"
        f"&year={year}&season=4&report_id={report_basis}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read()
    return raw.decode("big5", "ignore"), url


class HtmlTableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.stack = []
        self.current_cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.stack.append({"rows": [], "row": None})
        elif tag == "tr" and self.stack:
            self.stack[-1]["row"] = []
        elif tag in {"td", "th"} and self.stack and self.stack[-1]["row"] is not None:
            self.current_cell = ""

    def handle_data(self, data):
        if self.current_cell is not None:
            self.current_cell += data

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.stack and self.current_cell is not None:
            self.stack[-1]["row"].append(clean_label(self.current_cell))
            self.current_cell = None
        elif tag == "tr" and self.stack:
            row = self.stack[-1]["row"]
            if row and any(clean_label(cell) for cell in row):
                self.stack[-1]["rows"].append(row)
            self.stack[-1]["row"] = None
        elif tag == "table" and self.stack:
            table = self.stack.pop()
            if table["rows"]:
                self.tables.append(table["rows"])


class SimpleTable:
    def __init__(self, rows):
        self.rows = rows
        self.columns = rows[0] if rows else []
        self.data_rows = rows[1:] if rows else []

    def all_text(self):
        return " ".join(clean_label(value) for row in self.rows for value in row)

    def first_column_head_text(self, limit=12):
        return " ".join(clean_label(row[0]) for row in self.data_rows[:limit] if row)

    def iter_records(self):
        for row in self.data_rows:
            yield {column: row[idx] if idx < len(row) else "" for idx, column in enumerate(self.columns)}


def parse_html_tables(html):
    parser = HtmlTableParser()
    parser.feed(html)
    return [SimpleTable(rows) for rows in parser.tables if rows]


def parse_company_name(tables):
    for table in tables[:2]:
        text = table.all_text()
        match = re.search(r"Provided by:\s*([^\.]+(?:\.[^F]+)?)\s+Finacial year", text)
        if match:
            return clean_label(match.group(1))
    return ""


def read_html_tables(html, cfg, company_code, year):
    tables = parse_html_tables(html)
    if tables:
        return tables
    raise RuntimeError(f"Could not read {cfg['title']} table for {company_code} in {year}: no HTML tables found.")


def select_statement_table(tables, cfg, year):
    period_token = f"{year}{cfg['period_suffix']}"
    candidates = []
    for table in tables:
        if len(table.columns) < 2:
            continue
        columns_text = " ".join(table.columns)
        first_col_text = table.first_column_head_text()
        if period_token in columns_text:
            return table
        if cfg["title"] in columns_text or cfg["title"] in first_col_text:
            candidates.append(table)
    if candidates:
        return candidates[-1]
    return None


def fetch_statement_table(company_code, cfg, year, report_basis):
    last_error = None
    retry_delays = [3, 6, 12, 20]
    for attempt in range(5):
        try:
            html, url = fetch_html(company_code, cfg["endpoint"], year, report_basis)
            if any(marker.lower() in html.lower() for marker in RATE_LIMIT_MARKERS):
                raise RuntimeError("MOPS rate limit reached. Waiting before retry.")
            if "No data" in html:
                raise RuntimeError(f"No {cfg['title']} data found for {company_code} in {year}.")
            tables = read_html_tables(html, cfg, company_code, year)
            data = select_statement_table(tables, cfg, year)
            if data is None or len(data.columns) < 2:
                raise RuntimeError(f"Could not read {cfg['title']} table for {company_code} in {year}.")
            return data, tables, url
        except Exception as exc:
            last_error = exc
            if attempt < len(retry_delays):
                time.sleep(retry_delays[attempt])
    raise last_error


def parse_statement(company_code, cfg, years, report_basis):
    rows_by_year = {}
    source_urls = {}
    row_order = []
    company_name = ""
    fetched_years = list(range(years[-1], years[0] - 1, -2))

    for fetch_year in fetched_years:
        data, tables, url = fetch_statement_table(company_code, cfg, fetch_year, report_basis)
        if not company_name:
            company_name = parse_company_name(tables)

        label_col = data.columns[0]
        period_cols = {}
        for year in years:
            period_token = f"{year}{cfg['period_suffix']}"
            matched_cols = [col for col in data.columns[1:] if period_token in col]
            if matched_cols:
                period_cols[str(year)] = matched_cols[0]
                source_urls[str(year)] = url
        if not period_cols:
            raise RuntimeError(f"Could not read {cfg['title']} table for {company_code} in {fetch_year}.")

        year_values = {year: rows_by_year.get(year, {}) for year in period_cols}
        for record in data.iter_records():
            label = clean_label(record.get(label_col))
            if not label or label == cfg["title"]:
                continue
            if label not in row_order:
                row_order.append(label)
            for year, value_col in period_cols.items():
                year_values[year][label] = to_number(record.get(value_col))
        rows_by_year.update(year_values)
        time.sleep(1.0)

    missing_years = [str(year) for year in years if str(year) not in rows_by_year]
    if missing_years:
        raise RuntimeError(f"Could not read {cfg['title']} data for {company_code} in {', '.join(missing_years)}.")

    rows = []
    for label in row_order:
        rows.append({"item": label, "values": {str(year): rows_by_year[str(year)].get(label) for year in years}})

    return {
        "title": cfg["title"],
        "unit": "NT$ thousand except EPS",
        "periods": [str(year) for year in years],
        "rows": rows,
        "source_urls": source_urls,
        "company_name": company_name,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--company-code", required=True)
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--report-basis", choices=["A", "B", "C"], default="C")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    years = list(range(args.start_year, args.end_year + 1))
    payload = {
        "company_code": args.company_code,
        "company_name": "",
        "report_basis": f"{args.report_basis} annual financial statements, season 4",
        "as_of_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_name": "eMOPS / Taiwan Market Observation Post System",
        "statements": {},
    }

    for key, cfg in STATEMENTS.items():
        statement = parse_statement(args.company_code, cfg, years, args.report_basis)
        payload["statements"][key] = {k: v for k, v in statement.items() if k != "company_name"}
        if not payload["company_name"] and statement["company_name"]:
            payload["company_name"] = statement["company_name"]

    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(args.output)


if __name__ == "__main__":
    main()
