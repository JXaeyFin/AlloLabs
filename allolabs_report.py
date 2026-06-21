"""PDF reporting and sector classification for AlloLabs."""

from __future__ import annotations

import json
import math
import re
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch, Rectangle


NAVY = "#05070A"
BLUE = "#4DA3FF"
TEAL = "#20C77A"
GOLD = "#F0A202"
RED = "#FF5A5F"
INK = "#F4F7FA"
MUTED = "#9AA4B2"
PALE = "#070A0E"
GRID = "#2B333D"
WHITE = "#11161C"
PANEL_ALT = "#161C23"
LOGO_BG = "#FFFFFF"
POSITIVE = "#42D392"
TERMINAL_ORANGE = "#FFB000"
ALLOCATION_APPENDIX_MIN_WEIGHT = 0.00005
ALLOCATION_APPENDIX_ROWS_PER_PAGE = 28
COMPANY_LOGO_DIR = Path(__file__).resolve().parent / "resources" / "company-logos"
COMPANY_LOGO_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,19}$")
COMPANY_LOGO_CACHE = {}

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


def _company_logo_path(ticker):
    normalized = str(ticker or "").strip().upper()
    if not COMPANY_LOGO_PATTERN.fullmatch(normalized):
        return None
    path = COMPANY_LOGO_DIR / f"{normalized}.png"
    return path if path.is_file() else None


def _draw_company_logo(fig, ticker, x, y, size):
    """Draw a locally cached logo in a restrained rounded-square card."""
    path = _company_logo_path(ticker)
    if path is None:
        return False
    try:
        image = COMPANY_LOGO_CACHE.get(path)
        if image is None:
            image = plt.imread(path)
            COMPANY_LOGO_CACHE[path] = image
    except (OSError, ValueError):
        return False

    height = size * fig.get_figwidth() / fig.get_figheight()
    ax = fig.add_axes([x, y, size, height], zorder=4)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    clip = FancyBboxPatch(
        (0, 0),
        1,
        1,
        boxstyle="round,pad=0,rounding_size=0.18",
        transform=ax.transAxes,
        linewidth=0,
        facecolor=LOGO_BG,
        zorder=0,
    )
    ax.add_patch(clip)
    logo = ax.imshow(image, extent=(0.08, 0.92, 0.08, 0.92), interpolation="lanczos", zorder=1)
    logo.set_clip_path(clip)
    ax.add_patch(
        FancyBboxPatch(
            (0, 0),
            1,
            1,
            boxstyle="round,pad=0,rounding_size=0.18",
            transform=ax.transAxes,
            linewidth=0.8,
            edgecolor=GRID,
            facecolor="none",
            zorder=2,
        )
    )
    return True


