"""Symbol-universe loading for ranked market views."""

from pathlib import Path
from io import BytesIO
from urllib.request import Request, urlopen

import pandas as pd

NSE_EQUITY_DIRECTORY_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"

MONEYCONTROL_RANKING_URLS = {
    "Gainers": "https://www.moneycontrol.com/stocks/market-stats/top-gainers-nse/?indexName=NIFTY%20500&id=7",
    "Losers": "https://www.moneycontrol.com/stocks/market-stats/top-losers-nse/?indexName=NIFTY%20500&id=7",
}

MONEYCONTROL_INDEXES = {
    "NIFTY 50": ("NIFTY 50", 9),
    "NIFTY 100": ("NIFTY 100", 10),
    "NIFTY AUTO": ("NIFTY AUTO", 13),
    "NIFTY BANK": ("NIFTY BANK", 23),
    "NIFTY PSU BANK": ("NIFTY PSU BANK", 24),
    "NIFTY IT": ("NIFTY IT", 14),
    "NIFTY METAL": ("NIFTY METAL", 19),
    "NIFTY PHARMA": ("NIFTY PHARMA", 18),
    "NIFTY INFRASTRUCTURE": ("NIFTY INFRASTRUCTURE", 21),
    "NIFTY POWER": ("NIFTY POWER", 22),
    "NIFTY FINANCIAL SERVICES": ("NIFTY FINANCIAL SERVICES", 25),
    "NIFTY OIL AND GAS": ("NIFTY OIL AND GAS", 26),
    "NIFTY TELECOMMUNICATIONS": ("NIFTY TELECOMMUNICATIONS", 27),
    "NIFTY MIDCAP 100": ("NIFTY MIDCAP 100", 11),
    "NIFTY SMALLCAP 100": ("NIFTY SMALLCAP 100", 12),
    "NIFTY MIDSMALL HEALTHCARE": ("NIFTY MIDSMALL HEALTHCARE", 28),
}


def load_constituents(path: Path) -> list[tuple[str, str]]:
    """Load an explicit CSV universe with `symbol` and `exchange` columns."""
    frame = pd.read_csv(path)
    required = {"symbol", "exchange"}
    missing = required - {str(column).strip().lower() for column in frame.columns}
    if missing:
        raise ValueError(f"Constituent CSV is missing columns: {', '.join(sorted(missing))}")
    columns = {str(column).strip().lower(): column for column in frame.columns}
    return [(str(row[columns["symbol"]]).strip().upper(), str(row[columns["exchange"]]).strip().upper()) for _, row in frame.iterrows()]


def load_nse_stock_directory() -> pd.DataFrame:
    """Fetch the current NSE symbol and company-name directory."""
    request = Request(NSE_EQUITY_DIRECTORY_URL, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/csv"})
    with urlopen(request, timeout=15) as response:
        frame = pd.read_csv(BytesIO(response.read()))
    columns = {str(column).strip().upper(): column for column in frame.columns}
    if "SYMBOL" not in columns or "NAME OF COMPANY" not in columns:
        raise ValueError("NSE stock directory returned an unexpected format.")
    return pd.DataFrame(
        {
            "symbol": frame[columns["SYMBOL"]].astype(str).str.strip().str.upper(),
            "name": frame[columns["NAME OF COMPANY"]].astype(str).str.strip(),
        }
    ).drop_duplicates("symbol")


def parse_moneycontrol_rankings(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize the public Moneycontrol top-movers table."""
    required = {"Stock Name", "Price"}
    if not required.issubset(frame.columns):
        missing = required - set(frame.columns)
        raise ValueError(f"Moneycontrol ranking is missing columns: {', '.join(sorted(missing))}")
    result = pd.DataFrame()
    result["Stock"] = frame["Stock Name"].astype(str).str.replace(r"Vol Shocker|52WK [HL]", "", regex=True).str.strip()
    price_text = frame["Price"].astype(str)
    result["Price"] = pd.to_numeric(price_text.str.extract(r"^([\d,]+\.\d{2})")[0].str.replace(",", ""), errors="coerce")
    result["Change %"] = pd.to_numeric(price_text.str.extract(r"\(([-\d.]+)%\)")[0], errors="coerce")
    result = result.dropna(subset=["Price", "Change %"]).reset_index(drop=True)
    result.insert(0, "Rank", range(1, len(result) + 1))
    return result


def load_moneycontrol_rankings(direction: str) -> pd.DataFrame:
    """Fetch the current NIFTY 500 top 50 gainers or losers from Moneycontrol."""
    try:
        url = MONEYCONTROL_RANKING_URLS[direction]
    except KeyError as error:
        raise ValueError("Ranking direction must be Gainers or Losers.") from error
    tables = pd.read_html(url)
    if not tables:
        raise ValueError("Moneycontrol returned no ranking table.")
    return parse_moneycontrol_rankings(tables[0]).head(50)


def load_index_recommendations(index_name: str) -> tuple[pd.DataFrame, str]:
    """Load the top 20 momentum candidates for a supported Indian index."""
    try:
        source_name, source_id = MONEYCONTROL_INDEXES[index_name]
    except KeyError as error:
        raise ValueError(f"Unsupported index: {index_name}") from error
    encoded_name = source_name.replace(" ", "%20")
    url = f"https://www.moneycontrol.com/stocks/market-stats/top-gainers-nse/?indexName={encoded_name}&id={source_id}"
    tables = pd.read_html(url)
    if not tables:
        raise ValueError(f"No ranking table returned for {index_name}.")
    return parse_moneycontrol_rankings(tables[0]).head(20), url