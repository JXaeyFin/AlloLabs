"""
================================================================================
MPT Data-Driven Asset Allocation Model
================================================================================
Author:      Jeffrey Xia
Description: Implements Modern Portfolio Theory (MPT) on a global large-cap
             equity universe using SLSQP optimization to construct:
               1. Maximum Sharpe Ratio (Tangency Portfolio)
               2. Minimum Volatility (Global Minimum Variance Portfolio)

             Both portfolios can be evaluated out of sample against broad
             Canadian, U.S., U.K., and European market benchmarks.

             A Jobson-Korkie significance test is applied to assess whether
             out-of-sample Sharpe ratio outperformance is statistically
             meaningful.

Methodology: SLSQP via scipy.optimize.minimize
Data:        yfinance live prices (training + out-of-sample), pulled up to today
Risk-Free:   2.68% (Canadian 1-Year Treasury, as of model construction)

Dependencies: numpy, pandas, scipy, matplotlib, yfinance
================================================================================
"""

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy.optimize import minimize
from scipy import stats

from wealthgpt_report import create_portfolio_pdf

SCRIPT_DIR = Path(__file__).resolve().parent


def env_float(
    name: str,
    default: float,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    """Read and validate a numeric runtime setting."""
    raw_value = os.getenv(name)
    try:
        value = default if raw_value in (None, "") else float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric, received {raw_value!r}.") from exc
    if not np.isfinite(value):
        raise ValueError(f"{name} must be finite.")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be at most {maximum}.")
    return value


def env_bool(name: str, default: bool) -> bool:
    """Read a strict boolean runtime setting."""
    raw_value = os.getenv(name)
    if raw_value in (None, ""):
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false, received {raw_value!r}.")


def env_ticker_subset(name: str) -> list[str] | None:
    """Read a JSON ticker list, or return None for the full universe."""
    raw_value = os.getenv(name)
    if raw_value in (None, "", "null"):
        return None
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} must contain a JSON list of ticker symbols.") from exc
    if not isinstance(payload, list) or not all(
        isinstance(ticker, str) and ticker.strip() for ticker in payload
    ):
        raise ValueError(f"{name} must contain a JSON list of non-empty ticker symbols.")
    return list(dict.fromkeys(ticker.strip().upper() for ticker in payload))

TERMINAL_BANNER = r"""
 __        __         _ _   _      ____ ____ _____
 \ \      / /__  __ _| | |_| |__  / ___|  _ \_   _|
  \ \ /\ / / _ \/ _` | | __| '_ \| |  _| |_) || |
   \ V  V /  __/ (_| | | |_| | | | |_| |  __/ | |
    \_/\_/ \___|\__,_|_|\__|_| |_|\____|_|    |_|

              AI-assisted allocation research
                    Invest with caution
""".strip("\n")

# =============================================================================
# BLOCK 0: UNIVERSE DEFINITION
# =============================================================================
# Global large-cap research universe in Yahoo Finance ticker format.
# Benchmarks are maintained separately from the optimizable universe.

ASSET_UNIVERSE = [
    
    # ==========================================================
    # 🇺🇸 US CORE (S&P 100 MEGA CAPS)
    # ==========================================================
    "AAPL","ABBV","ABT","ACN","ADBE","AIG","AMD","AMGN","AMT","AMZN",
    "AVGO","AXP","BA","BAC","BK","BKNG","BLK","BMY","BRK-B","C",
    "CAT","CL","CMCSA","COF","COP","COST","CRM","CSCO","CVS","CVX",
    "DHR","DIS","DOW","GE","GILD","GM","GOOG","GOOGL","GS","HD",
    "HON","IBM","INTC","JNJ","JPM","KHC","KO","LIN","LLY","LOW",
    "MA","MCD","META","MET","MMM","MRK","MS","MSFT","NEE","NFLX",
    "NKE","NVDA","ORCL","PEP","PFE","PG","PM","QCOM","RTX","SBUX",
    "SCHW","SO","SPG","T","TGT","TMO","TMUS","TSLA","TXN","UNH",
    "UNP","UPS","USB","V","VZ","WFC","WMT","XOM",

    # ==========================================================
    # 🇺🇸 US GROWTH / NASDAQ EXTENSIONS
    # ==========================================================
    "ABNB","ADI","ADP","ARM","CDW","CRWD","DDOG","FTNT","KLAC","LRCX",
    "MAR","MDB","MELI","MCHP","MDLZ","MPWR","MRVL","MU","NXPI","PANW",
    "PAYX","PDD","PLTR","REGN","ROP","SHOP","SNPS","VRTX","WDAY","ZS",
    "APP","CTSH","GFS","ON","STX","TEAM","AKAM","ANSS",

    # ==========================================================
    # 🇺🇸 US HEALTHCARE / BIOTECH EXTENSION
    # ==========================================================
    "ALNY","BIIB","DXCM","IDXX","INSM","ISRG",

    # ==========================================================
    # 🇺🇸 US CONSUMER / DIGITAL
    # ==========================================================
    "DASH","EBAY","KDP","MNST","ORLY","ROST",

    # ==========================================================
    # 🇺🇸 US INDUSTRIALS / LOGISTICS
    # ==========================================================
    "CPRT","CSX","CTAS","FAST","ODFL","PCAR","VRSK",

    # ==========================================================
    # 🇺🇸 US MEDIA / GAMING
    # ==========================================================
    "CHTR","EA","TTWO","WBD",

    # ==========================================================
    # 🇺🇸 US ENERGY / UTILITIES
    # ==========================================================
    "AEP","BKR","EXC","FANG","XEL",

    # ==========================================================
    # 🇨🇦 CANADA CORE (FINANCIALS / ENERGY / DEFENSIVE)
    # ==========================================================
    "RY.TO","TD.TO","BMO.TO","BNS.TO","NA.TO","CM.TO",
    "ENB.TO","TRP.TO","SU.TO","CNQ.TO","CVE.TO","TOU.TO",
    "POW.TO","SLF.TO","MFC.TO","FFH.TO",
    "BAM.TO","BN.TO","BIP-UN.TO",
    "FTS.TO","EMA.TO","PPL.TO",
    "TRI.TO","OTEX.TO","CSU.TO",
    "WCN.TO","WSP.TO","CNR.TO","CP.TO",
    "ATD.TO","DOL.TO","QSR.TO","MRU.TO",
    "SHOP.TO","GIB-A.TO","WN.TO",
    "WPM.TO","FNV.TO","AEM.TO","ABX.TO",
    "TECK-B.TO","NTR.TO","FM.TO",
    "CCO.TO","BCE.TO","T.TO","RCI-B.TO",

    # ==========================================================
    # 🇬🇧 LONDON STOCK EXCHANGE (FTSE 100 — GLOBAL DRIVERS ONLY)
    # NOTE: no global duplicates (avoid adding Shell/HSBC overlap issues)
    # ==========================================================
    "AZN.L","ULVR.L","SHEL.L","BP.L","HSBA.L",
    "GSK.L","RIO.L","BATS.L","DGE.L","GLEN.L",
    "AAL.L","LSEG.L","NG.L","VOD.L","REL.L",
    "CPG.L","SMIN.L","IMB.L","CRH.L","SN.L",

    # ==========================================================
    # 🇪🇺 EURONEXT 100 (EUROPEAN LARGE CAP EXPOSURE)
    # NOTE: filtered to avoid duplication with US listings where possible
    # ==========================================================
    "ASML.AS","SAP.DE","SIE.DE","AIR.PA","OR.PA",
    "MC.PA","SAN.PA","BNP.PA","ENGI.PA","AI.PA",
    "RMS.PA","KER.PA","DG.PA","ENEL.MI","ISP.MI",
    "ENI.MI","STLA.MI","ABI.BR","DSY.PA","HO.PA",
    "PHIA.AS","AD.AS","ZURN.SW","NESN.SW","NOVN.SW",
    "ROG.SW","UBSG.SW","CS.PA"
]
# Benchmarks & tracker funds: keep the TSX ETF, add broad-market trackers
# including S&P 500, Nasdaq-100, an LSE FTSE tracker, and the Euro Stoxx index.
# Note: users can customise this list to specific ETF tickers if desired.
BENCHMARK_TICKERS = ["XIU.TO", "SPY", "QQQ", "ISF.L", "^STOXX50E"]