def _page_header(fig, title, subtitle, page_number):
    fig.patch.set_facecolor(PALE)
    fig.patches.append(
        Rectangle((0, 0.91), 1, 0.09, transform=fig.transFigure, color=NAVY, zorder=0)
    )
    fig.text(0.055, 0.958, title, color=WHITE, fontsize=20, weight="bold", va="center")
    fig.text(0.055, 0.925, subtitle, color=MUTED, fontsize=9.3, va="center")
    fig.text(
        0.945,
        0.035,
        f"ALLOLABS  |  {page_number}",
        color=MUTED,
        fontsize=7.5,
        ha="right",
    )
    fig.text(
        0.055,
        0.035,
        "RESEARCH SYSTEM OUTPUT // EDUCATIONAL USE // NOT INVESTMENT ADVICE",
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


def _safe_float(value):
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if np.isfinite(numeric) else None


def _weighted_input(frame, column):
    if column not in frame:
        return None
    values = pd.to_numeric(frame[column], errors="coerce")
    mask = values.notna()
    if not mask.any():
        return None
    weights = frame.loc[mask, "weight"].astype(float)
    return float(np.dot(weights, values[mask]))


def _return_diagnostics(frame, metrics):
    model_return = _safe_float(metrics.get("return"))
    volatility = _safe_float(metrics.get("volatility"))
    historical = _weighted_input(frame, "historical_return")
    equilibrium = _weighted_input(frame, "prior_return")
    ai_view = _weighted_input(frame, "expected_return")
    posterior = _weighted_input(frame, "posterior_return")
    uses_black_litterman = posterior is not None or equilibrium is not None or ai_view is not None
    if historical is None and not uses_black_litterman:
        historical = model_return
    confidence = pd.to_numeric(frame["confidence"], errors="coerce")
    covered = confidence.notna()
    gross = float(frame["weight"].abs().sum())
    covered_gross = float(frame.loc[covered, "weight"].abs().sum()) if covered.any() else 0.0
    avg_confidence = (
        float(np.average(confidence[covered], weights=frame.loc[covered, "weight"].abs()))
        if covered.any() and covered_gross > 0
        else None
    )
    extreme = bool(
        model_return is not None
        and (
            abs(model_return) >= 0.25
            or (volatility is not None and volatility > 0 and abs(model_return) >= 2.0 * volatility)
        )
    )
    return {
        "historical": historical,
        "equilibrium": equilibrium,
        "ai_view": ai_view,
        "posterior": posterior,
        "optimizer_input": model_return,
        "mode": "black_litterman" if uses_black_litterman else "historical",
        "volatility": volatility,
        "coverage": covered_gross / gross if gross > 0 else 0.0,
        "confidence": avg_confidence,
        "extreme": extreme,
    }


def _diagnostic_label(diagnostics):
    if diagnostics["extreme"]:
        return "HIGH / UNSTABLE INPUT"
    if diagnostics["coverage"] < 0.75:
        return "PARTIAL VIEW COVERAGE"
    return "MODEL INPUT - NOT FORECAST"


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
                "historical_return": item.get("historical_return"),
                "prior_return": item.get("prior_return"),
                "posterior_return": item.get("posterior_return"),
                "delta_return": item.get("delta_return"),
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
    ax.set_facecolor(WHITE)
    ax.barh(data["ticker"], data["weight"] * 100, color=bar_colors, alpha=0.92)
    ax.axvline(0, color=MUTED, linewidth=0.7)
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
                color=NAVY,
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
    ax.set_facecolor(WHITE)
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
    legend = ax.legend(frameon=False, fontsize=8, loc="lower right")
    for label in legend.get_texts():
        label.set_color(INK)


def _return_bridge_page(pdf, max_frame, min_frame, max_metrics, min_metrics, page_number):
    fig = plt.figure(figsize=(8.5, 11))
    _page_header(
        fig,
        "Return Input Bridge",
        "Separating observed history, equilibrium assumptions, AI views, and optimizer inputs",
        page_number,
    )
    diagnostics = (
        ("MAXIMUM SHARPE", _return_diagnostics(max_frame, max_metrics), BLUE),
        ("MINIMUM VOLATILITY", _return_diagnostics(min_frame, min_metrics), TEAL),
    )
    labels = [
        ("Historical sample", "Annualized arithmetic return observed in the training window."),
        ("Equilibrium prior", "Risk-and-covariance-implied return before security views."),
        ("AI view", "Weighted 12-month security views where research is available."),
        ("Optimizer input", "Black-Litterman posterior when enabled; otherwise the historical input."),
    ]
    for left, (name, values, color) in zip((0.055, 0.52), diagnostics):
        _rounded_box(fig, left, 0.45, 0.425, 0.42, facecolor=WHITE)
        fig.text(left + 0.02, 0.835, name, color=color, fontsize=10.5, weight="bold")
        fig.text(
            left + 0.37,
            0.835,
            _diagnostic_label(values),
            color=RED if values["extreme"] else MUTED,
            fontsize=6.8,
            ha="right",
            weight="bold",
        )
        series = (
            values["historical"],
            values["equilibrium"],
            values["ai_view"],
            values["optimizer_input"],
        )
        y = 0.782
        for (label, explanation), value in zip(labels, series):
            fig.text(left + 0.02, y, label.upper(), color=MUTED, fontsize=7.2, weight="bold")
            fig.text(
                left + 0.37,
                y,
                _format_optional_percent(value, 1),
                color=color if label == "Optimizer input" else INK,
                fontsize=12 if label == "Optimizer input" else 10,
                ha="right",
                weight="bold" if label == "Optimizer input" else "normal",
            )
            fig.text(
                left + 0.02,
                y - 0.025,
                "\n".join(textwrap.wrap(explanation, 51)),
                color=MUTED,
                fontsize=7.1,
                linespacing=1.2,
            )
            y -= 0.083
        fig.text(
            left + 0.02,
            0.493,
            f"MODE  {values['mode'].replace('_', ' ').upper()}",
            color=GOLD,
            fontsize=7.4,
            weight="bold",
        )
        fig.text(
            left + 0.02,
            0.473,
            (
                f"Research coverage {values['coverage']:.0%}"
                + (
                    f"  |  mean confidence {values['confidence']:.0%}"
                    if values["confidence"] is not None
                    else "  |  confidence unavailable"
                )
            ),
            color=MUTED,
            fontsize=7.1,
        )

    _rounded_box(fig, 0.055, 0.105, 0.89, 0.285, facecolor=PANEL_ALT)
    fig.text(0.08, 0.35, "HOW TO READ THESE NUMBERS", color=TERMINAL_ORANGE, fontsize=10, weight="bold")
    guidance = [
        (
            "Historical is descriptive, not predictive.",
            "A strong training period can annualize to an implausibly high figure. It records what occurred in that sample; it is not a promise that the same return will repeat.",
        ),
        (
            "The posterior is an optimization input.",
            "Black-Litterman regularizes the prior with security views, but the result remains model-sensitive. It should be used to compare allocations, not quoted as a precise realized-return forecast.",
        ),
        (
            "Risk estimates are also conditional.",
            "Annualized volatility and Sharpe are based on the same covariance window. Regime changes, correlation spikes, transaction costs, taxes, and liquidity can materially alter realized outcomes.",
        ),
    ]
    y = 0.31
    for heading, body in guidance:
        fig.text(0.08, y, heading, color=INK, fontsize=8.4, weight="bold")
        fig.text(0.08, y - 0.024, "\n".join(textwrap.wrap(body, 126)), color=MUTED, fontsize=7.6)
        y -= 0.077
    pdf.savefig(fig, facecolor=fig.get_facecolor())
    plt.close(fig)


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
        "Allocation Monitor",
        f"MODEL RUN // TRAINING WINDOW {training_start} TO {training_end} // VALUES ARE CONDITIONAL ESTIMATES",
        1,
    )
    max_diag = _return_diagnostics(max_frame, max_metrics)
    min_diag = _return_diagnostics(min_frame, min_metrics)

    _metric_card(
        fig, 0.055, 0.79, 0.205, 0.085, "Max Sharpe risk",
        f"{max_metrics['volatility']:.1%}", "Annualized covariance estimate", BLUE,
    )
    _metric_card(
        fig, 0.275, 0.79, 0.205, 0.085, "Max model return",
        f"{max_metrics['return']:.1%}", _diagnostic_label(max_diag), GOLD,
    )
    _metric_card(
        fig, 0.52, 0.79, 0.205, 0.085, "Min Volatility risk",
        f"{min_metrics['volatility']:.1%}", "Annualized covariance estimate", TEAL,
    )
    _metric_card(
        fig, 0.74, 0.79, 0.205, 0.085, "Min Vol model return",
        f"{min_metrics['return']:.1%}", _diagnostic_label(min_diag), GOLD,
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
        "MODEL DISCIPLINE: displayed returns are Black-Litterman optimizer inputs, not realized-return forecasts. "
        "They combine sample-dependent estimates, an equilibrium prior, and optional AI views. Use the portfolios "
        "to study relative allocation and risk trade-offs. Portfolio weights sum to 100% net; negative weights are shorts."
    )
    fig.text(0.055, 0.09, "\n".join(textwrap.wrap(overview_note, 125)), color=MUTED, fontsize=7.7)
    pdf.savefig(fig, facecolor=fig.get_facecolor())
    plt.close(fig)


