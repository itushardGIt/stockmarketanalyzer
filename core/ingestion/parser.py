"""CSV/XLSX holdings parser with explicit broker-header normalization."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import pandas as pd
from pydantic import ValidationError

from core.ingestion.schemas import HoldingRow, ParsedHoldings

HEADER_ALIASES: dict[str, str] = {
    "symbol": "symbol",
    "trading symbol": "symbol",
    "tradingsymbol": "symbol",
    "instrument": "symbol",
    "exchange": "exchange",
    "quantity": "quantity",
    "qty": "quantity",
    "quantity available": "quantity",
    "average price": "avg_cost",
    "avg price": "avg_cost",
    "avg. price": "avg_cost",
    "average cost": "avg_cost",
    "avg. cost": "avg_cost",
    "sector": "sector",
}
REQUIRED_COLUMNS = {"symbol", "exchange", "quantity", "avg_cost"}


class UploadParseError(ValueError):
    """Raised when an upload cannot be safely normalized."""


def _normalized_headers(columns: object) -> dict[str, object]:
    """Return a case-insensitive lookup for broker column names."""
    return {str(column).strip().lower(): column for column in columns}


def _read_excel_holdings(payload: BytesIO) -> tuple[pd.DataFrame, bool]:
    """Find the tabular holdings section in a Zerodha workbook."""
    workbook = pd.ExcelFile(payload)
    sheets = workbook.sheet_names
    preferred_sheets = [sheet for sheet in ("Equity", "Combined") if sheet in sheets]
    ordered_sheets = preferred_sheets + [sheet for sheet in sheets if sheet not in preferred_sheets]
    for sheet in ordered_sheets:
        raw = pd.read_excel(workbook, sheet_name=sheet, header=None)
        for header_row, row in raw.iterrows():
            headers = _normalized_headers(row.dropna().tolist())
            if {"symbol", "average price"}.issubset(headers) and (
                "quantity available" in headers or "quantity" in headers
            ):
                frame = raw.iloc[header_row + 1 :].copy()
                frame.columns = raw.iloc[header_row]
                return frame, "exchange" not in headers
    raise UploadParseError("Could not find a holdings table in the Excel workbook.")


def parse_holdings(file: BinaryIO | bytes, filename: str) -> ParsedHoldings:
    """Parse and validate a CSV or XLSX Holdings export."""
    suffix = Path(filename).suffix.lower()
    payload = BytesIO(file) if isinstance(file, bytes) else file
    if suffix == ".csv":
        frame = pd.read_csv(payload)
        uses_default_exchange = False
    elif suffix in {".xlsx", ".xls"}:
        frame, uses_default_exchange = _read_excel_holdings(payload)
    else:
        raise UploadParseError("Supported holdings formats are CSV and XLSX.")

    normalized_headers = _normalized_headers(frame.columns)
    mapped = {
        target: normalized_headers[source]
        for source, target in HEADER_ALIASES.items()
        if source in normalized_headers
    }
    missing = REQUIRED_COLUMNS - mapped.keys()
    if uses_default_exchange and "exchange" in missing:
        frame["exchange"] = "NSE"
        mapped["exchange"] = "exchange"
        missing.remove("exchange")
    if missing:
        raise UploadParseError(f"Missing required holdings columns: {', '.join(sorted(missing))}.")

    selected = frame.rename(columns={source: target for target, source in mapped.items()})
    selected = selected[[*mapped.keys()]].dropna(how="all")
    rows: list[HoldingRow] = []
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    for row_number, record in enumerate(selected.to_dict(orient="records"), start=2):
        try:
            row = HoldingRow.model_validate(record)
        except ValidationError as error:
            errors.append(f"Row {row_number}: {error.errors()[0]['msg']}")
            continue
        identity = (row.exchange, row.symbol)
        if identity in seen:
            errors.append(f"Row {row_number}: duplicate position {row.exchange}:{row.symbol}.")
            continue
        seen.add(identity)
        rows.append(row)
    if errors:
        raise UploadParseError(" ".join(errors))
    if not rows:
        raise UploadParseError("The holdings file contains no data rows.")
    return ParsedHoldings(rows=rows, source_filename=filename)