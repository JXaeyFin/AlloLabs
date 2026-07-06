"""Editorial PDF memo renderer for AlloLabs portfolio research."""

from __future__ import annotations

import math
import textwrap
from pathlib import Path

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch, Rectangle


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Color Palette & Module Constants
# Paper/editorial color scheme (off-white background, navy ink) contrasting with
# the dark terminal palette used in allolabs_report.py.
# ═══════════════════════════════════════════════════════════════════════════════

PAGE = "#F7F5F0"
PAPER = "#FFFFFF"
NAVY = "#12263A"
BLUE = "#315F85"
BLUE_LIGHT = "#DCE7F0"
GREEN = "#2F6B57"
GREEN_LIGHT = "#DCE9E3"
RED = "#A64B45"
GOLD = "#A8792A"
INK = "#17212B"
BODY = "#3E4A55"
MUTED = "#74808B"
GRID = "#D9DDD9"
PALE = "#ECEBE6"
RESOURCE_DIR = Path(__file__).resolve().parent / "resources"
COMPANY_LOGO_DIR = RESOURCE_DIR / "company-logos"
APPENDIX_MIN_WEIGHT = 0.00005
APPENDIX_ROWS = 38
_LOGO_CACHE = {}


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Industry Profile Library
# Each entry is a tuple of (keyword_match_tuple, display_name, earnings_driver,
# rate_sensitivity, portfolio_role, key_metrics_to_watch).
# Matched by lowercased industry string from yfinance; first match wins.
# ═══════════════════════════════════════════════════════════════════════════════

INDUSTRY_PROFILES = [
    (
        ("bank", "financial", "capital market"),
        "Banks and capital markets",
        "Earnings typically respond to net-interest margins, credit quality, loan growth, trading activity, and capital requirements.",
        "Moderately higher rates can support margins, but abrupt tightening may weaken borrowers and increase provisions. Recession risk and funding stress are the principal downside channels.",
        "A cyclical income sleeve that may diversify long-duration growth assets, although it is not defensive during a credit shock.",
        "Yield-curve shape, deposit costs, delinquencies, loan-loss provisions, and regulatory capital.",
    ),
    (
        ("insurance",),
        "Insurance",
        "Insurers combine underwriting results with returns earned on invested premiums. Pricing discipline and catastrophe losses often matter more than headline economic growth.",
        "Higher bond yields can improve reinvestment income over time, while severe claims inflation, catastrophe activity, or reserve deficiencies can offset that benefit.",
        "Often provides a different earnings engine from banks and technology, with sensitivity split between underwriting and fixed-income markets.",
        "Combined ratios, renewal pricing, reserve development, catastrophe losses, and portfolio yields.",
    ),
    (
        ("software", "information technology service", "internet content"),
        "Software and digital services",
        "Recurring revenue, retention, pricing, and operating leverage drive results. Valuation often embeds a long stream of expected future cash flows.",
        "Falling discount rates and durable growth generally help valuations. Higher rates, slower bookings, weak seat expansion, or elevated AI investment can compress multiples.",
        "A growth engine with scalable economics, balanced most naturally by cash-generative defensive or real-asset exposures.",
        "Annual recurring revenue, remaining performance obligations, net retention, margins, and free-cash-flow conversion.",
    ),
    (
        ("semiconductor", "computer hardware", "electronic"),
        "Semiconductors and hardware",
        "Demand is shaped by product cycles, capacity, inventory, capital expenditure, and end-market concentration. Earnings can move faster than revenue.",
        "AI and data-center investment can be powerful tailwinds, while inventory corrections, export restrictions, and customer concentration create sharp downside risk.",
        "Adds innovation and cyclical upside but usually increases sensitivity to capital-spending expectations and valuation changes.",
        "Bookings, inventory days, utilization, gross margin, foundry capacity, export controls, and customer concentration.",
    ),
    (
        ("oil", "gas", "energy", "petroleum", "exploration"),
        "Energy producers and infrastructure",
        "Cash flow is linked to commodity prices, production volumes, decline rates, transport capacity, and capital discipline.",
        "Rising oil and gas prices can create an inflation offset. Demand destruction, excess supply, political intervention, and high reinvestment needs are key risks.",
        "A real-asset sleeve that can offset inflation pressure on consumers and rate-sensitive equities, but adds commodity cyclicality.",
        "Benchmark prices, differentials, production guidance, reserve replacement, payout policy, and project execution.",
    ),
    (
        ("utility", "electric", "renewable"),
        "Utilities and regulated infrastructure",
        "Revenue is comparatively stable, but returns depend on regulation, financing costs, capital programs, and allowed returns on equity.",
        "Defensive demand can cushion growth shocks. Higher bond yields and funding costs often pressure valuations and project economics.",
        "A lower-beta ballast that can moderate cyclical sectors, though it may share duration risk with high-growth equities.",
        "Rate cases, allowed ROE, capital expenditure, debt refinancing, load growth, and weather normalization.",
    ),
    (
        ("pharma", "biotech", "medical", "health", "drug"),
        "Health care and life sciences",
        "Demand is generally less cyclical, while product pipelines, patents, reimbursement, regulation, and clinical outcomes drive company dispersion.",
        "Economic weakness is usually less damaging than for discretionary sectors. Patent cliffs, trial failures, pricing reform, and reimbursement changes remain material idiosyncratic risks.",
        "A defensive growth sleeve that can offset consumer and industrial cyclicality without relying exclusively on bond-like income.",
        "Pipeline milestones, patent exposure, reimbursement, procedure volumes, organic growth, and research productivity.",
    ),
    (
        ("consumer staple", "beverage", "food", "tobacco", "household"),
        "Consumer staples",
        "Demand is usually resilient, with earnings driven by pricing, volume, brand strength, input costs, and distribution.",
        "The group tends to hold up in slower growth, but inflation can squeeze margins when price increases lag commodity and labor costs.",
        "A defensive cash-flow sleeve that can offset discretionary demand and industrial cyclicality.",
        "Organic sales, price versus volume, gross margin, promotional intensity, input costs, and market share.",
    ),
    (
        ("retail", "restaurant", "auto", "travel", "luxury", "consumer discretionary"),
        "Consumer discretionary",
        "Results depend on household income, employment, credit availability, traffic, ticket size, and inventory execution.",
        "Lower rates and improving confidence can help demand. Inflation, unemployment, weak real wages, or excess inventory can quickly pressure margins.",
        "A cyclical growth sleeve that benefits from healthy consumers but needs defensive balance elsewhere in the portfolio.",
        "Comparable sales, traffic, average ticket, inventory, promotional activity, consumer credit, and margin guidance.",
    ),
    (
        ("industrial", "aerospace", "rail", "transport", "construction", "engineering"),
        "Industrials and transportation",
        "Order books, utilization, pricing, input costs, government programs, and capital spending are central to earnings.",
        "Infrastructure and reshoring can support demand. Recession, freight weakness, project delays, and cost overruns are major risks.",
        "A cyclical real-economy sleeve that can complement digital growth but remains exposed to business investment and trade.",
        "Backlog, book-to-bill, utilization, pricing, freight volumes, project margins, and capital-spending surveys.",
    ),
    (
        ("mining", "metal", "chemical", "material", "gold"),
        "Materials and mining",
        "Commodity prices, grade, volume, energy costs, project execution, and capital allocation drive highly variable cash flow.",
        "Inflation and supply constraints may support pricing, while slower global manufacturing and China-sensitive demand can pressure earnings.",
        "A tangible-asset and inflation-sensitive sleeve that can offset some nominal-growth risk, with meaningful commodity volatility.",
        "Realized prices, cost curves, production, reserve life, project budgets, and demand from construction and manufacturing.",
    ),
    (
        ("telecom", "media", "communication", "entertainment"),
        "Communications and media",
        "Subscriber economics, advertising, content spending, network investment, and competitive intensity determine cash generation.",
        "Connectivity can be defensive, while advertising and entertainment are cyclical. High leverage makes parts of the group rate-sensitive.",
        "A mixed sleeve: recurring subscriptions can stabilize returns, but media and platform exposures may behave like growth equities.",
        "Churn, average revenue per user, ad demand, content costs, network capex, and leverage.",
    ),
]