def _portfolio_breakdown_page(pdf, frame, metrics, name, color, page_number):
    fig = plt.figure(figsize=(8.5, 11))
    _page_header(
        fig,
        f"{name} Portfolio",
        "Construction, concentration, sector structure, and conditional model diagnostics",
        page_number,
    )
    diagnostics = _return_diagnostics(frame, metrics)
    _metric_card(fig, 0.055, 0.79, 0.205, 0.085, "Model return input", f"{metrics['return']:.1%}", _diagnostic_label(diagnostics), GOLD)
    _metric_card(fig, 0.275, 0.79, 0.205, 0.085, "Model volatility", f"{metrics['volatility']:.1%}", "Sample covariance estimate", color)
    _metric_card(fig, 0.495, 0.79, 0.205, 0.085, "Optimizer score", f"{metrics['sharpe']:.2f}", "In-sample Sharpe objective", color)
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
    headers = ["Ticker", "Weight", "Sector", "BL input", "Confidence", "Rank"]
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
            f"SECURITY NOTES {start + 1}-{start + 4} // THESIS, MODEL INPUTS, AND PRINCIPAL RISK",
            starting_page + page_offset,
        )
        y_positions = [0.73, 0.53, 0.33, 0.13]
        for position, (_, row) in zip(y_positions, top.iloc[start:start + 4].iterrows()):
            _rounded_box(fig, 0.055, position, 0.89, 0.145)
            fig.patches.append(
                Rectangle((0.055, position), 0.009, 0.145, transform=fig.transFigure, color=color, zorder=1)
            )
            rank = start + list(y_positions).index(position) + 1
            has_logo = _draw_company_logo(
                fig,
                row["ticker"],
                0.082,
                position + 0.089,
                0.048,
            )
            ticker_x = 0.145 if has_logo else 0.082
            detail_x = 0.315 if has_logo else 0.275
            fig.text(ticker_x, position + 0.111, f"#{rank}  {row['ticker']}", color=INK, fontsize=12, weight="bold")
            fig.text(
                detail_x,
                position + 0.113,
                (
                    f"{row['weight']:.2%} weight  |  {row['sector']}  |  "
                    f"BL input {_format_optional_percent(row['posterior_return'], 1)}"
                ),
                color=MUTED,
                fontsize=8.2,
            )
            rationale = " ".join(str(row["view"]).split())
            wrapped = "\n".join(textwrap.wrap(rationale, width=112))
            fig.text(0.082, position + 0.078, wrapped, color=INK, fontsize=8.1, va="top", linespacing=1.3)
            bridge = (
                f"Prior {_format_optional_percent(row['prior_return'], 1)}  |  "
                f"AI view {_format_optional_percent(row['expected_return'], 1)}  |  "
                f"Confidence {_format_optional_percent(row['confidence'], 0)}"
            )
            fig.text(0.69, position + 0.018, bridge, color=GOLD, fontsize=6.7, ha="right")
        fig.text(
            0.945,
            0.052,
            "Company marks: Logo.dev",
            color=MUTED,
            fontsize=6.7,
            ha="right",
            url="https://logo.dev",
        )
        pdf.savefig(fig, facecolor=fig.get_facecolor())
        plt.close(fig)


