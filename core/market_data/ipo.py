"""Public IPO snapshot retrieval and transparent screening."""

from __future__ import annotations

from datetime import date

import pandas as pd

IPO_SOURCE_URL = "https://www.moneycontrol.com/ipo/ipo-snapshot/"


def _numeric(value: object) -> float | None:
    """Extract a numeric value from a public IPO cell."""
    text = str(value).replace(",", "")
    number = pd.to_numeric(text.replace("₹", "").replace("Cr", "").replace("x", "").strip(), errors="coerce")
    return float(number) if pd.notna(number) else None


def parse_ipo_snapshot(tables: list[pd.DataFrame], today: date | None = None) -> pd.DataFrame:
    """Normalize public IPO listing and subscription tables into one research view."""
    current_date = today or date.today()
    rows: list[dict[str, object]] = []
    for table_index, table in enumerate(tables):
        if "Company Name" not in table.columns:
            continue
        for _, record in table.iterrows():
            name = str(record.get("Company Name", "")).strip()
            if not name or name.lower() == "nan":
                continue
            open_date = str(record.get("Open Date", record.get("Listing Date", ""))).strip()
            close_date = str(record.get("Close Date", "")).strip()
            total_subscription = record.get("Total Subscription", record.get("Total", ""))
            listing_gain = record.get("Listing Gain", "")
            rows.append(
                {
                    "Company": name,
                    "Type": str(record.get("Unnamed: 1", "")),
                    "Open / listing date": open_date,
                    "Close date": close_date,
                    "Issue price": str(record.get("Issue Price", "")),
                    "Subscription": str(total_subscription),
                    "Listing gain": str(listing_gain),
                    "Issue size": str(record.get("Issue Size", "")),
                    "Source section": "Listing / subscription",
                    "Research signal": "Review prospectus and valuation",
                }
            )
    result = pd.DataFrame(rows)
    if result.empty:
        raise ValueError("The public IPO source returned no named IPO rows.")
    return result.drop_duplicates(subset=["Company"]).reset_index(drop=True)


def load_ipo_snapshot() -> pd.DataFrame:
    """Load public ongoing, upcoming, and recently listed IPO rows."""
    tables = pd.read_html(IPO_SOURCE_URL)
    return parse_ipo_snapshot(tables)