SECTOR_FALLBACKS = {
    "Financials": "Banks and capital markets",
    "Information Technology": "Software and digital services",
    "Energy": "Energy producers and infrastructure",
    "Utilities": "Utilities and regulated infrastructure",
    "Health Care": "Health care and life sciences",
    "Consumer Staples": "Consumer staples",
    "Consumer Discretionary": "Consumer discretionary",
    "Industrials": "Industrials and transportation",
    "Materials": "Materials and mining",
    "Communication Services": "Communications and media",
}


MACRO_FACTORS = {
    "Policy rates rise": {
        "Financials": 0.5, "Information Technology": -1.3, "Utilities": -1.5,
        "Consumer Discretionary": -0.9, "Communication Services": -0.7,
        "Industrials": -0.4, "Energy": 0.2, "Materials": -0.3,
        "Consumer Staples": -0.2, "Health Care": -0.2,
    },
    "Inflation reaccelerates": {
        "Energy": 1.8, "Materials": 1.6, "Financials": 0.3,
        "Consumer Staples": -0.5, "Consumer Discretionary": -1.0,
        "Industrials": -0.5, "Information Technology": -0.4,
    },
    "Economic growth slows": {
        "Consumer Staples": 1.4, "Health Care": 1.3, "Utilities": 1.1,
        "Consumer Discretionary": -1.5, "Industrials": -1.4,
        "Materials": -1.2, "Financials": -1.1, "Energy": -1.0,
        "Information Technology": -0.6, "Communication Services": -0.5,
    },
    "Commodity prices rise": {
        "Energy": 2.0, "Materials": 1.7, "Industrials": -0.4,
        "Consumer Discretionary": -0.8, "Consumer Staples": -0.6,
        "Utilities": -0.3,
    },
    "Risk appetite contracts": {
        "Consumer Staples": 0.9, "Health Care": 0.8, "Utilities": 0.7,
        "Information Technology": -1.3, "Consumer Discretionary": -1.1,
        "Communication Services": -0.9, "Financials": -0.7,
        "Industrials": -0.6, "Materials": -0.5,
    },
}


MICRO_FACTORS = {
    "Portfolio earnings miss": {
        "Information Technology": -1.6, "Consumer Discretionary": -1.4,
        "Communication Services": -1.2, "Industrials": -0.9,
        "Financials": -0.8, "Energy": -0.8, "Materials": -0.8,
        "Health Care": -0.6, "Consumer Staples": -0.4, "Utilities": -0.2,
    },
    "Operating margins compress": {
        "Consumer Discretionary": -1.5, "Industrials": -1.3,
        "Information Technology": -1.0, "Consumer Staples": -0.9,
        "Communication Services": -0.8, "Materials": -0.8,
    },
    "Capital spending accelerates": {
        "Industrials": 1.4, "Information Technology": 1.2, "Materials": 0.8,
        "Utilities": 0.5, "Financials": 0.2,
    },
    "Credit losses increase": {
        "Financials": -2.0, "Consumer Discretionary": -0.7,
        "Industrials": -0.4, "Real Estate": -1.2,
    },
    "Regulatory pressure rises": {
        "Financials": -1.1, "Health Care": -1.0,
        "Communication Services": -1.0, "Utilities": -0.7,
        "Information Technology": -0.6, "Energy": -0.5,
    },
}


HEDGE_RELATIONSHIPS = [
    ("Information Technology", "Utilities", "Growth duration versus regulated cash flow", "Utilities may cushion a growth slowdown, while technology provides upside when innovation spending and risk appetite improve. Both can still be hurt by sharply higher rates."),
    ("Information Technology", "Consumer Staples", "Secular growth versus defensive demand", "Staples demand is typically steadier when corporate or consumer activity weakens, offsetting part of technology's earnings and valuation sensitivity."),
    ("Consumer Discretionary", "Consumer Staples", "Elastic versus essential consumption", "Staples can absorb some weakness when household budgets tighten, while discretionary holdings participate more strongly in improving confidence and real income."),
    ("Energy", "Consumer Discretionary", "Commodity producer versus commodity consumer", "Higher energy prices can support producers while pressuring household spending and transport costs; falling prices can reverse the relationship."),
    ("Energy", "Utilities", "Inflation sensitivity versus defensive income", "Energy offers commodity upside; utilities offer steadier demand. The combination diversifies cash-flow drivers but can remain sensitive to financing costs."),
    ("Financials", "Utilities", "Rate beneficiary versus rate-sensitive income", "A measured increase in rates may aid bank margins while weighing on utilities. A credit shock can overwhelm that offset and hurt financials materially."),
    ("Financials", "Health Care", "Credit cycle versus defensive demand", "Health-care demand is less tied to lending and employment, providing a different earnings engine when credit conditions deteriorate."),
    ("Materials", "Consumer Staples", "Input-price exposure versus resilient demand", "Materials can benefit from commodity inflation, while staples provide steadier demand but may face input-cost pressure. Their economic sensitivities are distinct rather than perfectly inverse."),
    ("Industrials", "Health Care", "Capital cycle versus defensive growth", "Industrials depend on orders and utilization; health care relies more on clinical demand and product cycles, reducing dependence on one macro pathway."),
]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Utility & Layout Helpers
# Formatting, text wrapping, table, logo drawing, and primitive drawing
# functions shared by all memo page builders below.
# ═══════════════════════════════════════════════════════════════════════════════