def _methodology_page(pdf, max_frame, min_frame, max_metrics, min_metrics, page_number):
    fig = plt.figure(figsize=(8.5, 11))
    _page_header(
        fig,
        "Model Notes & Risk Controls",
        "What the system estimates, what it does not know, and how to use the output responsibly",
        page_number,
    )
    sections = [
        (
            "01  RETURN ESTIMATION",
            "When AI-assisted Black-Litterman is enabled, an equilibrium prior is blended with security views. When it "
            "is disabled, the optimizer may use annualized historical returns directly. In either mode, the displayed "
            "return is an uncertain optimization input, not a promised 12-month outcome.",
        ),
        (
            "02  WHY LARGE NUMBERS APPEAR",
            "Short or unusually strong training windows can produce extreme annualized observations. Concentrated "
            "portfolios can also magnify a few high posterior inputs. Figures above roughly 25% should be treated as "
            "instability warnings that warrant sensitivity testing, not as base-case forecasts.",
        ),
        (
            "03  RISK MODEL",
            "Volatility and correlations are estimated from the selected training sample. They can understate risk "
            "during regime changes, liquidity shocks, crowded unwinds, or structural breaks. Correlations often rise "
            "when diversification is needed most.",
        ),
        (
            "04  AI RESEARCH LAYER",
            "AI views summarize supplied fundamentals and headlines into probability-weighted return inputs. Confidence "
            "measures evidence quality, not the probability of a positive return. Generated analysis may be incomplete, "
            "stale, biased, or wrong and should be independently verified.",
        ),
        (
            "05  IMPLEMENTATION GAP",
            "The model excludes taxes, bid-ask spreads, market impact, borrow availability, financing costs, and most "
            "turnover effects unless approximated through regularization. Real portfolios should include these costs, "
            "position liquidity, mandate limits, and rebalancing governance.",
        ),
    ]
    y = 0.835
    for heading, body in sections:
        _rounded_box(fig, 0.055, y - 0.122, 0.89, 0.135, facecolor=WHITE)
        fig.text(0.078, y - 0.018, heading, color=TERMINAL_ORANGE, fontsize=9, weight="bold")
        fig.text(
            0.078,
            y - 0.052,
            "\n".join(textwrap.wrap(body, 124)),
            color=INK,
            fontsize=7.7,
            va="top",
            linespacing=1.3,
        )
        y -= 0.146

    max_diag = _return_diagnostics(max_frame, max_metrics)
    min_diag = _return_diagnostics(min_frame, min_metrics)
    _rounded_box(fig, 0.055, 0.075, 0.89, 0.105, facecolor=PANEL_ALT)
    fig.text(0.078, 0.15, "RUN-SPECIFIC FLAGS", color=TERMINAL_ORANGE, fontsize=8.5, weight="bold")
    flags = []
    for label, diag in (("Max Sharpe", max_diag), ("Min Volatility", min_diag)):
        flags.append(
            f"{label}: {_diagnostic_label(diag).lower()}, research coverage {diag['coverage']:.0%}, "
            f"effective model volatility {_format_optional_percent(diag['volatility'], 1)}."
        )
    fig.text(0.078, 0.118, "\n".join(flags), color=INK, fontsize=7.5, linespacing=1.4)
    pdf.savefig(fig, facecolor=fig.get_facecolor())
    plt.close(fig)