# =============================================================================
# BLOCK 1: DATE WINDOW CONFIGURATION
# =============================================================================
# USER-FACING KNOBS
training_years = env_float(
    "WEALTHGPT_TRAINING_YEARS", 1.0, minimum=0.25, maximum=10.0
)
oos_years = env_float(
    "WEALTHGPT_OOS_YEARS", 0.5, minimum=0.0, maximum=5.0
)
# Set OOS to 0 to skip the chart and Jobson-Korkie test.
# ─────────────────────────────────────────────────────────────────────────────

today = pd.Timestamp.today().normalize()

if oos_years == 0:
    # No OOS: training runs right up to yesterday
    training_end   = today - pd.Timedelta(days=1)
    oos_start      = None
    oos_end        = None
else:
    # OOS window ends yesterday; starts oos_years back from there
    oos_end        = today - pd.Timedelta(days=1)
    oos_start      = oos_end - pd.DateOffset(months=int(round(oos_years * 12))) \
                     + pd.Timedelta(days=1)
    training_end   = oos_start - pd.Timedelta(days=1)

training_start = training_end \
                 - pd.DateOffset(months=int(round(training_years * 12))) \
                 + pd.Timedelta(days=1)

print(TERMINAL_BANNER)
print()
print(f"Training window : {training_start.date()} -> {training_end.date()}  ({training_years} yr)")
if oos_years == 0:
    print("Out-of-sample   : DISABLED  (oos_years = 0)")
else:
    print(f"Out-of-sample   : {oos_start.date()} -> {oos_end.date()}  ({oos_years} yr)")

# =============================================================================
# BLOCK 2: YFINANCE DATA INGESTION - TRAINING
# =============================================================================
print("\nDownloading training prices from yfinance...")

raw_train = yf.download(
    ASSET_UNIVERSE,
    start=training_start,
    end=training_end + pd.Timedelta(days=1),   # yfinance end is exclusive
    progress=False,
    auto_adjust=True,
)["Close"]

# Replace isolated missing prices with the most recent available quote.
raw_train = raw_train.sort_index().ffill()

# Retain assets with sufficient coverage, then align all return observations.
minimum_price_observations = max(21, int(len(raw_train) * 0.80))
raw_train = raw_train.dropna(axis=1, how="all")
raw_train = raw_train.loc[
    :, raw_train.notna().sum(axis=0) >= minimum_price_observations
]

# Compute daily returns; drop rows with no valid returns on any day
train_returns = raw_train.pct_change(fill_method=None).dropna(how="any")

# Remove any ticker whose returns are entirely missing
train_returns = train_returns.dropna(axis=1, how="all")

# Remove XIU if it crept in (benchmark, not an investable asset here)
train_returns = train_returns[[c for c in train_returns.columns if "XIU" not in c]]

tickers    = train_returns.columns.tolist()
num_assets = len(tickers)

if num_assets < 2:
    raise RuntimeError("Training data contains fewer than two usable assets.")
if len(train_returns) < 20:
    raise RuntimeError("Training data contains fewer than 20 complete return observations.")

print(f"Clean training universe: {num_assets} assets across "
      f"{len(train_returns)} trading days.")

# =============================================================================
# BLOCK 3: STATISTICAL FOUNDATIONS
# =============================================================================
mu    = train_returns.mean() * 252          # annualised expected return
Sigma = train_returns.cov()  * 252          # annualised covariance matrix

mu_values    = mu.values
Sigma_values = Sigma.values

risk_free_rate = 0.0268   # Canadian 1-Year Treasury

# =============================================================================
# BLACK-LITTERMAN + GPT CONFIGURATION
# =============================================================================
black_litterman_tau = 0.05
black_litterman_delta = 2.5

# Provide your API key through the OPENAI_API_KEY environment variable.
gpt_api_key = os.getenv("OPENAI_API_KEY", None)
gpt_model = "gpt-5.4"
gpt_batch_size = 12
gpt_max_output_tokens = 7000
gpt_request_attempts = 3
gpt_refresh_cache = env_bool("WEALTHGPT_REFRESH_CACHE", False)

# When set to True, the script will query GPT-5.4 for each stock and use those views
# to compute posterior returns via Black-Litterman. This may be slow and requires a valid key.
gpt_black_litterman = env_bool("WEALTHGPT_GPT_VIEWS", False)

# If you want the model to generate research on a subset rather than all tickers,
# set this to a list of tickers like ["AEM.TO", "BCE.TO"]. Otherwise leave as None.
black_litterman_ticker_subset = env_ticker_subset(
    "WEALTHGPT_RESEARCH_TICKERS"
)

BL_CACHE_PATH = SCRIPT_DIR / "black_litterman_stock_analysis.json"
GPT_VIEWS_CSV_PATH = SCRIPT_DIR / "gpt_views.csv"
PORTFOLIO_REPORT_PATH = SCRIPT_DIR / "wealthgpt_portfolio_report.pdf"

