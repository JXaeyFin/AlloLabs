"""Shared Yahoo Finance company context used by AI research and the dashboard."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

import yfinance as yf


RATIO_FIELDS = {
    "trailingPE": "P/E (TTM)",
    "priceToBook": "P/B",
    "debtToEquity": "Debt/Equity",
    "returnOnEquity": "ROE",
    "earningsGrowth": "EPS Growth (YoY)",
    "enterpriseToEbitda": "EV/EBITDA",
    "freeCashflow": "FCF",
    "totalRevenue": "Revenue",
    "netMargins": "Net Margin",
    "beta": "Beta",
    "marketCap": "Market Cap",
}


def _format_ratio(key: str, value):
    if key in {"returnOnEquity", "netMargins", "earningsGrowth"}:
        return f"{float(value) * 100:.1f}%"
    if key in {"freeCashflow", "totalRevenue", "marketCap"}:
        return f"${float(value) / 1e9:.2f}B"
    return round(float(value), 2)


def _news_url(item: dict, content: dict) -> str:
    candidates = (
        content.get("canonicalUrl"),
        content.get("clickThroughUrl"),
        content.get("link"),
        content.get("url"),
        item.get("link"),
        item.get("url"),
    )
    for candidate in candidates:
        if isinstance(candidate, dict):
            candidate = candidate.get("url")
        if not isinstance(candidate, str):
            continue
        candidate = candidate.strip()
        parsed = urlparse(candidate)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return candidate
    return ""


def fetch_ticker_context(ticker: str, max_news: int = 5) -> dict:
    """Return the exact fundamentals and news context supplied to AI research."""
    normalized = ticker.strip().upper()
    company = yf.Ticker(normalized)

    try:
        info = company.get_info() or {}
    except Exception:
        info = {}

    ratios = {}
    for key, label in RATIO_FIELDS.items():
        value = info.get(key)
        if value is None:
            continue
        try:
            ratios[label] = _format_ratio(key, value)
        except (TypeError, ValueError, OverflowError):
            continue

    news_items = []
    try:
        raw_news = company.news or []
    except Exception:
        raw_news = []
    for item in raw_news[:max_news]:
        content = item.get("content") or item
        title = str(content.get("title") or "").strip()
        if not title:
            continue
        provider = content.get("provider") or {}
        source = (
            provider.get("displayName")
            if isinstance(provider, dict)
            else None
        ) or content.get("publisher") or "Unknown"
        published = str(
            content.get("pubDate")
            or content.get("providerPublishTime")
            or ""
        )
        if published.isdigit():
            try:
                published = datetime.fromtimestamp(
                    int(published)
                ).astimezone().date().isoformat()
            except (OSError, OverflowError, ValueError):
                published = ""
        else:
            published = published[:10]
        summary = str(content.get("summary") or "").strip()
        news_items.append({
            "title": title,
            "source": str(source),
            "date": published,
            "summary": summary[:300] if summary else "",
            "url": _news_url(item, content),
        })

    return {
        "ticker": normalized,
        "name": (
            info.get("longName")
            or info.get("shortName")
            or normalized
        ),
        "ratios": ratios,
        "news": news_items,
        "source": "Yahoo Finance",
        "fetchedAt": datetime.now().astimezone().isoformat(),
    }