def _allocation_appendix(pdf, max_frame, min_frame, page_number):
    portfolios = (
        (
            max_frame[max_frame["weight"].abs() >= ALLOCATION_APPENDIX_MIN_WEIGHT].copy(),
            "MAX SHARPE",
            BLUE,
        ),
        (
            min_frame[min_frame["weight"].abs() >= ALLOCATION_APPENDIX_MIN_WEIGHT].copy(),
            "MIN VOLATILITY",
            TEAL,
        ),
    )
    page_count = max(
        1,
        max(
            math.ceil(len(frame) / ALLOCATION_APPENDIX_ROWS_PER_PAGE)
            for frame, _, _ in portfolios
        ),
    )

    for page_offset in range(page_count):
        fig = plt.figure(figsize=(8.5, 11))
        continuation = f" - page {page_offset + 1} of {page_count}" if page_count > 1 else ""
        _page_header(
            fig,
            "Detailed Allocation Appendix",
            (
                "Positions at or above 0.005% absolute weight"
                f"{continuation}; values may not sum to exactly 100% because of display rounding"
            ),
            page_number + page_offset,
        )

        start = page_offset * ALLOCATION_APPENDIX_ROWS_PER_PAGE
        stop = start + ALLOCATION_APPENDIX_ROWS_PER_PAGE
        for left, (frame, name, color) in zip((0.055, 0.52), portfolios):
            page_rows = frame.iloc[start:stop]
            _rounded_box(fig, left, 0.085, 0.425, 0.79)
            fig.text(left + 0.02, 0.84, name, color=color, fontsize=11, weight="bold")
            fig.text(
                left + 0.37,
                0.84,
                f"{len(frame)} positions",
                color=MUTED,
                fontsize=7.5,
                ha="right",
            )
            fig.text(left + 0.02, 0.812, "Ticker", color=MUTED, fontsize=7.5, weight="bold")
            fig.text(left + 0.14, 0.812, "Sector", color=MUTED, fontsize=7.5, weight="bold")
            fig.text(left + 0.37, 0.812, "Weight", color=MUTED, fontsize=7.5, weight="bold", ha="right")
            y = 0.784
            for _, row in page_rows.iterrows():
                fig.text(left + 0.02, y, row["ticker"], color=INK, fontsize=7.3, weight="bold")
                fig.text(left + 0.14, y, row["sector"], color=INK, fontsize=7.1)
                fig.text(left + 0.37, y, f"{row['weight']:.3%}", color=INK, fontsize=7.3, ha="right")
                y -= 0.024
            if page_rows.empty:
                fig.text(
                    left + 0.02,
                    0.775,
                    "No additional positions on this continuation page.",
                    color=MUTED,
                    fontsize=7.3,
                )

        pdf.savefig(fig, facecolor=fig.get_facecolor())
        plt.close(fig)

    return page_count


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
    """Create an educational terminal-style portfolio research report."""
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
        "Title": "AlloLabs Portfolio Research Monitor",
        "Author": "Jeffrey Xia",
        "Subject": "Educational global portfolio construction and model-risk report",
        "Keywords": "portfolio optimization, Black-Litterman, model risk, MPT, global equities",
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
        _return_bridge_page(pdf, max_frame, min_frame, max_metrics, min_metrics, 2)
        _portfolio_breakdown_page(pdf, max_frame, max_metrics, "Maximum Sharpe", BLUE, 3)
        _rationale_pages(pdf, max_frame, "Maximum Sharpe", BLUE, 4)
        _portfolio_breakdown_page(pdf, min_frame, min_metrics, "Minimum Volatility", TEAL, 6)
        _rationale_pages(pdf, min_frame, "Minimum Volatility", TEAL, 7)
        _methodology_page(pdf, max_frame, min_frame, max_metrics, min_metrics, 9)
        _allocation_appendix(pdf, max_frame, min_frame, 10)

    return output_path