# =============================================================================
# BLOCK 4: OBJECTIVE FUNCTIONS
# =============================================================================

def portfolio_performance(
    weights: np.ndarray,
    mu: np.ndarray,
    Sigma: np.ndarray,
    rf: float,
) -> Tuple[float, float, float]:
    """Annualised return, volatility, and Sharpe ratio for a weight vector."""
    ret  = float(np.dot(weights, mu))
    variance = float(np.dot(weights.T, np.dot(Sigma, weights)))
    if variance < -1e-10:
        raise ValueError(f"Portfolio variance is negative ({variance:.3e}).")
    risk = float(np.sqrt(max(variance, 0.0)))
    sharpe = (ret - rf) / risk if risk > 0 else 0.0
    return ret, risk, sharpe


def extract_response_text(response_json: dict) -> str:
    if response_json.get("error"):
        raise RuntimeError(f"OpenAI response error: {response_json['error']}")

    status = response_json.get("status")
    if status and status != "completed":
        details = response_json.get("incomplete_details") or status
        raise RuntimeError(f"OpenAI response was not completed: {details}")

    if "output" in response_json:
        texts = []
        refusals = []
        for item in response_json["output"]:
            content = item.get("content")
            if isinstance(content, list):
                for chunk in content:
                    if isinstance(chunk, dict) and chunk.get("type") == "output_text":
                        texts.append(chunk.get("text", ""))
                    elif isinstance(chunk, dict) and chunk.get("type") == "refusal":
                        refusals.append(chunk.get("refusal", "Request refused"))
                    elif isinstance(chunk, str):
                        texts.append(chunk)
            elif isinstance(content, str):
                texts.append(content)
        if refusals:
            raise RuntimeError(f"OpenAI request refused: {'; '.join(refusals)}")
        text = "\n".join(texts).strip()
        if not text:
            raise RuntimeError("OpenAI response contained no output text.")
        return text

    if "choices" in response_json and len(response_json["choices"]) > 0:
        choice = response_json["choices"][0]
        if "message" in choice:
            return choice["message"].get("content", "").strip()
        return choice.get("text", "").strip()

    raise RuntimeError("OpenAI response contained no recognized text output.")


def build_views_schema(tickers_list) -> dict:
    return {
        "type": "object",
        "properties": {
            "views": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "enum": list(tickers_list),
                        },
                        "industry": {"type": "string"},
                        "view": {"type": "string"},
                        "expected_return": {"type": "number"},
                        "confidence": {"type": "number"},
                    },
                    "required": [
                        "ticker",
                        "industry",
                        "view",
                        "expected_return",
                        "confidence",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["views"],
        "additionalProperties": False,
    }


def gpt_5_4_request(
    prompt: str,
    api_key: str,
    tickers_list,
    model: str = "gpt-5.4",
    max_tokens: int = 7000,
    attempts: int = 3,
) -> str:
    if not api_key:
        raise ValueError("GPT API key is required for Black-Litterman research.")

    request_body = json.dumps({
        "model": model,
        "input": prompt,
        "max_output_tokens": max_tokens,
        "store": False,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "tsx_equity_views",
                "description": "One calibrated equity view for every requested ticker.",
                "strict": True,
                "schema": build_views_schema(tickers_list),
            },
        },
    }).encode("utf-8")

    last_error = None
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=request_body,
            headers={
                "Authorization": f"Bearer {api_key.strip()}",
                "Content-Type": "application/json",
                "User-Agent": "tsx-black-litterman/1.0",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=180) as resp:
                return extract_response_text(json.load(resp))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(f"OpenAI request failed ({exc.code}): {detail}")
            if exc.code not in {408, 409, 429, 500, 502, 503, 504}:
                raise last_error from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = RuntimeError(f"OpenAI request failed: {exc}")

        if attempt < attempts:
            delay = min(2 ** (attempt - 1), 8)
            print(f"    OpenAI request attempt {attempt} failed; retrying in {delay}s...")
            time.sleep(delay)

    raise last_error or RuntimeError("OpenAI request failed for an unknown reason.")