def _safe_float(value, default=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _pct(value, decimals=1):
    return f"{_safe_float(value):.{decimals}%}"


def _wrap(value, width):
    return textwrap.wrap(str(value or ""), width=max(12, width), break_long_words=False) or [""]


def _portfolio_statistics(frame, metrics):
    weights = frame["weight"].astype(float).to_numpy()
    gross = float(np.abs(weights).sum())
    net = float(weights.sum())
    top_five = float(np.sort(np.abs(weights))[::-1][:5].sum())
    effective = 1.0 / float(np.square(weights).sum()) if np.any(weights) else 0.0
    shorts = float(np.abs(weights[weights < 0]).sum())
    return {
        "return": _safe_float(metrics.get("return")),
        "volatility": _safe_float(metrics.get("volatility")),
        "sharpe": _safe_float(metrics.get("sharpe")),
        "gross": gross,
        "net": net,
        "top_five": top_five,
        "effective": effective,
        "shorts": shorts,
        "positions": int((np.abs(weights) >= APPENDIX_MIN_WEIGHT).sum()),
    }


def _sector_exposure(frame):
    result = (
        frame.assign(abs_weight=frame["weight"].abs())
        .groupby("sector", as_index=False)["abs_weight"]
        .sum()
        .sort_values("abs_weight", ascending=False)
    )
    total = float(result["abs_weight"].sum())
    result["weight"] = result["abs_weight"] / total if total else 0.0
    return result[["sector", "weight"]].reset_index(drop=True)


def _industry_exposure(frame):
    working = frame.copy()
    working["industry_display"] = working.apply(
        lambda row: row["industry"]
        if str(row["industry"]).strip().lower() not in {"", "not classified", "none", "nan"}
        else f"{row['sector']} (broad)",
        axis=1,
    )
    result = (
        working.assign(abs_weight=working["weight"].abs())
        .groupby(["industry_display", "sector"], as_index=False)["abs_weight"]
        .sum()
        .sort_values("abs_weight", ascending=False)
    )
    total = float(result["abs_weight"].sum())
    result["weight"] = result["abs_weight"] / total if total else 0.0
    return result.rename(columns={"industry_display": "industry"})[["industry", "sector", "weight"]].reset_index(drop=True)


def _industry_profile(industry, sector):
    text = f"{industry} {sector}".lower()
    for keywords, title, behavior, sensitivity, role, watch in INDUSTRY_PROFILES:
        if any(keyword in text for keyword in keywords):
            return {"title": title, "behavior": behavior, "sensitivity": sensitivity, "role": role, "watch": watch}
    fallback = SECTOR_FALLBACKS.get(sector, f"{sector} companies")
    return {
        "title": fallback,
        "behavior": "Business results are shaped by demand, pricing, operating leverage, balance-sheet strength, and company-specific execution.",
        "sensitivity": "The group may respond to growth, financing conditions, input costs, and regulation; the direction and magnitude vary across issuers.",
        "role": "This exposure contributes another source of earnings, but its diversification value depends on the underlying companies and market regime.",
        "watch": "Revenue growth, margins, cash conversion, leverage, guidance, and major company-specific catalysts.",
    }


def _factor_score(sector_frame, factor_map):
    weights = dict(zip(sector_frame["sector"], sector_frame["weight"]))
    return sum(weights.get(sector, 0.0) * score for sector, score in factor_map.items())


def _score_label(score):
    if score >= 0.45:
        return "Potential beneficiary", GREEN
    if score >= 0.12:
        return "Mild support", GREEN
    if score <= -0.45:
        return "High sensitivity", RED
    if score <= -0.12:
        return "Moderate sensitivity", RED
    return "Mixed / limited", GOLD


def _company_logo(ticker):
    safe = str(ticker).upper()
    path = COMPANY_LOGO_DIR / f"{safe}.png"
    return path if path.is_file() else None


def _cropped_company_logo(ticker):
    """Load a logo once and remove transparent or near-white outer padding."""
    key = str(ticker).upper()
    if key in _LOGO_CACHE:
        return _LOGO_CACHE[key]
    path = _company_logo(key)
    if path is None:
        _LOGO_CACHE[key] = None
        return None
    image = mpimg.imread(path)
    rgb = image[..., :3] if image.ndim == 3 else np.repeat(image[..., None], 3, axis=2)
    if image.ndim == 3 and image.shape[2] >= 4:
        mask = image[..., 3] > 0.04
    else:
        mask = np.ones(rgb.shape[:2], dtype=bool)
    visible_ink = np.min(rgb, axis=2) < 0.965
    content = mask & visible_ink
    if content.sum() < max(16, content.size * 0.002):
        content = mask
    ys, xs = np.where(content)
    if len(xs):
        pad = max(3, int(max(xs.max() - xs.min(), ys.max() - ys.min()) * 0.07))
        left, right = max(0, xs.min() - pad), min(image.shape[1], xs.max() + pad + 1)
        top, bottom = max(0, ys.min() - pad), min(image.shape[0], ys.max() + pad + 1)
        image = image[top:bottom, left:right]
    _LOGO_CACHE[key] = image
    return image


def _draw_company_logo(fig, ticker, x, y, width=0.078):
    """Draw a physically square, rounded company mark with a vector fallback."""
    height = width * 8.5 / 11
    ax = fig.add_axes([x, y, width, height])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    frame = FancyBboxPatch(
        (0.01, 0.01), 0.98, 0.98,
        boxstyle="round,pad=0.01,rounding_size=0.13",
        facecolor=PAPER, edgecolor=GRID, linewidth=0.7,
        transform=ax.transAxes,
    )
    ax.add_patch(frame)
    image = _cropped_company_logo(ticker)
    if image is not None:
        artist = ax.imshow(image, extent=(0.09, 0.91, 0.09, 0.91), interpolation="lanczos", resample=True, zorder=2)
        artist.set_clip_path(frame)
    else:
        initials = "".join(part[:1] for part in str(ticker).split(".") if part)[:3]
        ax.text(0.5, 0.5, initials, ha="center", va="center", color=NAVY, fontsize=10, weight="bold")


class MemoBuilder:
    def __init__(self, pdf):
        self.pdf = pdf
        self.page_number = 0

    def page(self, section, title, subtitle=""):
        self.page_number += 1
        fig = plt.figure(figsize=(8.5, 11), facecolor=PAGE)
        fig.subplots_adjust(0, 0, 1, 1)
        fig.add_artist(Rectangle((0, 0.965), 1, 0.035, transform=fig.transFigure, color=NAVY, zorder=0))
        fig.text(0.06, 0.942, "ALLOLABS", color=BLUE, fontsize=8.5, weight="bold", family="sans-serif")
        fig.text(0.06, 0.914, section.upper(), color=MUTED, fontsize=7.3, weight="bold", family="sans-serif")
        fig.text(0.06, 0.875, title, color=NAVY, fontsize=22, weight="bold", family="sans-serif")
        if subtitle:
            fig.text(0.06, 0.842, subtitle, color=BODY, fontsize=9.2, family="sans-serif")
        fig.add_artist(Rectangle((0.06, 0.817), 0.88, 0.0012, transform=fig.transFigure, color=GRID))
        fig.text(0.06, 0.027, "ALLOLABS PORTFOLIO RESEARCH | EDUCATIONAL USE", color=MUTED, fontsize=6.8)
        fig.text(0.94, 0.027, str(self.page_number), color=MUTED, fontsize=7, ha="right")
        return fig

    def save(self, fig):
        self.pdf.savefig(fig, facecolor=PAGE)
        plt.close(fig)


def _paragraph(fig, x, y, text, width=100, size=9.1, color=BODY, leading=1.42, weight="normal"):
    lines = _wrap(text, width)
    line_height = size / 720 * leading
    fig.text(x, y, "\n".join(lines), color=color, fontsize=size, va="top", linespacing=leading, weight=weight)
    return y - line_height * len(lines)


def _bullets(fig, items, x, y, width=94, size=8.8, gap=0.012):
    for item in items:
        fig.text(x, y, "•", color=BLUE, fontsize=size + 1, weight="bold", va="top")
        y = _paragraph(fig, x + 0.022, y, item, width=width, size=size)
        y -= gap
    return y


def _small_label(fig, x, y, text, color=BLUE):
    fig.text(x, y, text.upper(), color=color, fontsize=7.2, weight="bold")


def _rule(fig, y, x=0.06, width=0.88, color=GRID):
    fig.add_artist(Rectangle((x, y), width, 0.001, transform=fig.transFigure, color=color))


def _table(ax, rows, columns, widths=None, header_color=NAVY, font_size=7.6, row_height=0.065):
    ax.axis("off")
    if not rows:
        rows = [["No additional positions"] + [""] * (len(columns) - 1)]
    table = ax.table(cellText=rows, colLabels=columns, loc="upper left", cellLoc="left", colLoc="left", colWidths=widths)
    table.auto_set_font_size(False)
    table.set_fontsize(font_size)
    for (row, column), cell in table.get_celld().items():
        cell.set_edgecolor(GRID)
        cell.set_linewidth(0.55)
        cell.set_height(row_height)
        cell.PAD = 0.045
        if row == 0:
            cell.set_facecolor(header_color)
            cell.get_text().set_color(PAPER)
            cell.get_text().set_weight("bold")
        else:
            cell.set_facecolor(PAPER if row % 2 else "#F0F2F1")
            cell.get_text().set_color(INK)
    return table


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Memo Page Builders
# One function per report page/section.  Assembled in order by
# create_investment_memo() at the bottom of this file.
# ═══════════════════════════════════════════════════════════════════════════════

def _cover(builder, training_start, training_end, max_stats, min_stats):
    builder.page_number += 1
    fig = plt.figure(figsize=(8.5, 11), facecolor=PAGE)
    fig.add_artist(Rectangle((0, 0), 1, 1, transform=fig.transFigure, color=PAGE))
    fig.add_artist(Rectangle((0, 0.82), 1, 0.18, transform=fig.transFigure, color=NAVY))
    logo = RESOURCE_DIR / "allolabs-logo.png"
    if logo.is_file():
        ax = fig.add_axes([0.065, 0.852, 0.09, 0.09])
        ax.set_zorder(10)
        ax.patch.set_alpha(0)
        ax.imshow(mpimg.imread(logo), interpolation="lanczos", resample=True)
        ax.axis("off")
    fig.text(0.175, 0.915, "ALLOLABS", color=PAPER, fontsize=20, weight="bold")
    fig.text(0.175, 0.875, "PORTFOLIO RESEARCH", color="#B9CAD9", fontsize=8.5, weight="bold")
    fig.text(0.07, 0.69, "Portfolio Allocation\nMemorandum", color=NAVY, fontsize=34, weight="bold", linespacing=1.08)
    fig.text(0.075, 0.605, "Comparative analysis of the Maximum Sharpe and Minimum Volatility portfolios", color=BODY, fontsize=11)
    fig.add_artist(Rectangle((0.075, 0.575), 0.17, 0.004, transform=fig.transFigure, color=BLUE))
    fig.text(0.075, 0.505, "ANALYSIS WINDOW", color=MUTED, fontsize=7.5, weight="bold")
    fig.text(0.075, 0.468, f"{training_start} to {training_end}", color=INK, fontsize=12, weight="bold")
    fig.text(0.075, 0.395, "PORTFOLIOS", color=MUTED, fontsize=7.5, weight="bold")
    fig.text(0.075, 0.355, "Maximum Sharpe", color=BLUE, fontsize=12, weight="bold")
    fig.text(0.30, 0.355, f"Model return {_pct(max_stats['return'])}  |  Risk {_pct(max_stats['volatility'])}", color=BODY, fontsize=9)
    fig.text(0.075, 0.315, "Minimum Volatility", color=GREEN, fontsize=12, weight="bold")
    fig.text(0.30, 0.315, f"Model return {_pct(min_stats['return'])}  |  Risk {_pct(min_stats['volatility'])}", color=BODY, fontsize=9)
    fig.text(0.075, 0.19, "Prepared as an educational model memo", color=INK, fontsize=9.5, weight="bold")
    fig.text(0.075, 0.158, "Expected returns are optimization inputs derived from the selected sample and research process. They are not promised or independently forecast investment returns.", color=MUTED, fontsize=8.2, wrap=True)
    fig.text(0.075, 0.07, "CONFIDENTIAL WORKING PAPER  |  NOT INVESTMENT ADVICE", color=MUTED, fontsize=7.2, weight="bold")
    builder.pdf.savefig(fig, facecolor=PAGE)
    plt.close(fig)


def _executive_memo(builder, max_stats, min_stats, max_sector, min_sector, top_industries):
    fig = builder.page("Executive memorandum", "Decision brief", "What the two allocations are designed to do, and what matters most")
    fig.text(0.06, 0.782, "TO", color=MUTED, fontsize=7, weight="bold")
    fig.text(0.14, 0.782, "Portfolio review committee", color=INK, fontsize=8.5)
    fig.text(0.06, 0.752, "FROM", color=MUTED, fontsize=7, weight="bold")
    fig.text(0.14, 0.752, "AlloLabs research system", color=INK, fontsize=8.5)
    fig.text(0.06, 0.722, "SUBJECT", color=MUTED, fontsize=7, weight="bold")
    fig.text(0.14, 0.722, "Allocation comparison and portfolio sensitivity review", color=INK, fontsize=8.5)
    _rule(fig, 0.695)
    y = 0.662
    y = _paragraph(
        fig, 0.06, y,
        "This memorandum compares two portfolios built from the same eligible asset universe. The Maximum Sharpe portfolio emphasizes the strongest modeled return-to-risk trade-off. The Minimum Volatility portfolio emphasizes covariance-based risk reduction. Neither allocation should be read as a prediction; each is a conditional expression of the inputs, constraints, and historical relationships available at the run date.",
        width=116, size=9.4,
    )
    y -= 0.025
    _small_label(fig, 0.06, y, "Principal observations")
    y -= 0.028
    max_dom = max_sector.iloc[0]
    min_dom = min_sector.iloc[0]
    bullets = [
        f"The Maximum Sharpe portfolio carries {_pct(max_stats['volatility'])} model volatility and a {_pct(max_stats['top_five'])} top-five concentration. Its largest sector is {max_dom['sector']} at {_pct(max_dom['weight'])} of gross sector exposure.",
        f"The Minimum Volatility portfolio carries {_pct(min_stats['volatility'])} model volatility with approximately {min_stats['effective']:.1f} effective holdings. Its largest sector is {min_dom['sector']} at {_pct(min_dom['weight'])}.",
        f"The largest industry allocations are {', '.join(item['industry'] for item in top_industries[:3])}. Their combined behavior determines much of the portfolio's sensitivity to rates, growth, commodity prices, and earnings delivery.",
        "The two portfolios are alternatives, not a ranking of good versus bad. The appropriate choice depends on tolerance for concentration, model uncertainty, turnover, and adverse macro regimes.",
    ]
    y = _bullets(fig, bullets, 0.065, y, width=107, size=8.8, gap=0.014)
    y -= 0.004
    _small_label(fig, 0.06, y, "Comparative exhibit")
    table_top = y - 0.022
    table_height = 0.225
    ax = fig.add_axes([0.06, max(0.085, table_top - table_height), 0.88, table_height])
    rows = [
        ["Modeled return input", _pct(max_stats["return"]), _pct(min_stats["return"])],
        ["Annualized model risk", _pct(max_stats["volatility"]), _pct(min_stats["volatility"])],
        ["Model Sharpe ratio", f"{max_stats['sharpe']:.2f}", f"{min_stats['sharpe']:.2f}"],
        ["Top-five absolute weight", _pct(max_stats["top_five"]), _pct(min_stats["top_five"])],
        ["Effective holdings", f"{max_stats['effective']:.1f}", f"{min_stats['effective']:.1f}"],
        ["Active positions", str(max_stats["positions"]), str(min_stats["positions"])],
    ]
    _table(ax, rows, ["Measure", "Maximum Sharpe", "Minimum Volatility"], widths=[0.46, 0.27, 0.27], font_size=8.0, row_height=0.095)
    builder.save(fig)


def _process_page(builder):
    fig = builder.page("Process", "How the portfolio is constructed", "A simplified view of the analytical chain")
    y = 0.775
    intro = "The process converts a broad equity universe into two constrained portfolios. Each stage has a distinct purpose, and each introduces assumptions that must be monitored rather than hidden."
    y = _paragraph(fig, 0.06, y, intro, width=114, size=9.4)
    y -= 0.025
    stages = [
        ("01", "Define the opportunity set", "Select eligible securities, currencies, listings, and the training window. Missing or low-quality data are removed before optimization."),
        ("02", "Estimate market relationships", "Calculate historical returns and covariance. These estimates describe the sample; they do not guarantee that future relationships will remain stable."),
        ("03", "Form conditional return inputs", "Blend equilibrium information with optional AI-assisted company views and confidence levels through the Black-Litterman framework."),
        ("04", "Apply portfolio controls", "Impose long-only or long/short rules, position caps, sector limits, and optional regularization before solving with SLSQP."),
        ("05", "Compare and monitor", "Review concentration, industry exposures, sensitivities, and out-of-sample evidence. Re-run when inputs or the investment thesis materially change."),
    ]
    for number, heading, body in stages:
        fig.text(0.065, y, number, color=BLUE, fontsize=16, weight="bold", va="top")
        fig.text(0.14, y, heading, color=NAVY, fontsize=10.5, weight="bold", va="top")
        y = _paragraph(fig, 0.14, y - 0.027, body, width=91, size=8.5)
        y -= 0.023
        if number != "05":
            fig.add_artist(Rectangle((0.082, y + 0.006), 0.002, 0.021, transform=fig.transFigure, color=GRID))
    _rule(fig, 0.145)
    _small_label(fig, 0.06, 0.119, "Interpretive discipline", color=GOLD)
    _paragraph(fig, 0.06, 0.092, "The report separates measured exposure from inferred behavior. Factor sensitivities and hedge relationships are qualitative diagnostics based on sector and industry structure; they are not substitute estimates for a full scenario model, option exposure analysis, or forward covariance forecast.", width=118, size=8.1, color=MUTED)
    builder.save(fig)


def _comparison_page(builder, max_frame, min_frame, max_stats, min_stats, max_sector, min_sector):
    fig = builder.page("Portfolio exhibits", "Allocation comparison", "Concentration, position structure, and sector composition")
    _small_label(fig, 0.06, 0.785, "Exhibit 1 | Largest absolute positions")
    for left, frame, color, name in [(0.06, max_frame, BLUE, "Maximum Sharpe"), (0.525, min_frame, GREEN, "Minimum Volatility")]:
        top = frame.head(10).iloc[::-1]
        ax = fig.add_axes([left, 0.49, 0.415, 0.255], facecolor=PAGE)
        ax.barh(top["ticker"], top["weight"].abs() * 100, color=color, height=0.62)
        ax.set_title(name, loc="left", color=NAVY, fontsize=10, weight="bold", pad=10)
        ax.grid(axis="x", color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        ax.tick_params(axis="both", labelsize=7.2, colors=BODY, length=0)
        ax.set_xlabel("Absolute portfolio weight (%)", fontsize=7.2, color=MUTED)
        for spine in ax.spines.values():
            spine.set_visible(False)
    _small_label(fig, 0.06, 0.445, "Exhibit 2 | Sector exposure")
    sectors = sorted(set(max_sector["sector"]) | set(min_sector["sector"]))
    max_map = dict(zip(max_sector["sector"], max_sector["weight"]))
    min_map = dict(zip(min_sector["sector"], min_sector["weight"]))
    y_pos = np.arange(len(sectors))
    ax = fig.add_axes([0.16, 0.17, 0.74, 0.23], facecolor=PAGE)
    ax.barh(y_pos + 0.18, [max_map.get(item, 0) * 100 for item in sectors], height=0.34, color=BLUE, label="Maximum Sharpe")
    ax.barh(y_pos - 0.18, [min_map.get(item, 0) * 100 for item in sectors], height=0.34, color=GREEN, label="Minimum Volatility")
    ax.set_yticks(y_pos, sectors)
    ax.tick_params(axis="both", labelsize=7.1, colors=BODY, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_xlabel("Share of gross sector exposure (%)", fontsize=7.2, color=MUTED)
    ax.legend(frameon=False, fontsize=7.2, loc="lower right")
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.text(0.06, 0.11, f"Maximum Sharpe: {_pct(max_stats['top_five'])} in the five largest positions; {max_stats['effective']:.1f} effective holdings.", color=BODY, fontsize=8.2)
    fig.text(0.06, 0.082, f"Minimum Volatility: {_pct(min_stats['top_five'])} in the five largest positions; {min_stats['effective']:.1f} effective holdings.", color=BODY, fontsize=8.2)
    builder.save(fig)


def _industry_overview_page(builder, max_industry, min_industry):
    fig = builder.page("Industry analysis", "Industry allocation", "Where the portfolios concentrate their underlying business exposure")
    combined = pd.merge(
        max_industry[["industry", "sector", "weight"]],
        min_industry[["industry", "sector", "weight"]],
        on=["industry", "sector"], how="outer", suffixes=("_max", "_min"),
    ).fillna(0.0)
    combined["combined"] = (combined["weight_max"] + combined["weight_min"]) / 2
    combined = combined.sort_values("combined", ascending=False).head(15).iloc[::-1]
    ax = fig.add_axes([0.25, 0.34, 0.67, 0.43], facecolor=PAGE)
    y_pos = np.arange(len(combined))
    ax.barh(y_pos + 0.18, combined["weight_max"] * 100, height=0.34, color=BLUE, label="Maximum Sharpe")
    ax.barh(y_pos - 0.18, combined["weight_min"] * 100, height=0.34, color=GREEN, label="Minimum Volatility")
    ax.set_yticks(y_pos, combined["industry"])
    ax.tick_params(axis="both", labelsize=6.8, colors=BODY, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_xlabel("Share of gross industry exposure (%)", fontsize=7.2, color=MUTED)
    ax.legend(frameon=False, fontsize=7.4, loc="lower right")
    for spine in ax.spines.values():
        spine.set_visible(False)
    _small_label(fig, 0.06, 0.285, "Interpretation")
    y = _paragraph(fig, 0.06, 0.257, "Industry exposure is calculated from absolute position weights, then normalized within each portfolio. This view reveals the business drivers beneath broad sector labels. A concentrated industry can dominate portfolio behavior even when the sector total appears diversified.", width=116, size=8.8)
    y -= 0.015
    _small_label(fig, 0.06, y, "Reading the exhibit", color=GOLD)
    _bullets(fig, [
        "Long and short positions both contribute to gross exposure; direction still matters when interpreting a specific security.",
        "Industry labels come from stored company research and fall back to the broader sector when detailed classification is unavailable.",
        "The next section describes the three largest combined industry exposures and their usual sensitivities.",
    ], 0.065, y - 0.028, width=108, size=8.2, gap=0.009)
    builder.save(fig)
    return combined.iloc[::-1].head(3).to_dict("records")


def _industry_profiles_page(builder, top_industries):
    for rank, item in enumerate(top_industries, start=1):
        profile = _industry_profile(item["industry"], item["sector"])
        fig = builder.page(
            "Industry analysis",
            f"{rank}. {profile['title']}",
            f"{item['industry']} | {item['sector']} | Exposure and operating sensitivity",
        )
        fig.text(0.06, 0.785, "Industry exposure profile", color=NAVY, fontsize=13, weight="bold")
        fig.text(0.06, 0.755, "STRUCTURAL EXPOSURE", color=BLUE, fontsize=7, weight="bold")
        max_weight = _safe_float(item.get("weight_max"))
        min_weight = _safe_float(item.get("weight_min"))
        ax = fig.add_axes([0.06, 0.655, 0.44, 0.08])
        ax.barh([0.67, 0.25], [max_weight * 100, min_weight * 100], height=0.25, color=[BLUE, GREEN])
        ax.set_xlim(0, max(max_weight, min_weight, 0.01) * 115)
        ax.axis("off")
        fig.text(0.53, 0.708, f"Maximum Sharpe  {_pct(max_weight)}", color=BLUE, fontsize=8.5, weight="bold")
        fig.text(0.53, 0.674, f"Minimum Volatility  {_pct(min_weight)}", color=GREEN, fontsize=8.5, weight="bold")
        fig.text(0.53, 0.640, f"Average gross signal  {_pct(item['combined'])}", color=MUTED, fontsize=7.6)
        _rule(fig, 0.61)
        y = 0.575
        for label, value, color in [
            ("GENERAL BEHAVIOR", profile["behavior"], BLUE),
            ("PRIMARY SENSITIVITIES", profile["sensitivity"], GOLD),
            ("ROLE IN THIS PORTFOLIO", profile["role"], BLUE),
            ("INDICATORS TO WATCH", profile["watch"], BLUE),
        ]:
            fig.text(0.06, y, label, color=color, fontsize=7, weight="bold", va="top")
            y = _paragraph(fig, 0.27, y, value, width=83, size=8.6)
            y -= 0.025
        _rule(fig, 0.17)
        fig.text(0.06, 0.14, "COMMITTEE INTERPRETATION", color=GOLD, fontsize=7, weight="bold")
        _paragraph(
            fig,
            0.27,
            0.14,
            "Treat this profile as a monitoring framework, not a forecast. Company-specific balance sheets, geographic exposure, valuation, catalysts, and position direction can materially alter the portfolio outcome.",
            width=83,
            size=8.1,
            color=MUTED,
        )
        builder.save(fig)


def _hedge_page(builder, max_sector, min_sector):
    fig = builder.page("Portfolio interaction", "Structural offsets within the portfolios", "Which exposures may hedge one another, by how much, and why")
    max_map = dict(zip(max_sector["sector"], max_sector["weight"]))
    min_map = dict(zip(min_sector["sector"], min_sector["weight"]))
    relationships = []
    for first, second, label, explanation in HEDGE_RELATIONSHIPS:
        a = (max_map.get(first, 0.0) + min_map.get(first, 0.0)) / 2
        b = (max_map.get(second, 0.0) + min_map.get(second, 0.0)) / 2
        if min(a, b) < 0.01:
            continue
        balance = min(a, b) / max(a, b) if max(a, b) else 0.0
        relationships.append((min(a, b), balance, first, second, a, b, label, explanation))
    relationships.sort(reverse=True)
    relationships = relationships[:4]
    if not relationships:
        relationships = [(0, 0, "Diversifying sectors", "Other sectors", 0, 0, "Limited structural offset identified", "The current sector mix does not contain a large predefined pairing. Diversification therefore depends more heavily on security-level covariance and position sizing.")]
    y = 0.785
    y = _paragraph(fig, 0.06, y, "A hedge is not assumed merely because two industries are different. The pairings below are structural offsets: they respond to distinct economic channels and may reduce dependence on one scenario. They can still decline together during broad market stress.", width=116, size=9.0)
    y -= 0.025
    for index, (_, balance, first, second, a, b, label, explanation) in enumerate(relationships, start=1):
        strength = "strongly balanced" if balance >= 0.65 else "moderately balanced" if balance >= 0.35 else "asymmetrically balanced"
        fig.text(0.06, y, f"{index}. {label}", color=NAVY, fontsize=10.5, weight="bold", va="top")
        fig.text(0.94, y, strength.upper(), color=GREEN if balance >= 0.35 else GOLD, fontsize=6.8, weight="bold", ha="right", va="top")
        y -= 0.031
        fig.text(0.065, y, f"{first}  {_pct(a)}", color=BLUE, fontsize=7.8, weight="bold", va="top")
        fig.text(0.34, y, f"{second}  {_pct(b)}", color=GREEN, fontsize=7.8, weight="bold", va="top")
        y -= 0.029
        y = _paragraph(fig, 0.065, y, explanation, width=112, size=7.8, leading=1.34)
        y -= 0.021
        _rule(fig, y, x=0.06, width=0.88)
        y -= 0.026
    fig.text(0.06, 0.075, "Sizing note: percentages are the average gross sector shares across the two portfolios. Balance describes relative sleeve size, not a statistical hedge ratio.", color=MUTED, fontsize=7.3)
    builder.save(fig)


def _sensitivity_page(builder, max_sector, min_sector, factors, title, subtitle, section):
    fig = builder.page(section, title, subtitle)
    rows = []
    for factor, mapping in factors.items():
        max_score = _factor_score(max_sector, mapping)
        min_score = _factor_score(min_sector, mapping)
        max_label, _ = _score_label(max_score)
        min_label, _ = _score_label(min_score)
        rows.append((factor, max_score, max_label, min_score, min_label))
    ax = fig.add_axes([0.06, 0.49, 0.88, 0.29])
    _table(
        ax,
        [[factor, f"{score_max:+.2f}", label_max, f"{score_min:+.2f}", label_min] for factor, score_max, label_max, score_min, label_min in rows],
        ["Indicator / shock", "Max score", "Max interpretation", "Min score", "Min interpretation"],
        widths=[0.27, 0.11, 0.23, 0.11, 0.23], font_size=7.2, row_height=0.13,
    )
    _small_label(fig, 0.06, 0.435, "Largest modeled leverage")
    max_worst = min(rows, key=lambda item: item[1])
    min_worst = min(rows, key=lambda item: item[3])
    y = 0.403
    y = _paragraph(fig, 0.06, y, f"Maximum Sharpe: {max_worst[0]} is the largest adverse structural sensitivity in this set (score {max_worst[1]:+.2f}). The reading follows from the current sector mix and does not estimate the size of a market loss.", width=112, size=8.8)
    y -= 0.018
    y = _paragraph(fig, 0.06, y, f"Minimum Volatility: {min_worst[0]} is the largest adverse structural sensitivity in this set (score {min_worst[3]:+.2f}). Lower covariance-based volatility does not remove event or fundamental risk.", width=112, size=8.8)
    y -= 0.022
    _small_label(fig, 0.06, y, "How to use the scores", color=GOLD)
    _bullets(fig, [
        "Scores range approximately from -2 to +2 and aggregate hardcoded sector sensitivities using current gross sector weights.",
        "Negative values indicate potential vulnerability; positive values indicate potential support. Values near zero indicate mixed or limited portfolio-level exposure.",
        "These diagnostics help prioritize monitoring and scenario analysis. They are not return forecasts, stress-test losses, or causal estimates.",
    ], 0.065, y - 0.028, width=108, size=8.2, gap=0.01)
    builder.save(fig)


def _security_brief_pages(builder, max_frame, min_frame):
    max_weights = dict(zip(max_frame["ticker"], max_frame["weight"]))
    min_weights = dict(zip(min_frame["ticker"], min_frame["weight"]))
    candidates = pd.concat([max_frame.head(8), min_frame.head(8)], ignore_index=True)
    candidates["importance"] = candidates["ticker"].map(lambda ticker: max(abs(max_weights.get(ticker, 0)), abs(min_weights.get(ticker, 0))))
    candidates = candidates.sort_values("importance", ascending=False).drop_duplicates("ticker").head(9)
    rows = candidates.to_dict("records")
    chunks = []
    current, used = [], 0.0
    for row in rows:
        summary = row.get("view") or "No AI research summary was stored for this security in the completed run. Interpret the allocation using the measured weight, sector exposure, and underlying source data."
        lines = _wrap(summary, 90)
        if len(lines) > 11:
            lines = lines[:10] + ["The complete summary remains available in the stored run data."]
        row["_summary_lines"] = lines
        estimated = 0.142 + len(lines) * (8.3 / 720 * 1.38)
        if current and (len(current) >= 3 or used + estimated > 0.64):
            chunks.append(current)
            current, used = [], 0.0
        current.append(row)
        used += estimated
    if current or not chunks:
        chunks.append(current)
    completed = 0
    for page_index, chunk in enumerate(chunks, start=1):
        fig = builder.page("Security analysis", f"Leading security briefs {page_index}", "Largest positions across both portfolios, with stored AI research summaries")
        y = 0.79
        for rank, row in enumerate(chunk, start=completed + 1):
            _draw_company_logo(fig, row["ticker"], 0.06, y - 0.06)
            fig.text(0.155, y, f"{rank:02d}  {row['ticker']}", color=NAVY, fontsize=13, weight="bold", va="top")
            fig.text(0.155, y - 0.026, f"{row['sector']}  |  {row['industry']}", color=MUTED, fontsize=7.5, va="top")
            fig.text(0.94, y, f"MAX {_pct(max_weights.get(row['ticker'], 0))}   MIN {_pct(min_weights.get(row['ticker'], 0))}", color=BLUE, fontsize=7.3, weight="bold", ha="right", va="top")
            y -= 0.074
            y = _paragraph(fig, 0.155, y, " ".join(row["_summary_lines"]), width=86, size=8.3, leading=1.38)
            posterior = row.get("posterior_return")
            confidence = row.get("confidence")
            detail = f"Posterior input: {_pct(posterior) if pd.notna(posterior) else 'N/A'}  |  Research confidence: {_pct(confidence, 0) if pd.notna(confidence) else 'N/A'}"
            fig.text(0.155, y - 0.008, detail, color=GOLD, fontsize=7.1, weight="bold")
            y -= 0.05
            if rank < completed + len(chunk):
                _rule(fig, y, x=0.155, width=0.785)
                y -= 0.03
        completed += len(chunk)
        fig.text(0.06, 0.075, "AI summaries are research inputs, not verified company guidance. Review source fundamentals and current disclosures before relying on any statement.", color=MUTED, fontsize=7.3)
        builder.save(fig)


def _conclusion_page(builder, max_stats, min_stats, macro_rows, micro_rows):
    fig = builder.page("Conclusion", "Portfolio interpretation", "A concise synthesis of the allocation, its trade-offs, and the next monitoring priorities")
    y = 0.785
    y = _paragraph(fig, 0.06, y, "The Maximum Sharpe and Minimum Volatility portfolios express different objectives from the same analytical foundation. The first accepts more concentration and model dependence in pursuit of a stronger return-to-risk input. The second gives greater weight to covariance-based stability. The report does not establish that either portfolio will outperform; it clarifies what each portfolio is asking the market to deliver.", width=116, size=9.3)
    y -= 0.025
    _small_label(fig, 0.06, y, "Key conclusions")
    y = _bullets(fig, [
        f"Maximum Sharpe combines {_pct(max_stats['volatility'])} model risk with {_pct(max_stats['top_five'])} in its five largest absolute positions. Its outcome is more dependent on concentrated security and industry theses.",
        f"Minimum Volatility reduces modeled risk to {_pct(min_stats['volatility'])} and distributes exposure across approximately {min_stats['effective']:.1f} effective holdings, but remains vulnerable to regime shifts in covariance and defensive-sector valuation.",
        "Industry pairings provide partial structural offsets, not guaranteed hedges. Broad liquidity shocks, valuation compression, and correlated earnings revisions can overwhelm normal diversification relationships.",
        "The highest-priority monitoring items are the most adverse macro and micro sensitivity scores, top-holding earnings delivery, sector cap utilization, and changes in the assumptions embedded in AI views.",
    ], 0.065, y - 0.03, width=108, size=8.7, gap=0.014)
    y -= 0.008
    _small_label(fig, 0.06, y, "Practical review triggers", color=GOLD)
    y = _bullets(fig, [
        "A material change in rates, inflation, credit conditions, or commodity prices relative to the assumptions used at the run date.",
        "A top holding issues guidance or results that invalidate the stored research rationale or materially change free-cash-flow expectations.",
        "Concentration rises because of market movement, or a sector/position approaches its hard limit.",
        "Out-of-sample behavior diverges from the covariance structure used to construct the portfolio.",
        "The investment committee's risk tolerance, horizon, liquidity needs, or permitted universe changes.",
    ], 0.065, y - 0.03, width=108, size=8.4, gap=0.011)
    _rule(fig, 0.125)
    fig.text(0.06, 0.095, "BOTTOM LINE", color=BLUE, fontsize=7.2, weight="bold")
    fig.text(0.16, 0.095, "Use the portfolios as disciplined starting points for review, not as automatic trading instructions.", color=NAVY, fontsize=9.2, weight="bold")
    builder.save(fig)


def _methodology_page(builder, max_stats, min_stats):
    fig = builder.page("Appendix", "Methodology and limitations", "What the report measures, what it infers, and what it does not claim")
    sections = [
        ("Return inputs", "Portfolio returns shown in this report are optimizer inputs derived from the selected training sample and optional Black-Litterman research views. They are not realized-return forecasts, guarantees, or independently calibrated capital-market assumptions."),
        ("Risk model", "Annualized volatility and diversification statistics depend on the covariance estimate used in the completed run. Correlations can rise during stress, and historical covariance may not represent the next regime."),
        ("Industry and factor interpretation", "Industry profiles, hedge relationships, and sensitivity scores are deterministic educational diagnostics based on current gross exposure and hardcoded behavioral mappings. They do not estimate loss magnitude or statistical hedge ratios."),
        ("AI research", "Stored AI opinions summarize supplied fundamentals and news context. They can be incomplete, stale, or incorrect. Confidence scores represent model-assigned research confidence, not probability of positive returns."),
        ("Portfolio implementation", "Weights omit taxes, commissions, bid-ask spreads, market impact, account constraints, and investor-specific suitability unless separately represented in the optimization configuration."),
        ("Use of this memorandum", "The document is intended for research and education. It should be paired with current issuer disclosures, independent data verification, scenario analysis, and professional judgment."),
    ]
    y = 0.785
    for heading, body in sections:
        fig.text(0.06, y, heading, color=NAVY, fontsize=9.5, weight="bold", va="top")
        y = _paragraph(fig, 0.06, y - 0.025, body, width=116, size=8.3)
        y -= 0.018
        _rule(fig, y + 0.008)
    diagnostics_y = max(0.085, y - 0.01)
    fig.text(0.06, diagnostics_y, "RUN DIAGNOSTICS", color=BLUE, fontsize=7.2, weight="bold")
    fig.text(0.25, diagnostics_y, f"Maximum Sharpe: gross {_pct(max_stats['gross'])}, net {_pct(max_stats['net'])}, short sleeve {_pct(max_stats['shorts'])}.", color=BODY, fontsize=7.8)
    fig.text(0.25, diagnostics_y - 0.027, f"Minimum Volatility: gross {_pct(min_stats['gross'])}, net {_pct(min_stats['net'])}, short sleeve {_pct(min_stats['shorts'])}.", color=BODY, fontsize=7.8)
    builder.save(fig)


def _allocation_appendix(builder, max_frame, min_frame):
    max_rows = max_frame[max_frame["weight"].abs() >= APPENDIX_MIN_WEIGHT].copy()
    min_rows = min_frame[min_frame["weight"].abs() >= APPENDIX_MIN_WEIGHT].copy()
    for frame, name, color in [
        (max_rows, "Maximum Sharpe", BLUE),
        (min_rows, "Minimum Volatility", GREEN),
    ]:
        total_pages = max(1, math.ceil(len(frame) / APPENDIX_ROWS))
        for index in range(total_pages):
            start = index * APPENDIX_ROWS
            chunk = frame.iloc[start:start + APPENDIX_ROWS]
            fig = builder.page(
                "Appendix",
                f"{name} allocation schedule {index + 1}/{total_pages}",
                "All positions with absolute portfolio weight of at least 0.005%",
            )
            ax = fig.add_axes([0.06, 0.09, 0.88, 0.70])
            rows = [
                [
                    str(start + rank),
                    row.ticker,
                    str(row.sector)[:28],
                    str(row.industry)[:37],
                    f"{row.weight:.3%}",
                    _pct(row.posterior_return) if pd.notna(row.posterior_return) else "N/A",
                ]
                for rank, row in enumerate(chunk.itertuples(), start=1)
            ]
            _table(
                ax,
                rows,
                ["Rank", "Ticker", "Sector", "Industry", "Weight", "BL input"],
                widths=[0.07, 0.12, 0.22, 0.33, 0.13, 0.13],
                header_color=color,
                font_size=6.3,
                row_height=0.024,
            )
            builder.save(fig)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Main Entry Point
# create_investment_memo() is the only public function.  It orchestrates all
# memo page builders in sequence and writes the final PDF.
# ═══════════════════════════════════════════════════════════════════════════════

def create_investment_memo(
    output_path,
    max_frame,
    min_frame,
    max_metrics,
    min_metrics,
    training_start,
    training_end,
):
    """Write the complete AlloLabs investment memorandum."""
    output_path = Path(output_path)
    max_stats = _portfolio_statistics(max_frame, max_metrics)
    min_stats = _portfolio_statistics(min_frame, min_metrics)
    max_sector = _sector_exposure(max_frame)
    min_sector = _sector_exposure(min_frame)
    max_industry = _industry_exposure(max_frame)
    min_industry = _industry_exposure(min_frame)

    metadata = {
        "Title": "AlloLabs Portfolio Allocation Memorandum",
        "Author": "AlloLabs",
        "Subject": "Educational portfolio allocation, industry, and sensitivity analysis",
        "Keywords": "portfolio allocation, Black-Litterman, industry exposure, risk sensitivity, model memo",
    }
    with PdfPages(output_path, metadata=metadata) as pdf:
        builder = MemoBuilder(pdf)
        _cover(builder, training_start, training_end, max_stats, min_stats)
        provisional = pd.merge(
            max_industry, min_industry, on=["industry", "sector"], how="outer", suffixes=("_max", "_min")
        ).fillna(0.0)
        provisional["combined"] = (provisional["weight_max"] + provisional["weight_min"]) / 2
        top_industries = provisional.sort_values("combined", ascending=False).head(3).to_dict("records")
        _executive_memo(builder, max_stats, min_stats, max_sector, min_sector, top_industries)
        _process_page(builder)
        _comparison_page(builder, max_frame, min_frame, max_stats, min_stats, max_sector, min_sector)
        top_industries = _industry_overview_page(builder, max_industry, min_industry)
        _industry_profiles_page(builder, top_industries)
        _hedge_page(builder, max_sector, min_sector)
        _sensitivity_page(builder, max_sector, min_sector, MACRO_FACTORS, "Macro sensitivity map", "How rates, inflation, growth, commodities, and risk appetite may influence the current sector mix", "Risk assessment")
        _sensitivity_page(builder, max_sector, min_sector, MICRO_FACTORS, "Micro sensitivity map", "How earnings, margins, capital spending, credit, and regulation may transmit through holdings", "Risk assessment")
        _security_brief_pages(builder, max_frame, min_frame)
        _conclusion_page(builder, max_stats, min_stats, MACRO_FACTORS, MICRO_FACTORS)
        _methodology_page(builder, max_stats, min_stats)
        _allocation_appendix(builder, max_frame, min_frame)
    return output_path
