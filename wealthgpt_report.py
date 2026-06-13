"""PDF reporting and sector classification for WealthGPT."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch, Rectangle


NAVY = "#102A43"
BLUE = "#2F6B9A"
TEAL = "#1A9A8A"
GOLD = "#D4A72C"
RED = "#C85C5C"
INK = "#243B53"
MUTED = "#627D98"
PALE = "#F3F7FA"
GRID = "#D9E2EC"
WHITE = "#FFFFFF"

SECTOR_MAP = {
    "AEM.TO": "Materials",
    "ATD.TO": "Consumer Staples",
    "BAM.TO": "Financials",
    "BN.TO": "Financials",
    "BIP-UN.TO": "Industrials",
    "BMO.TO": "Financials",
    "BNS.TO": "Financials",
    "ABX.TO": "Materials",
    "BCE.TO": "Communication Services",
    "CAE.TO": "Industrials",
    "CCO.TO": "Materials",
    "CM.TO": "Financials",
    "CNR.TO": "Industrials",
    "CNQ.TO": "Energy",
    "CP.TO": "Industrials",
    "CTC-A.TO": "Consumer Discretionary",
    "CCL-B.TO": "Materials",
    "CLS.TO": "Information Technology",
    "CVE.TO": "Energy",
    "GIB-A.TO": "Information Technology",
    "CSU.TO": "Information Technology",
    "DOL.TO": "Consumer Discretionary",
    "EMA.TO": "Utilities",
    "ENB.TO": "Energy",
    "FFH.TO": "Financials",
    "FM.TO": "Materials",
    "FSV.TO": "Real Estate",
    "FTS.TO": "Utilities",
    "FNV.TO": "Materials",
    "WN.TO": "Consumer Staples",
    "GIL.TO": "Consumer Discretionary",
    "H.TO": "Utilities",
    "IMO.TO": "Energy",
    "IFC.TO": "Financials",
    "K.TO": "Materials",
    "L.TO": "Consumer Staples",
    "MG.TO": "Consumer Discretionary",
    "MFC.TO": "Financials",
    "MRU.TO": "Consumer Staples",
    "NA.TO": "Financials",
    "NTR.TO": "Materials",
    "OTEX.TO": "Information Technology",
    "PPL.TO": "Energy",
    "POW.TO": "Financials",
    "QSR.TO": "Consumer Discretionary",
    "RCI-B.TO": "Communication Services",
    "RY.TO": "Financials",
    "SAP.TO": "Consumer Staples",
    "SHOP.TO": "Information Technology",
    "SLF.TO": "Financials",
    "SU.TO": "Energy",
    "TRP.TO": "Energy",
    "TECK-B.TO": "Materials",
    "T.TO": "Communication Services",
    "TRI.TO": "Industrials",
    "TD.TO": "Financials",
    "TOU.TO": "Energy",
    "WCN.TO": "Industrials",
    "WPM.TO": "Materials",
    "WSP.TO": "Industrials",
}

YAHOO_SECTOR_MAP = {
    "Basic Materials": "Materials",
    "Communication Services": "Communication Services",
    "Consumer Cyclical": "Consumer Discretionary",
    "Consumer Defensive": "Consumer Staples",
    "Energy": "Energy",
    "Financial Services": "Financials",
    "Healthcare": "Health Care",
    "Industrials": "Industrials",
    "Real Estate": "Real Estate",
    "Technology": "Information Technology",
    "Utilities": "Utilities",
}

INDUSTRY_KEYWORDS = {
    "Communication Services": (
        "advertising", "broadcast", "entertainment", "gaming", "media",
        "publishing", "telecom", "wireless",
    ),
    "Consumer Discretionary": (
        "apparel", "auto", "casino", "consumer electronics", "hotel",
        "internet retail", "leisure", "lodging", "luxury", "restaurant",
        "retail", "travel",
    ),
    "Consumer Staples": (
        "beverage", "confection", "discount store", "food", "grocery",
        "household", "packaged", "personal care", "tobacco",
    ),
    "Energy": (
        "coal", "drilling", "energy", "exploration", "oil", "petroleum",
        "pipeline", "refining",
    ),
    "Financials": (
        "asset management", "bank", "capital market", "credit", "exchange",
        "financial", "insurance", "mortgage", "payments",
    ),
    "Health Care": (
        "biotech", "diagnostic", "drug", "health", "life science", "medical",
        "pharma",
    ),
    "Industrials": (
        "aerospace", "air freight", "airline", "business services",
        "construction", "defense", "engineering", "industrial", "logistics",
        "machinery", "rail", "transport", "waste",
    ),
    "Information Technology": (
        "application software", "cloud", "computer", "cyber", "data processing",
        "electronic", "information technology", "semiconductor", "software",
        "technology hardware",
    ),
    "Materials": (
        "aluminum", "chemical", "copper", "forest", "gold", "materials",
        "metal", "mining", "paper", "steel",
    ),
    "Real Estate": ("real estate", "reit"),
    "Utilities": (
        "electric", "gas utility", "independent power", "regulated", "utility",
        "utilities", "water",
    ),
}

LAST_SECTORS: dict[str, str] = {}


def _infer_sector(industry):
    normalized = str(industry or "").strip().lower()
    for sector, keywords in INDUSTRY_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return sector
    return None


def _load_sector_cache(path):
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return {
            str(ticker): str(sector)
            for ticker, sector in payload.items()
            if isinstance(ticker, str) and isinstance(sector, str)
        }
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def resolve_sectors(tickers, max_weights, min_weights, analysis, cache_path):
    """Resolve sectors from known mappings, research, cache, then Yahoo."""
    cache_path = Path(cache_path)
    resolved = dict(SECTOR_MAP)
    resolved.update(_load_sector_cache(cache_path))
    active = {
        ticker
        for ticker, max_weight, min_weight in zip(tickers, max_weights, min_weights)
        if max(float(max_weight), float(min_weight)) > 1e-7
    }

    for ticker in tickers:
        item = analysis.get(ticker, {})
        sector = YAHOO_SECTOR_MAP.get(str(item.get("sector", "")))
        sector = sector or _infer_sector(item.get("industry"))
        if sector:
            resolved[ticker] = sector

    unresolved = sorted(
        ticker
        for ticker in active
        if resolved.get(ticker) in {None, "Other", "Unclassified"}
    )
    if unresolved:
        try:
            import yfinance as yf

            for ticker in unresolved:
                try:
                    info = yf.Ticker(ticker).get_info() or {}
                    sector = YAHOO_SECTOR_MAP.get(str(info.get("sector", "")))
                    sector = sector or _infer_sector(info.get("industry"))
                    resolved[ticker] = sector or "Unclassified"
                except Exception:
                    resolved[ticker] = "Unclassified"
        except ImportError:
            for ticker in unresolved:
                resolved[ticker] = "Unclassified"

    for ticker in tickers:
        resolved.setdefault(ticker, "Unclassified")

    current = {ticker: resolved[ticker] for ticker in tickers}
    temporary_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps({ticker: current[ticker] for ticker in sorted(current)}, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(cache_path)
    LAST_SECTORS.clear()
    LAST_SECTORS.update(current)
    SECTOR_MAP.update(current)
    return current


def _rounded_box(fig, x, y, width, height, facecolor=WHITE, edgecolor=GRID, radius=0.012):
    box = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle=f"round,pad=0.006,rounding_size={radius}",
        transform=fig.transFigure,
        linewidth=0.8,
        edgecolor=edgecolor,
        facecolor=facecolor,
        zorder=0,
    )
    fig.patches.append(box)
    return box


def _page_header(fig, title, subtitle, page_number):
    fig.patch.set_facecolor(PALE)
    fig.patches.append(
        Rectangle((0, 0.91), 1, 0.09, transform=fig.transFigure, color=NAVY, zorder=0)
    )
    fig.text(0.055, 0.958, title, color=WHITE, fontsize=20, weight="bold", va="center")
    fig.text(0.055, 0.925, subtitle, color="#D9EAF3", fontsize=9.5, va="center")
    fig.text(
        0.945,
        0.035,
        f"WEALTHGPT  |  {page_number}",
        color=MUTED,
        fontsize=7.5,
        ha="right",
    )
    fig.text(
        0.055,
        0.035,
        "Research model output. Not investment advice.",
        color=MUTED,
        fontsize=7.5,
    )


def _metric_card(fig, x, y, width, height, label, value, detail, accent):
    _rounded_box(fig, x, y, width, height)
    fig.patches.append(
        Rectangle((x, y), 0.007, height, transform=fig.transFigure, color=accent, zorder=1)
    )
    fig.text(x + 0.025, y + height - 0.024, label.upper(), color=MUTED, fontsize=7.4, weight="bold")
    fig.text(x + 0.025, y + 0.035, value, color=INK, fontsize=17, weight="bold")
    fig.text(x + 0.025, y + 0.014, detail, color=MUTED, fontsize=7.5)


def _format_optional_percent(value, decimals=1):
    """Format an optional decimal return or confidence value for display."""
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if not np.isfinite(numeric_value):
        return "N/A"
    return f"{numeric_value:.{decimals}%}"


def _portfolio_frame(tickers, weights, analysis):
    records = []
    for ticker, weight in zip(tickers, weights):
        item = analysis.get(ticker, {})
        records.append(
            {
                "ticker": ticker,
                "weight": float(weight),
                "sector": SECTOR_MAP.get(ticker, "Unclassified"),
                "industry": item.get("industry") or "Not classified",
                "posterior_return": item.get("posterior_return"),
                "expected_return": item.get("expected_return"),
                "confidence": item.get("confidence"),
                "view": item.get("view") or "No research rationale is available.",
            }
        )
    frame = pd.DataFrame(records)
    return (
        frame.assign(_absolute_weight=frame["weight"].abs())
        .sort_values("_absolute_weight", ascending=False)
        .drop(columns="_absolute_weight")
        .reset_index(drop=True)
    )


def _sector_frame(frame):
    sectors = (
        frame.assign(weight=frame["weight"].abs())
        .groupby("sector", as_index=False)["weight"]
        .sum()
        .sort_values("weight", ascending=False)
        .reset_index(drop=True)
    )
    gross_exposure = sectors["weight"].sum()
    if gross_exposure > 0:
        sectors["weight"] /= gross_exposure
    return sectors


def _effective_holdings(weights):
    weights = np.asarray(weights, dtype=float)
    return 1.0 / np.sum(np.square(weights)) if np.any(weights) else 0.0


def _dominant_sector(sectors):
    row = sectors.iloc[0]
    return f"{row['sector']} ({row['weight']:.1%})"


def _draw_weight_chart(ax, frame, color, count=10):
    data = frame.head(count).sort_values("weight")
    bar_colors = [RED if value < 0 else color for value in data["weight"]]
    ax.barh(data["ticker"], data["weight"] * 100, color=bar_colors, alpha=0.92)
    ax.axvline(0, color=INK, linewidth=0.7)
    ax.set_title(f"Top {min(count, len(data))} absolute positions", loc="left", fontsize=11, weight="bold", color=INK)
    ax.set_xlabel("Portfolio weight (%)", fontsize=8, color=MUTED)
    ax.tick_params(axis="both", labelsize=8, colors=INK)
    ax.grid(axis="x", color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    maximum = float((data["weight"].abs() * 100).max())
    for y_pos, value in enumerate(data["weight"] * 100):
        if abs(value) >= 0.88 * maximum:
            ax.text(
                value - 0.25 if value >= 0 else value + 0.25,
                y_pos,
                f"{value:.1f}%",
                va="center",
                ha="right" if value >= 0 else "left",
                fontsize=7.5,
                color=WHITE,
                weight="bold",
            )
        else:
            offset = 0.2 if value >= 0 else -0.2
            ax.text(
                value + offset,
                y_pos,
                f"{value:.1f}%",
                va="center",
                ha="left" if value >= 0 else "right",
                fontsize=7.5,
                color=INK,
            )


def _draw_sector_comparison(ax, max_sector, min_sector):
    sector_order = list(
        dict.fromkeys(max_sector["sector"].tolist() + min_sector["sector"].tolist())
    )
    max_map = max_sector.set_index("sector")["weight"].to_dict()
    min_map = min_sector.set_index("sector")["weight"].to_dict()
    sector_order = sorted(
        sector_order,
        key=lambda sector: max(max_map.get(sector, 0), min_map.get(sector, 0)),
        reverse=True,
    )
    sector_order = sector_order[:10][::-1]
    y = np.arange(len(sector_order))
    height = 0.34
    ax.barh(y + height / 2, [max_map.get(s, 0) * 100 for s in sector_order], height, color=BLUE, label="Max Sharpe")
    ax.barh(y - height / 2, [min_map.get(s, 0) * 100 for s in sector_order], height, color=TEAL, label="Min Volatility")
    ax.set_yticks(y, sector_order)
    ax.set_xlabel("Portfolio weight (%)", fontsize=8, color=MUTED)
    ax.set_title("Sector exposure", loc="left", fontsize=11, weight="bold", color=INK)
    ax.tick_params(axis="both", labelsize=7.8, colors=INK)
    ax.grid(axis="x", color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.legend(frameon=False, fontsize=8, loc="lower right")


def _overview_page(
    pdf,
    max_frame,
    min_frame,
    max_metrics,
    min_metrics,
    training_start,
    training_end,
):
    fig = plt.figure(figsize=(8.5, 11))
    _page_header(
        fig,
        "Portfolio Summary",
        f"Global allocation model  |  Training: {training_start} to {training_end}",
        1,
    )

    _metric_card(
        fig, 0.055, 0.79, 0.205, 0.085, "Max Sharpe return",
        f"{max_metrics['return']:.1%}", f"Sharpe {max_metrics['sharpe']:.2f}", BLUE,
    )
    _metric_card(
        fig, 0.275, 0.79, 0.205, 0.085, "Max Sharpe risk",
        f"{max_metrics['volatility']:.1%}", f"Top 5 gross share: {max_frame.head(5)['weight'].abs().sum() / max_frame['weight'].abs().sum():.1%}", BLUE,
    )
    _metric_card(
        fig, 0.52, 0.79, 0.205, 0.085, "Min Vol return",
        f"{min_metrics['return']:.1%}", f"Sharpe {min_metrics['sharpe']:.2f}", TEAL,
    )
    _metric_card(
        fig, 0.74, 0.79, 0.205, 0.085, "Min Vol risk",
        f"{min_metrics['volatility']:.1%}", f"Top 5 gross share: {min_frame.head(5)['weight'].abs().sum() / min_frame['weight'].abs().sum():.1%}", TEAL,
    )

    ax_left = fig.add_axes([0.075, 0.49, 0.39, 0.245], facecolor=WHITE)
    ax_right = fig.add_axes([0.535, 0.49, 0.39, 0.245], facecolor=WHITE)
    _draw_weight_chart(ax_left, max_frame, BLUE, count=8)
    _draw_weight_chart(ax_right, min_frame, TEAL, count=8)

    max_sector = _sector_frame(max_frame)
    min_sector = _sector_frame(min_frame)
    ax_sector = fig.add_axes([0.19, 0.17, 0.41, 0.245], facecolor=WHITE)
    _draw_sector_comparison(ax_sector, max_sector, min_sector)

    _rounded_box(fig, 0.635, 0.145, 0.31, 0.27)
    fig.text(0.66, 0.38, "PORTFOLIO CHARACTER", color=INK, fontsize=10, weight="bold")
    overlap = float(
        np.minimum(max_frame["weight"].abs(), min_frame["weight"].abs()).sum()
        / max(max_frame["weight"].abs().sum(), min_frame["weight"].abs().sum())
    )
    notes = [
        ("Max Sharpe", f"Dominant sector: {_dominant_sector(max_sector)}"),
        ("Min Volatility", f"Dominant sector: {_dominant_sector(min_sector)}"),
        ("Diversification", f"Effective holdings: {_effective_holdings(max_frame['weight']):.1f} vs. {_effective_holdings(min_frame['weight']):.1f}"),
        ("Common exposure", f"Weight overlap: {overlap:.1%}"),
    ]
    y = 0.345
    for label, detail in notes:
        fig.text(0.66, y, label, color=GOLD, fontsize=8.5, weight="bold")
        fig.text(0.66, y - 0.024, "\n".join(textwrap.wrap(detail, 37)), color=INK, fontsize=8.2)
        y -= 0.058

    overview_note = (
        "Expected returns are Black-Litterman posterior estimates. Volatility and Sharpe metrics are "
        "annualized in-sample estimates. Portfolio weights sum to 100% net; negative weights indicate short positions."
    )
    fig.text(0.055, 0.09, "\n".join(textwrap.wrap(overview_note, 125)), color=MUTED, fontsize=7.7)
    pdf.savefig(fig, facecolor=fig.get_facecolor())
    plt.close(fig)


def _portfolio_breakdown_page(pdf, frame, metrics, name, color, page_number):
    fig = plt.figure(figsize=(8.5, 11))
    _page_header(
        fig,
        f"{name} Portfolio",
        "Allocation breakdown, concentration, and sector structure",
        page_number,
    )
    _metric_card(fig, 0.055, 0.79, 0.205, 0.085, "Expected return", f"{metrics['return']:.1%}", "Annualized", color)
    _metric_card(fig, 0.275, 0.79, 0.205, 0.085, "Volatility", f"{metrics['volatility']:.1%}", "Annualized", color)
    _metric_card(fig, 0.495, 0.79, 0.205, 0.085, "Sharpe ratio", f"{metrics['sharpe']:.2f}", "Risk-free adjusted", color)
    active = frame[frame["weight"].abs() > 0.0001]
    _metric_card(fig, 0.715, 0.79, 0.23, 0.085, "Active positions", f"{len(active)}", f"Effective: {_effective_holdings(frame['weight']):.1f}", color)

    ax_weights = fig.add_axes([0.075, 0.43, 0.52, 0.29], facecolor=WHITE)
    _draw_weight_chart(ax_weights, frame, color, count=12)

    sectors = _sector_frame(frame)
    ax_sector = fig.add_axes([0.65, 0.47, 0.29, 0.22], facecolor=WHITE)
    sector_colors = [color, GOLD, BLUE, "#7B8CDE", "#73A580", "#B98EA7", "#8D99AE", "#A17C6B"]
    shown = sectors.head(7).copy()
    other = 1.0 - shown["weight"].sum()
    if other > 0.001:
        shown.loc[len(shown)] = ["Other", other]
    ax_sector.pie(
        shown["weight"],
        labels=shown["sector"],
        colors=sector_colors[: len(shown)],
        startangle=90,
        counterclock=False,
        wedgeprops={"width": 0.42, "edgecolor": WHITE},
        textprops={"fontsize": 7, "color": INK},
        autopct=lambda value: f"{value:.0f}%" if value >= 5 else "",
        pctdistance=0.78,
    )
    ax_sector.set_title("Gross sector mix", fontsize=11, weight="bold", color=INK)

    _rounded_box(fig, 0.055, 0.075, 0.89, 0.285)
    fig.text(0.075, 0.328, "TOP EIGHT HOLDINGS", color=INK, fontsize=10, weight="bold")
    top = frame.head(8)
    columns = [0.075, 0.19, 0.31, 0.55, 0.72, 0.84]
    headers = ["Ticker", "Weight", "Sector", "Posterior", "Confidence", "Rank"]
    for x, header in zip(columns, headers):
        fig.text(x, 0.296, header, color=MUTED, fontsize=7.8, weight="bold")
    y = 0.268
    for rank, row in top.iterrows():
        fig.text(columns[0], y, row["ticker"], color=INK, fontsize=8.2, weight="bold")
        fig.text(columns[1], y, f"{row['weight']:.2%}", color=INK, fontsize=8.2)
        fig.text(columns[2], y, row["sector"], color=INK, fontsize=7.8)
        posterior = row["posterior_return"]
        confidence = row["confidence"]
        fig.text(columns[3], y, _format_optional_percent(posterior, 1), color=INK, fontsize=8.2)
        fig.text(columns[4], y, _format_optional_percent(confidence, 0), color=INK, fontsize=8.2)
        fig.text(columns[5], y, f"#{rank + 1}", color=color, fontsize=8.2, weight="bold")
        y -= 0.024

    pdf.savefig(fig, facecolor=fig.get_facecolor())
    plt.close(fig)


def _rationale_pages(pdf, frame, name, color, starting_page):
    top = frame.head(8).reset_index(drop=True)
    for page_offset, start in enumerate((0, 4)):
        fig = plt.figure(figsize=(8.5, 11))
        _page_header(
            fig,
            f"{name}: Holding Rationale",
            f"Research views for top holdings {start + 1}-{start + 4}; weights also reflect covariance and portfolio constraints",
            starting_page + page_offset,
        )
        y_positions = [0.73, 0.53, 0.33, 0.13]
        for position, (_, row) in zip(y_positions, top.iloc[start:start + 4].iterrows()):
            _rounded_box(fig, 0.055, position, 0.89, 0.145)
            fig.patches.append(
                Rectangle((0.055, position), 0.009, 0.145, transform=fig.transFigure, color=color, zorder=1)
            )
            rank = start + list(y_positions).index(position) + 1
            fig.text(0.082, position + 0.111, f"#{rank}  {row['ticker']}", color=INK, fontsize=12, weight="bold")
            fig.text(
                0.275,
                position + 0.113,
                (
                    f"{row['weight']:.2%} weight  |  {row['sector']}  |  "
                    f"Posterior {_format_optional_percent(row['posterior_return'], 1)}"
                ),
                color=MUTED,
                fontsize=8.2,
            )
            rationale = " ".join(str(row["view"]).split())
            wrapped = "\n".join(textwrap.wrap(rationale, width=112))
            fig.text(0.082, position + 0.078, wrapped, color=INK, fontsize=8.1, va="top", linespacing=1.3)
        pdf.savefig(fig, facecolor=fig.get_facecolor())
        plt.close(fig)


def _allocation_appendix(pdf, max_frame, min_frame, page_number):
    fig = plt.figure(figsize=(8.5, 11))
    _page_header(
        fig,
        "Detailed Allocation Appendix",
        "Positions above 0.01%; values may not sum to exactly 100% because of display rounding",
        page_number,
    )

    for left, frame, name, color in (
        (0.055, max_frame, "MAX SHARPE", BLUE),
        (0.52, min_frame, "MIN VOLATILITY", TEAL),
    ):
        _rounded_box(fig, left, 0.085, 0.425, 0.79)
        fig.text(left + 0.02, 0.84, name, color=color, fontsize=11, weight="bold")
        fig.text(left + 0.02, 0.812, "Ticker", color=MUTED, fontsize=7.5, weight="bold")
        fig.text(left + 0.14, 0.812, "Sector", color=MUTED, fontsize=7.5, weight="bold")
        fig.text(left + 0.37, 0.812, "Weight", color=MUTED, fontsize=7.5, weight="bold", ha="right")
        active = frame[frame["weight"].abs() > 0.0001].copy()
        y = 0.786
        line_height = min(0.022, 0.68 / max(len(active), 1))
        font_size = 7.3 if len(active) <= 30 else 6.5
        for _, row in active.iterrows():
            fig.text(left + 0.02, y, row["ticker"], color=INK, fontsize=font_size, weight="bold")
            fig.text(left + 0.14, y, row["sector"], color=INK, fontsize=font_size)
            fig.text(left + 0.37, y, f"{row['weight']:.2%}", color=INK, fontsize=font_size, ha="right")
            y -= line_height

    pdf.savefig(fig, facecolor=fig.get_facecolor())
    plt.close(fig)


def create_portfolio_pdf(
    output_path,
    tickers,
    max_weights,
    min_weights,
    max_metrics,
    min_metrics,
    analysis_path,
    training_start,
    training_end,
):
    """Create a polished multi-page PDF portfolio summary."""
    output_path = Path(output_path)
    analysis_path = Path(analysis_path)
    try:
        analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        analysis = {}

    sectors = resolve_sectors(
        tickers,
        max_weights,
        min_weights,
        analysis,
        output_path.with_name("sector_cache.json"),
    )

    max_frame = _portfolio_frame(tickers, max_weights, analysis)
    min_frame = _portfolio_frame(tickers, min_weights, analysis)

    allocation_export = pd.DataFrame(
        {
            "ticker": tickers,
            "sector": [sectors[ticker] for ticker in tickers],
            "max_sharpe_weight": max_weights,
            "min_volatility_weight": min_weights,
        }
    ).sort_values("max_sharpe_weight", ascending=False)
    allocation_export.to_csv(output_path.with_name("portfolio_allocations.csv"), index=False)

    metadata = {
        "Title": "WealthGPT Portfolio Summary",
        "Author": "Jeffrey Xia",
        "Subject": "Global portfolio allocation model summary",
        "Keywords": "portfolio optimization, Black-Litterman, MPT, global equities",
    }
    with PdfPages(output_path, metadata=metadata) as pdf:
        _overview_page(
            pdf,
            max_frame,
            min_frame,
            max_metrics,
            min_metrics,
            training_start,
            training_end,
        )
        _portfolio_breakdown_page(pdf, max_frame, max_metrics, "Maximum Sharpe", BLUE, 2)
        _rationale_pages(pdf, max_frame, "Maximum Sharpe", BLUE, 3)
        _portfolio_breakdown_page(pdf, min_frame, min_metrics, "Minimum Volatility", TEAL, 5)
        _rationale_pages(pdf, min_frame, "Minimum Volatility", TEAL, 6)
        _allocation_appendix(pdf, max_frame, min_frame, 8)

    return output_path