def parse_json_from_text(text: str):
    text = re.sub(r"^\s*```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        preview = text[:400].replace("\n", " ")
        raise ValueError(f"OpenAI returned invalid JSON: {preview}") from exc


def validate_view(item, allowed_tickers=None) -> dict:
    if not isinstance(item, dict):
        raise ValueError("View entry is not a JSON object.")

    ticker = str(item.get("ticker", "")).strip().upper()
    if not ticker:
        raise ValueError("View entry is missing a ticker.")
    if allowed_tickers is not None and ticker not in allowed_tickers:
        raise ValueError(f"Unexpected ticker in view output: {ticker}")

    try:
        expected_return = float(item.get("expected_return"))
        confidence = float(item.get("confidence"))
    except (TypeError, ValueError):
        raise ValueError(f"{ticker}: expected_return and confidence must be numeric.")

    if not np.isfinite(expected_return) or not -1.0 <= expected_return <= 1.0:
        raise ValueError(f"{ticker}: expected_return must be between -1.0 and 1.0.")
    if not np.isfinite(confidence) or not 0.01 <= confidence <= 0.99:
        raise ValueError(f"{ticker}: confidence must be between 0.01 and 0.99.")

    industry = str(item.get("industry", "")).strip()
    view = str(item.get("view", "")).strip()
    if not industry or not view:
        raise ValueError(f"{ticker}: industry and view must be non-empty strings.")

    return {
        "ticker": ticker,
        "industry": industry,
        "view": view,
        "expected_return": expected_return,
        "confidence": confidence,
    }


def validate_view_batch(payload, batch) -> list:
    raw_views = payload.get("views") if isinstance(payload, dict) else payload
    if not isinstance(raw_views, list):
        raise ValueError("OpenAI output must contain a 'views' array.")

    allowed = set(batch)
    validated = [validate_view(item, allowed) for item in raw_views]
    returned = [item["ticker"] for item in validated]

    duplicates = sorted({ticker for ticker in returned if returned.count(ticker) > 1})
    missing = sorted(allowed - set(returned))
    if duplicates or missing or len(validated) != len(batch):
        raise ValueError(
            f"Incomplete view batch; missing={missing or 'none'}, "
            f"duplicates={duplicates or 'none'}."
        )

    by_ticker = {item["ticker"]: item for item in validated}
    return [by_ticker[ticker] for ticker in batch]

def fetch_ticker_context(ticker: str, max_news: int = 5) -> dict:
    """
    Pulls fundamental ratios and recent news headlines from yfinance for a ticker.
    Returns a dict with 'ratios' and 'news' keys. Fails silently on missing fields.
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
    except Exception:
        return {"ratios": {}, "news": []}

    ratio_keys = {
        "trailingPE":          "P/E (TTM)",
        "priceToBook":         "P/B",
        "debtToEquity":        "Debt/Equity",
        "returnOnEquity":      "ROE",
        "earningsGrowth":      "EPS Growth (YoY)",
        "enterpriseToEbitda":  "EV/EBITDA",
        "freeCashflow":        "FCF",
        "totalRevenue":        "Revenue",
        "netMargins":          "Net Margin",
        "beta":                "Beta",
        "marketCap":           "Market Cap",
    }

    ratios = {}
    for key, label in ratio_keys.items():
        val = info.get(key)
        if val is not None:
            # Format percentages and large numbers cleanly
            if key in ("returnOnEquity", "netMargins", "earningsGrowth"):
                ratios[label] = f"{val * 100:.1f}%"
            elif key in ("freeCashflow", "totalRevenue", "marketCap"):
                ratios[label] = f"${val / 1e9:.2f}B"
            else:
                ratios[label] = round(val, 2)

    news_items = []
    try:
        raw_news = t.news or []
        for item in raw_news[:max_news]:
            content = item.get("content", {})
            title   = content.get("title", "").strip()
            source  = content.get("provider", {}).get("displayName", "Unknown")
            date    = content.get("pubDate", "")[:10]   # YYYY-MM-DD
            summary = content.get("summary", "").strip()
            if title:
                news_items.append({
                    "title":   title,
                    "source":  source,
                    "date":    date,
                    "summary": summary[:300] if summary else "",
                })
    except Exception:
        pass

    return {"ratios": ratios, "news": news_items}

def generate_gpt_views(
    tickers_list,
    api_key: str,
    model: str = "gpt-5.4",
    batch_size: int = 12,
):
    if not tickers_list:
        return []

    # Pre-fetch context for all tickers
    print("  Fetching fundamentals and news from yfinance...")
    context_map = {}
    for tkr in tickers_list:
        context_map[tkr] = fetch_ticker_context(tkr, max_news=5)
        print(f"    {tkr} - {len(context_map[tkr]['ratios'])} ratios, "
              f"{len(context_map[tkr]['news'])} news items")

    views = []
    for start in range(0, len(tickers_list), batch_size):
        batch = tickers_list[start:start + batch_size]

        # Build per-ticker context block
        ticker_blocks = []
        for tkr in batch:
            ctx   = context_map[tkr]
            lines = [f"### {tkr}"]

            if ctx["ratios"]:
                ratio_str = " | ".join(f"{k}: {v}" for k, v in ctx["ratios"].items())
                lines.append(f"Fundamentals: {ratio_str}")
            else:
                lines.append("Fundamentals: unavailable")

            if ctx["news"]:
                lines.append("Recent news:")
                for n in ctx["news"]:
                    src  = f"[{n['source']}]" if n["source"] != "Unknown" else ""
                    date = f"({n['date']})" if n["date"] else ""
                    lines.append(f"  - {n['title']} {src} {date}".strip())
                    if n["summary"]:
                        lines.append(f"    {n['summary']}")
            else:
                lines.append("Recent news: unavailable")

            ticker_blocks.append("\n".join(lines))

        context_section = "\n\n".join(ticker_blocks)

        print(f"    Sending GPT request for tickers {start + 1}-{start + len(batch)} of {len(tickers_list)}...")

        prompt = f"""You are a senior equity research analyst covering TSX-listed companies.

Your output will be used as alpha inputs in a Black-Litterman portfolio optimization model. Prioritize calibration, realism, and cross-sectional differentiation over persuasive writing.
For each ticker, estimate the most probable 12-month forward total return using the supplied fundamentals, ratios, and news.
Guidelines:
* Think probabilistically (base, bull, bear cases) and report the probability-weighted expected return.
* Expected returns should vary meaningfully across stocks; do not cluster forecasts in a narrow positive range.
* Negative returns are appropriate when risks outweigh upside.
* Strong businesses can have poor expected returns if valuation is demanding.
* Weak businesses can have positive expected returns if risks appear priced in.
* Discuss both upside drivers and downside risks.
* Do not invent facts or catalysts not present in the provided data.
* Confidence measures forecast reliability, not company quality.
* Reduce confidence when signals are sparse, conflicting, or incomplete.
* If both fundamentals and news are largely unavailable, confidence must not exceed 0.55.

Expected Return Scale:
> 0.20 = exceptional upside
> 0.10-0.20 = constructive
> 0.03-0.10 = modestly positive
> -0.03-0.03 = neutral/fairly valued
> -0.10--0.03 = moderate downside
> < -0.10 = material downside

Confidence Scale:
0.90+ = rare, unusually strong evidence
0.80-0.89 = strong conviction
0.70-0.79 = moderate conviction
0.60-0.69 = mixed signals
0.50-0.59 = limited information

Return one view for every requested ticker. The JSON response shape and required
fields are enforced by the API schema.
Requirements for "view":
* 2-3 concise sentences.
* Reference specific metrics, ratios, trends, or news when available.
* Explicitly identify the primary upside driver and primary risk.
TICKER DATA:
{context_section}
Analyze all {len(batch)} tickers and return JSON only.
"""

        batch_error = None
        for validation_attempt in range(1, 3):
            start_time = time.time()
            raw_output = gpt_5_4_request(
                prompt,
                api_key,
                batch,
                model=model,
                max_tokens=max(gpt_max_output_tokens, 450 * len(batch)),
                attempts=gpt_request_attempts,
            )
            elapsed = time.time() - start_time
            print(f"    GPT batch completed in {elapsed:.1f}s; validating response...")

            try:
                batch_views = validate_view_batch(parse_json_from_text(raw_output), batch)
                views.extend(batch_views)
                batch_error = None
                break
            except ValueError as exc:
                batch_error = exc
                if validation_attempt < 2:
                    print(f"    Invalid batch response: {exc} Retrying once...")

        if batch_error is not None:
            raise RuntimeError(f"Could not obtain a complete GPT view batch: {batch_error}")

    return views

def black_litterman_posterior(
    mu_prior: np.ndarray,
    Sigma: np.ndarray,
    tickers_list,
    views,
    tau: float = 0.05,
    delta: float = 2.5,
):
    n_assets = len(tickers_list)
    if mu_prior.shape != (n_assets,) or Sigma.shape != (n_assets, n_assets):
        raise ValueError("Black-Litterman inputs do not match the ticker universe.")
    if tau <= 0 or delta <= 0:
        raise ValueError("Black-Litterman tau and delta must be positive.")
    if not np.all(np.isfinite(mu_prior)) or not np.all(np.isfinite(Sigma)):
        raise ValueError("Black-Litterman inputs contain non-finite values.")

    ticker_index = {ticker: idx for idx, ticker in enumerate(tickers_list)}
    valid_views = []
    seen = set()
    for raw_view in views:
        view = validate_view(raw_view, set(tickers_list))
        if view["ticker"] in seen:
            raise ValueError(f"Duplicate Black-Litterman view for {view['ticker']}.")
        seen.add(view["ticker"])
        valid_views.append(view)

    equal_weight_proxy = np.full(n_assets, 1.0 / n_assets)
    equilibrium_prior = delta * Sigma.dot(equal_weight_proxy)
    posterior = equilibrium_prior.copy()

    if valid_views:
        P = np.zeros((len(valid_views), n_assets))
        Q = np.empty(len(valid_views))
        for row, view in enumerate(valid_views):
            P[row, ticker_index[view["ticker"]]] = 1.0
            Q[row] = view["expected_return"]

        tau_sigma = tau * Sigma
        view_prior_variance = np.diag(P.dot(tau_sigma).dot(P.T))
        confidence = np.array([view["confidence"] for view in valid_views])
        omega_diag = np.maximum(
            1e-10,
            view_prior_variance * (1.0 - confidence) / confidence,
        )
        view_covariance = P.dot(tau_sigma).dot(P.T) + np.diag(omega_diag)
        innovation = Q - P.dot(equilibrium_prior)

        try:
            solved_innovation = np.linalg.solve(view_covariance, innovation)
        except np.linalg.LinAlgError:
            solved_innovation = np.linalg.pinv(view_covariance).dot(innovation)
        posterior = equilibrium_prior + tau_sigma.dot(P.T).dot(solved_innovation)

    views_by_ticker = {view["ticker"]: view for view in valid_views}
    analysis = {}
    for ticker, idx in ticker_index.items():
        view = views_by_ticker.get(ticker, {})
        analysis[ticker] = {
            "ticker": ticker,
            "historical_return": float(mu_prior[idx]),
            "prior_return": float(equilibrium_prior[idx]),
            "posterior_return": float(posterior[idx]),
            "delta_return": float(posterior[idx] - equilibrium_prior[idx]),
            "view": view.get("view", ""),
            "industry": view.get("industry", ""),
            "confidence": view.get("confidence"),
            "expected_return": view.get("expected_return"),
        }

    return posterior, analysis


def load_cached_views(path: Path, allowed_tickers) -> dict:
    if not path.exists():
        return {}

    print(f"Loading cached Black-Litterman views from {path}.")
    try:
        with path.open("r", encoding="utf-8") as fp:
            cached = json.load(fp)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  Cache ignored because it could not be read: {exc}")
        return {}

    if isinstance(cached, dict):
        raw_entries = list(cached.values())
    elif isinstance(cached, list):
        raw_entries = cached
    else:
        print("  Cache ignored because its top-level shape is invalid.")
        return {}

    allowed = set(allowed_tickers)
    valid = {}
    empty_count = 0
    invalid = []
    for raw in raw_entries:
        if not isinstance(raw, dict):
            invalid.append("non-object entry")
            continue
        if raw.get("expected_return") is None or raw.get("confidence") is None:
            empty_count += 1
            continue
        try:
            view = validate_view(raw, allowed)
        except ValueError as exc:
            invalid.append(str(exc))
            continue
        if view["ticker"] in valid:
            invalid.append(f"duplicate view for {view['ticker']}")
            continue
        valid[view["ticker"]] = view

    print(f"  Cache contains {len(valid)} valid GPT views.")
    if empty_count:
        print(f"  {empty_count} entries do not contain a cached GPT view.")
    if invalid:
        print(f"  {len(invalid)} malformed cache entries were skipped.")
        for reason in invalid[:10]:
            print(f"    - {reason}")
    return valid


def write_json_atomic(path: Path, payload) -> None:
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2, ensure_ascii=False)
        fp.write("\n")
    temporary_path.replace(path)


def apply_black_litterman(mu_prior: np.ndarray, Sigma: np.ndarray, tickers_list):
    if not gpt_black_litterman:
        return mu_prior

    # Reuse validated cached views and generate only missing entries.
    selected_tickers = (
        list(black_litterman_ticker_subset)
        if black_litterman_ticker_subset is not None
        else list(tickers_list)
    )
    unknown_tickers = sorted(set(selected_tickers) - set(tickers_list))
    if unknown_tickers:
        raise ValueError(f"Black-Litterman subset contains unknown tickers: {unknown_tickers}")

    cached_views = (
        {} if gpt_refresh_cache else load_cached_views(BL_CACHE_PATH, selected_tickers)
    )
    missing_tickers = [
        ticker for ticker in selected_tickers if ticker not in cached_views
    ]

    if missing_tickers and gpt_api_key:
        print(f"Generating {len(missing_tickers)} missing GPT views...")
        generated = generate_gpt_views(
            missing_tickers,
            gpt_api_key,
            model=gpt_model,
            batch_size=gpt_batch_size,
        )
        cached_views.update({view["ticker"]: view for view in generated})
    elif missing_tickers:
        print(
            f"WARNING: {len(missing_tickers)} requested tickers have no valid cached "
            "view and OPENAI_API_KEY is not set. Continuing with the available views."
        )

    views = [
        cached_views[ticker]
        for ticker in selected_tickers
        if ticker in cached_views
    ]
    if not views:
        raise ValueError(
            "No valid GPT views are available. Set OPENAI_API_KEY or provide a valid cache."
        )
    # ────────────────────────────────────────────────────────────────────────

    mu_bl, analysis = black_litterman_posterior(
        mu_prior, Sigma, tickers_list, views,
        tau=black_litterman_tau,
        delta=black_litterman_delta,
    )

    output = {ticker: analysis.get(ticker, {}) for ticker in tickers_list}
    write_json_atomic(BL_CACHE_PATH, output)
    print(f"Black-Litterman analysis saved -> {BL_CACHE_PATH}")

    if views:
        rows = []
        for v in views:
            tkr  = v["ticker"]
            anal = analysis.get(tkr, {})
            rows.append({
                "ticker":           tkr,
                "industry":         v.get("industry", ""),
                "expected_return":  v.get("expected_return"),
                "confidence":       v.get("confidence"),
                "historical_return": anal.get("historical_return"),
                "prior_return":     anal.get("prior_return"),
                "posterior_return": anal.get("posterior_return"),
                "delta_return":     anal.get("delta_return"),
                "view":             v.get("view", ""),
            })
        pd.DataFrame(rows).sort_values("ticker").to_csv(GPT_VIEWS_CSV_PATH, index=False)
        print(f"GPT views exported -> {GPT_VIEWS_CSV_PATH}")

    return mu_bl


if gpt_black_litterman:
    print("\nApplying GPT-assisted Black-Litterman posterior returns...")
    mu_values = apply_black_litterman(mu_values, Sigma_values, tickers)


def negative_sharpe(weights: np.ndarray, mu: np.ndarray, Sigma: np.ndarray, rf: float) -> float:
    _, _, s = portfolio_performance(weights, mu, Sigma, rf)
    return -s


def portfolio_variance(weights: np.ndarray, Sigma: np.ndarray) -> float:
    variance = float(np.dot(weights.T, np.dot(Sigma, weights)))
    return float(np.sqrt(max(variance, 0.0)))


def validated_optimizer_weights(result, label: str) -> np.ndarray:
    if not result.success:
        raise RuntimeError(f"{label} optimization failed: {result.message}")
    weights = np.asarray(result.x, dtype=float)
    if not np.all(np.isfinite(weights)):
        raise RuntimeError(f"{label} optimization returned non-finite weights.")
    weights[np.abs(weights) < 1e-12] = 0.0
    if np.any(weights < -1e-8):
        raise RuntimeError(f"{label} optimization returned a negative weight.")
    total = float(weights.sum())
    if total <= 0:
        raise RuntimeError(f"{label} optimization returned zero total weight.")
    weights /= total
    if not np.isclose(weights.sum(), 1.0, atol=1e-8):
        raise RuntimeError(f"{label} optimization weights do not sum to one.")
    if np.any(weights > max_position_weight + 1e-7):
        largest = float(weights.max())
        raise RuntimeError(
            f"{label} optimization exceeded the {max_position_weight:.1%} "
            f"position limit with a {largest:.1%} holding."
        )
    return weights


# =============================================================================
# BLOCK 5: CONSTRAINTS AND BOUNDS
# =============================================================================
initial_guess = np.ones(num_assets) / num_assets
constraints   = {"type": "eq", "fun": lambda x: np.sum(x) - 1}
max_position_weight = env_float(
    "WEALTHGPT_MAX_POSITION_WEIGHT", 1.0, minimum=0.01, maximum=1.0
)
if max_position_weight * num_assets < 1.0 - 1e-12:
    raise ValueError(
        f"Maximum position {max_position_weight:.1%} is infeasible for "
        f"{num_assets} usable assets; choose at least {1 / num_assets:.1%}."
    )
bounds = tuple((0.0, max_position_weight) for _ in range(num_assets))

# =============================================================================
# BLOCK 6: SLSQP OPTIMISATION
# =============================================================================
print("\nRunning SLSQP optimisation engines...")

# --- Portfolio 1: Maximum Sharpe Ratio ---
res_sharpe = minimize(
    fun=negative_sharpe,
    x0=initial_guess,
    args=(mu_values, Sigma_values, risk_free_rate),
    method="SLSQP",
    bounds=bounds,
    constraints=constraints,
    tol=1e-9,
    options={"maxiter": 1000},
)
w_sharpe = validated_optimizer_weights(res_sharpe, "Maximum Sharpe")
opt_ret_S, opt_risk_S, opt_sr_S = portfolio_performance(w_sharpe, mu_values, Sigma_values, risk_free_rate)

# --- Portfolio 2: Minimum Volatility ---
res_vol = minimize(
    fun=portfolio_variance,
    x0=initial_guess,
    args=(Sigma_values,),
    method="SLSQP",
    bounds=bounds,
    constraints=constraints,
    tol=1e-9,
    options={"maxiter": 1000},
)
w_vol = validated_optimizer_weights(res_vol, "Minimum volatility")
opt_ret_V, opt_risk_V, opt_sr_V = portfolio_performance(w_vol, mu_values, Sigma_values, risk_free_rate)

# =============================================================================
# BLOCK 7: IN-SAMPLE ALLOCATION TABLE
# =============================================================================
print("\n" + "=" * 78)
# Display configuration: show very small weights with more decimal places
# `WEIGHT_DISPLAY_DECIMALS` controls how many decimals are shown for percent
# `WEIGHT_DISPLAY_THRESHOLD_PCT` is the minimum percent (not fraction) to display
WEIGHT_DISPLAY_DECIMALS = 6
WEIGHT_DISPLAY_THRESHOLD_PCT = 0.0001  # show weights > 0.0001% (very small)

title = f"IN-SAMPLE ASSET ALLOCATIONS  (>{WEIGHT_DISPLAY_THRESHOLD_PCT:.6f}%)"
print(f"{title:^78}")
print("=" * 78)
col_ms_width = 22
col_mv_width = 22
print(f"{'Ticker':<12} | {'Max Sharpe Wgt':>{col_ms_width}} | {'Min Vol Wgt':>{col_mv_width}}")
print("-" * 78)

for i, ticker in enumerate(tickers):
    ws = w_sharpe[i] * 100
    wv = w_vol[i]    * 100
    if ws > WEIGHT_DISPLAY_THRESHOLD_PCT or wv > WEIGHT_DISPLAY_THRESHOLD_PCT:
        ms_str = format(ws, f">{col_ms_width}.{WEIGHT_DISPLAY_DECIMALS}f") + "%"
        mv_str = format(wv, f">{col_mv_width}.{WEIGHT_DISPLAY_DECIMALS}f") + "%"
        print(f"{ticker:<12} | {ms_str} | {mv_str}")

print("-" * 78)
print(f"\nIn-sample Max Sharpe  ->  ret {opt_ret_S*100:.2f}%  "
      f"vol {opt_risk_S*100:.2f}%  Sharpe {opt_sr_S:.3f}")
print(f"In-sample Min Vol     ->  ret {opt_ret_V*100:.2f}%  "
      f"vol {opt_risk_V*100:.2f}%  Sharpe {opt_sr_V:.3f}")

# =============================================================================
# BLOCK 8: YFINANCE DATA INGESTION - OUT-OF-SAMPLE  (skipped if oos_years = 0)
# =============================================================================
if oos_years == 0:
    print("\n[OOS DISABLED]  oos_years = 0 - skipping out-of-sample blocks.")
    master  = None
    cum_ret = None
else:
    print("\n" + "=" * 62)
    print(f"OUT-OF-SAMPLE TESTING  ({oos_years} yr window)")
    print("=" * 62)

    print("Fetching OOS portfolio prices...")
    oos_raw = yf.download(
        tickers,
        start=oos_start,
        end=oos_end + pd.Timedelta(days=1),   # yfinance end is exclusive
        progress=False,
        auto_adjust=True,
    )["Close"]

    print(f"Fetching benchmarks ({', '.join(BENCHMARK_TICKERS)})...")
    bench_raw = yf.download(
        BENCHMARK_TICKERS,
        start=oos_start,
        end=oos_end + pd.Timedelta(days=1),
        progress=False,
        auto_adjust=True,
    )["Close"]

    oos_returns = oos_raw.sort_index().ffill().pct_change(fill_method=None).dropna(how="all")
    bench_returns = (
        bench_raw.sort_index().ffill().pct_change(fill_method=None).dropna(how="all")
    )

    # Survivorship: keep only tickers that exist in the OOS download
    surviving     = [t for t in tickers if t in oos_returns.columns]
    surv_idx      = [tickers.index(t) for t in surviving]
    if not surviving:
        raise RuntimeError("No portfolio tickers have usable out-of-sample data.")

    surv_w_sharpe = w_sharpe[surv_idx]
    surv_w_vol    = w_vol[surv_idx]

    if surv_w_sharpe.sum() <= 0 or surv_w_vol.sum() <= 0:
        raise RuntimeError("Surviving out-of-sample assets have zero portfolio weight.")
    surv_w_sharpe /= surv_w_sharpe.sum()
    surv_w_vol /= surv_w_vol.sum()

    oos_ret_mat     = oos_returns[surviving]
    port_ret_sharpe = oos_ret_mat.dot(surv_w_sharpe)
    port_ret_vol    = oos_ret_mat.dot(surv_w_vol)

    # Map downloaded benchmark tickers to friendly column labels
    BENCHMARK_LABELS = {
        "XIU.TO": "TSX_60",
        "SPY": "S&P_500",
        "QQQ": "Nasdaq_100",
        "ISF.L": "FTSE_100_ETF",
        "^STOXX50E": "STOXX50E",
    }

    master_payload = {
        "Max_Sharpe": port_ret_sharpe,
        "Min_Vol": port_ret_vol,
    }
    # Add only benchmarks that were actually downloaded
    for tkr, label in BENCHMARK_LABELS.items():
        if tkr in bench_returns.columns:
            master_payload[label] = bench_returns[tkr]

    master = pd.DataFrame(master_payload).dropna()
    if master.empty:
        raise RuntimeError("No aligned out-of-sample portfolio and benchmark returns.")

    cum_ret = (1 + master).cumprod() - 1

    # --- Summary metrics ---
    # Compute portfolio summary metrics
    oos_ret_sharpe = master["Max_Sharpe"].add(1).prod() - 1
    oos_ret_vol    = master["Min_Vol"].add(1).prod() - 1

    oos_vol_sharpe = master["Max_Sharpe"].std() * np.sqrt(252)
    oos_vol_vol    = master["Min_Vol"].std()    * np.sqrt(252)

    # Compute per-benchmark total return and annualised vol
    benchmark_oos_rets = {}
    benchmark_oos_vols = {}
    for col in master.columns:
        if col in ("Max_Sharpe", "Min_Vol"):
            continue
        benchmark_oos_rets[col] = master[col].add(1).prod() - 1
        benchmark_oos_vols[col] = master[col].std() * np.sqrt(252)

    print("-" * 62)
    print(f"Test period: {master.index[0].date()} -> {master.index[-1].date()}")
    print(f"Surviving tickers in OOS: {len(surviving)} / {num_assets}")
    print("-" * 62)
    print(f"{'Portfolio / Index':<30} | {'OOS Return':>10} | {'Ann. Vol':>9}")
    print("-" * 62)
    print(f"{'Max Sharpe Portfolio':<30} | {oos_ret_sharpe*100:>9.2f}%  | {oos_vol_sharpe*100:>8.2f}%")
    print(f"{'Min Vol Portfolio':<30} | {oos_ret_vol*100:>9.2f}%  | {oos_vol_vol*100:>8.2f}%")
    # Print benchmark rows
    for label, ret in benchmark_oos_rets.items():
        vol = benchmark_oos_vols.get(label, float('nan'))
        print(f"{label:<30} | {ret*100:>9.2f}%  | {vol*100:>8.2f}%")
    print("-" * 62)
    print("-" * 62)

# =============================================================================
# BLOCK 9: STATISTICAL SIGNIFICANCE - JOBSON-KORKIE (1981)
# =============================================================================

def jobson_korkie_test(
    returns_a: pd.Series,
    returns_b: pd.Series,
    rf: float,
    periods: int = 252,
) -> Tuple[float, float, float, float]:
    """
    Jobson-Korkie (1981) test for equality of two Sharpe ratios.
    Returns: z-statistic, p-value, SR_a, SR_b
    """
    rf_d    = rf / periods
    exc_a   = returns_a - rf_d
    exc_b   = returns_b - rf_d
    n       = len(returns_a)

    sr_a    = exc_a.mean() / exc_a.std() * np.sqrt(periods)
    sr_b    = exc_b.mean() / exc_b.std() * np.sqrt(periods)
    rho     = np.corrcoef(returns_a, returns_b)[0, 1]

    var_jk  = (1 / n) * (
        2 - 2 * rho
        + 0.5 * sr_a**2
        + 0.5 * sr_b**2
        - sr_a * sr_b * rho**2
    )
    z = (sr_a - sr_b) / np.sqrt(max(var_jk, 1e-12))
    p = 2 * (1 - stats.norm.cdf(abs(z)))
    return z, p, sr_a, sr_b


if master is not None:
    print("\n" + "=" * 62)
    print("STATISTICAL SIGNIFICANCE  (Jobson-Korkie 1981)")
    print("=" * 62)

    # Build comparisons dynamically vs all available benchmarks
    comparisons = []
    benchmark_cols = [c for c in master.columns if c not in ("Max_Sharpe", "Min_Vol")]
    for col in benchmark_cols:
        comparisons.append((f"Max Sharpe vs {col}", master["Max_Sharpe"], master[col]))
        comparisons.append((f"Min Vol vs {col}", master["Min_Vol"], master[col]))

    for label, ra, rb in comparisons:
        z, p, sra, srb = jobson_korkie_test(ra, rb, risk_free_rate)
        sig = "SIGNIFICANT" if p < 0.05 else "not significant"
        print(f"\n  {label}")
        print(f"    Sharpe (portfolio): {sra:.3f}  |  Sharpe (benchmark): {srb:.3f}")
        print(f"    Z-statistic: {z:.3f}  |  P-value: {p:.4f}  ({sig} at 95%)")

# =============================================================================
# BLOCK 10: VISUALISATION - EQUITY CURVES  (skipped if oos_years = 0)
# =============================================================================

def annotate_extremes(series_dict: dict, colors_dict: dict) -> None:
    """Annotates global highs and lows with basic collision avoidance."""
    placed: list = []
    x_gap, y_gap = 12, 1.2

    points = []
    for name, s in series_dict.items():
        points.append({"date": s.idxmax(), "val": s.max(), "kind": "Max", "color": colors_dict[name]})
        points.append({"date": s.idxmin(), "val": s.min(), "kind": "Min", "color": colors_dict[name]})
    points.sort(key=lambda p: p["date"])

    for pt in points:
        d, v, k, c = pt["date"], pt["val"], pt["kind"], pt["color"]
        ax.plot(d, v, marker="^" if k == "Max" else "v", color=c,
                markersize=7, markeredgecolor="white", zorder=5)

        ty = v + (y_gap if k == "Max" else -y_gap)
        for _ in range(20):
            if any(abs((d - px).days) < x_gap and abs(ty - py) < y_gap for px, py in placed):
                ty += 0.5 if k == "Max" else -0.5
            else:
                break
        placed.append((d, ty))

        ax.plot([d, d], [v, ty], color=c, linestyle=":", alpha=0.6, linewidth=1.2)
        ax.text(d, ty, f"{k}: {v:.1f}%", color=c, fontsize=8, ha="center", va="center",
                fontweight="bold", zorder=6,
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.85, edgecolor=c))


if cum_ret is None:
    print("\n[CHART SKIPPED]  No out-of-sample data to plot (oos_years = 0).")
    print("Done.")
else:
    print("\nGenerating equity curve chart...")

    # Larger figure to accommodate many benchmark lines and improve readability
    fig, ax = plt.subplots(figsize=(20, 10))

    dates = cum_ret.index
    ret_sharpe = cum_ret["Max_Sharpe"] * 100
    ret_vol = cum_ret["Min_Vol"] * 100

    color_sharpe = "#1f77b4"
    color_vol = "#d62728"

    # Reduce marker density dynamically to avoid clutter on long series
    marker_interval = max(1, len(dates) // 24)
    ax.plot(dates, ret_sharpe, label="Max Sharpe Portfolio", color=color_sharpe,
            linestyle="-", linewidth=3, marker="o", markersize=5, markevery=marker_interval)
    ax.plot(dates, ret_vol, label="Min Volatility Portfolio", color=color_vol,
            linestyle="-", linewidth=3, marker="D", markersize=5, markevery=marker_interval)

    # Plot all available benchmarks (thin, dotted lines)
    benchmark_cols = [c for c in cum_ret.columns if c not in ("Max_Sharpe", "Min_Vol")]
    cmap = plt.get_cmap("tab10")
    bench_colors = {col: cmap(i % 10) for i, col in enumerate(benchmark_cols)}
    for col in benchmark_cols:
        series = cum_ret[col] * 100
        ax.plot(dates, series, label=col, linestyle=":", linewidth=1.5, color=bench_colors[col])

    # Prepare series and color maps for annotation
    series_map = {"Max Sharpe": ret_sharpe, "Min Vol": ret_vol}
    color_map = {"Max Sharpe": color_sharpe, "Min Vol": color_vol}
    for col in benchmark_cols:
        series_map[col] = cum_ret[col] * 100
        color_map[col] = bench_colors[col]

    annotate_extremes(series_map, color_map)

    # Endpoint labels with vertical collision avoidance (portfolios + benchmarks)
    ep_labels = [
        ("Max Sharpe Portfolio", ret_sharpe.iloc[-1], color_sharpe),
        ("Min Volatility Portfolio", ret_vol.iloc[-1], color_vol),
    ]
    for col in benchmark_cols:
        ep_labels.append((col, (cum_ret[col] * 100).iloc[-1], bench_colors[col]))
    placed_y: list = []
    v_gap = 0.8

    for lbl, val, col in ep_labels:
        ty = val
        for _ in range(20):
            if any(abs(ty - ey) < v_gap for ey in placed_y):
                ty += v_gap
            else:
                break
        placed_y.append(ty)
        ax.text(dates[-1], ty, f" {val:.2f}%",
                va="bottom" if ty >= val else "top", fontsize=9,
                fontweight="bold", color=col)

    # Volatility summary box: include all benchmarks
    vol_lines = [
        "Out-of-Sample Volatility (Annualised)",
        "-------------------------------------",
        f"Max Sharpe:     {oos_vol_sharpe*100:>6.2f}%",
        f"Min Volatility: {oos_vol_vol*100:>6.2f}%",
    ]
    for label, vol in benchmark_oos_vols.items():
        vol_lines.append(f"{label + ':':<17} {vol*100:>6.2f}%")
    vol_box = "\n".join(vol_lines)
    ax.text(0.98, 0.04, vol_box, transform=ax.transAxes, fontsize=10, family="monospace",
            ha="right", va="bottom",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#f8f9fa", alpha=0.9, edgecolor="#ced4da"))

    ax.set_title(
        f"Out-of-Sample Performance: MPT Portfolios vs. Benchmarks\n"
        f"Training: {training_years} yr  |  OOS: {oos_years} yr  |  Data source: yfinance",
        fontsize=14, fontweight="bold",
    )
    ax.set_ylabel("Cumulative Return (%)", fontsize=11)
    ax.set_xlabel("Date", fontsize=11)
    ax.grid(True, linestyle="--", alpha=0.5)
    # Place legend to the right to free up plotting area
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), borderaxespad=0, fontsize=10)

    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    fig.autofmt_xdate()
    # Leave space on the right for the external legend and volatility box
    fig.tight_layout(rect=[0, 0, 0.85, 1])

    out_path = SCRIPT_DIR / "portfolio_vs_markets_oos.png"
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    print(f"Chart saved -> {out_path}")


print("\nGenerating portfolio summary PDF...")
create_portfolio_pdf(
    output_path=PORTFOLIO_REPORT_PATH,
    tickers=tickers,
    max_weights=w_sharpe,
    min_weights=w_vol,
    max_metrics={
        "return": opt_ret_S,
        "volatility": opt_risk_S,
        "sharpe": opt_sr_S,
    },
    min_metrics={
        "return": opt_ret_V,
        "volatility": opt_risk_V,
        "sharpe": opt_sr_V,
    },
    analysis_path=BL_CACHE_PATH,
    training_start=training_start.date(),
    training_end=training_end.date(),
)
print(f"Portfolio summary saved -> {PORTFOLIO_REPORT_PATH}")
