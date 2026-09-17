"""Public IPO snapshot retrieval and transparent screening."""

from __future__ import annotations

from datetime import date
import re

import pandas as pd
import requests

IPO_SOURCE_URL = "https://www.iposcanner.ai/"


def _numeric(value: object) -> float | None:
    """Extract a numeric value from a public IPO cell."""
    text = str(value).replace(",", "")
    number = pd.to_numeric(text.replace("₹", "").replace("Cr", "").replace("x", "").strip(), errors="coerce")
    return float(number) if pd.notna(number) else None


def _research_signal(subscription: object, listing_gain: object) -> str:
    """Classify public demand and listing data as a research prompt."""
    subscription_value = _numeric(subscription)
    listing_gain_value = _numeric(listing_gain)
    if (subscription_value is not None and subscription_value >= 5) or (
        listing_gain_value is not None and listing_gain_value >= 10
    ):
        return "Subscribe / strong demand"
    if (subscription_value is not None and subscription_value >= 1) or (
        listing_gain_value is not None and listing_gain_value >= 0
    ):
        return "Review / moderate demand"
    return "Avoid / weak demand"


def _extract_iposcanner_rows(page: str) -> list[dict[str, object]]:
    """Extract IPO records embedded in IPOScanner's Next.js page payload."""
    rows: list[dict[str, object]] = []
    company_pattern = re.compile(r'\\"company\\":\\"(?P<company>.*?)\\"')

    for match_index, company_match in enumerate(company_pattern.finditer(page)):
        start = company_match.start()
        next_match = company_pattern.search(page, company_match.end())
        record = page[start : next_match.start() if next_match else start + 2500]

        def field(pattern: str, default: str = "") -> str:
            value_match = re.search(pattern, record)
            value = value_match.group(1) if value_match else default
            return default if value in {"null", "None"} else value

        price_low = field(r'\\"offerPriceRange\\":\[(.*?),(.*?)\]', "")
        price_match = re.search(r'\\"offerPriceRange\\":\[(.*?),(.*?)\]', record)
        price = f"₹ {price_match.group(1)} - ₹ {price_match.group(2)}" if price_match else ""
        premium = field(r'\\"expectedPremium\\":\{.*?\\"percent\\":(.*?)[,}]', "")
        subscription = field(r'\\"subscribedTimes\\":(.*?)[,}]', "")
        if not price_low or not field(r'\\"offerStart\\":\\"(.*?)\\"'):
            continue
        rows.append(
            {
                "Company": company_match.group("company"),
                "Type": field(r'\\"category\\":\\"(.*?)\\"', field(r'\\"segment\\":\\"(.*?)\\"')),
                "Open / listing date": field(r'\\"offerStart\\":\\"(.*?)\\"'),
                "Close date": field(r'\\"offerEnd\\":\\"(.*?)\\"'),
                "Issue price": price,
                "Subscription": f"{subscription}x" if subscription else "",
                "Listing gain": f"{premium}%" if premium else "",
                "Issue size": field(r'\\"issueSize\\":(.*?)[,}]'),
                "Source section": "IPOScanner live IPO feed",
                "Research signal": _research_signal(subscription, premium),
            }
        )
    return rows


def parse_ipo_snapshot(tables: list[pd.DataFrame], today: date | None = None) -> pd.DataFrame:
    """Normalize public IPO listing and subscription tables into one research view."""
    current_date = today or date.today()
    rows: list[dict[str, object]] = []
    for table_index, table in enumerate(tables):
        company_column = next((column for column in ("Company Name", "IPO Name", "Company") if column in table.columns), None)
        if company_column is None:
            continue
        for _, record in table.iterrows():
            name = str(record.get(company_column, "")).strip()
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
                    "Research signal": _research_signal(total_subscription, listing_gain),
                }
            )
    result = pd.DataFrame(rows)
    if result.empty:
        raise ValueError("The public IPO source returned no named IPO rows.")
    result["Listing sort date"] = pd.to_datetime(
        result["Open / listing date"].str.extract(r"(\d{1,2}\s*-\s*\d{1,2}\s+[A-Za-z]{3}|\d{1,2}\s+[A-Za-z]{3}\s+\d{2,4})", expand=False),
        errors="coerce",
        dayfirst=True,
        format="mixed",
    )
    return (
        result.sort_values("Listing sort date", ascending=False, na_position="last")
        .drop(columns=["Listing sort date"])
        .drop_duplicates(subset=["Company"])
        .reset_index(drop=True)
    )


def load_ipo_snapshot() -> pd.DataFrame:
    """Load public ongoing, upcoming, and recently listed IPO rows."""
    response = requests.get(
        IPO_SOURCE_URL,
        headers={"User-Agent": "Mozilla/5.0 (compatible; StockMarketAnalyzer/1.0)"},
        timeout=20,
    )
    response.raise_for_status()
    rows = _extract_iposcanner_rows(response.text)
    if not rows:
        raise ValueError("IPOScanner returned no named IPO rows.")
    result = pd.DataFrame(rows)
    result["Listing sort date"] = pd.to_datetime(result["Open / listing date"], errors="coerce")
    return (
        result.sort_values("Listing sort date", ascending=False, na_position="last")
        .drop(columns=["Listing sort date"])
        .drop_duplicates(subset=["Company"])
        .reset_index(drop=True)
    )
