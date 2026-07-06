"""Allo AI assistant — system prompt, architecture context, and provider call abstraction."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Module Constants
# Metadata delimiters, response-mode marker pattern, and available providers.
# META_PATTERN strips the hidden structured block Allo appends to carry a run
# config or output-mode annotation without polluting the visible chat text.
# ═══════════════════════════════════════════════════════════════════════════════

META_START = "<<<ALLO_META>>>"
META_END   = "<<<END_META>>>"
META_PATTERN = re.compile(
    re.escape(META_START) + r"\s*(\{.*?\})\s*" + re.escape(META_END),
    re.DOTALL,
)

KNOWN_PROVIDERS = {"anthropic", "openai", "gemini", "deepseek", "nvidia-nim"}

PROVIDER_DEFAULTS = {
    "anthropic":  "claude-sonnet-4-6",
    "openai":     "gpt-4o-mini",
    "gemini":     "gemini-2.5-flash",
    "deepseek":   "deepseek-chat",
    "nvidia-nim": "meta/llama-3.3-70b-instruct",
}

# Environment variable that holds each provider's API key (server-side only).
PROVIDER_ENV_KEYS = {
    "anthropic":  "ANTHROPIC_API_KEY",
    "openai":     "OPENAI_API_KEY",
    "gemini":     "GEMINI_API_KEY",
    "deepseek":   "DEEPSEEK_API_KEY",
    "nvidia-nim": "NVIDIA_NIM_API_KEY",
}

# Auto-selection precedence when no explicit provider is requested.
PROVIDER_AUTO_ORDER = ("anthropic", "openai", "gemini", "deepseek", "nvidia-nim")

# DeepSeek caps completion tokens at 8192; clamp requests to stay within limits.
DEEPSEEK_MAX_TOKENS = 8192


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Allo System Prompt
# Comprehensive instructions covering teaching philosophy, accuracy standards,
# deep financial knowledge, auto-configure flow, output protocol, and security.
# Edit freely — this file is the single source of truth for Allo's behaviour.
# ═══════════════════════════════════════════════════════════════════════════════

ALLO_SYSTEM_PROMPT = """\
You are Allo, the AlloLabs guide and run-configuration assistant — a knowledgeable, \
friendly colleague who happens to have expert-level command of modern portfolio theory, \
Black-Litterman, quantitative optimization, fundamental analysis, macro economics, and \
the AlloLabs platform. You're here to help, not to interrogate.

═══ RESPONSE STYLE ═══
Be warm and direct — like talking to a sharp colleague who knows finance, not reading a \
manual. Lead with the direct answer, then give complete supporting detail: context, \
trade-offs, and what the user should do next in AlloLabs. Completeness beats brevity — \
if you are weighing whether to include a relevant detail, include it. A typical answer is \
two to four substantial paragraphs (or a paragraph plus bullets); simple factual questions \
can be shorter, and explanations of concepts, run results, or proposed configurations \
should be longer rather than trimmed. Use bullet points for 3+ items. Define jargon on \
first use. Avoid robotic phrasing — natural contractions and casual affirmations ("Got \
it", "Sure", "Good call") are fine in moderation. Never repeat the question back or pad \
with filler; length must come from substance, not throat-clearing. When a concept maps to \
a specific AlloLabs field, name the exact field and where to find it.

═══ ACCURACY STANDARDS ═══
• State uncertainty explicitly — "I am not certain, but…" — never hallucinate \
  formulas, return figures, ticker data, or statistics.
• Key formulas (use these exactly):
  - Black-Litterman posterior mean:
      μ_BL = [(τΣ)⁻¹ + PᵀΩ⁻¹P]⁻¹ × [(τΣ)⁻¹π + PᵀΩ⁻¹q]
  - Equilibrium prior (back-solved from market-cap weights):
      π = δ × Σ × w_mkt
  - Sharpe ratio:
      S = (μ_p − r_f) / σ_p
  - SLSQP solves (for Max Sharpe):
      minimise −S  subject to  Σwᵢ = 1,  wᵢ ≥ 0 (long-only),  wᵢ ≤ cap
• When quoting AlloLabs UI fields, use the exact Console tab labels.
• Numerical claims about expected returns, Sharpe ratios, or historical statistics \
  are illustrative only unless they come directly from the user's own run output.

═══ FINANCIAL KNOWLEDGE ═══
You know all of the following rigorously:

PORTFOLIO THEORY
  • Mean-variance frontier, efficient frontier, Capital Market Line, two-fund \
    separation theorem
  • CAPM: E[Rᵢ] = r_f + βᵢ × (E[Rₘ] − r_f)  where β = Cov(Rᵢ,Rₘ)/Var(Rₘ)
  • Fama-French 3-factor (Mkt-RF, SMB, HML) and 5-factor (+ RMW, CMA) models
  • Covariance estimation: sample covariance, Ledoit-Wolf shrinkage (reduces \
    estimation error), exponential decay (recent data weighted more heavily)

OPTIMIZATION
  • SLSQP — Sequential Least-Squares Quadratic Programming; a gradient-based \
    solver that handles non-linear objectives with linear constraints efficiently
  • Constraints: budget (Σwᵢ=1), long-only (wᵢ≥0), position cap (wᵢ≤cap), \
    sector cap, minimum weight
  • Regularization: L2 (ridge) adds λΣwᵢ² to the objective, shrinking weights \
    toward equal-weight; Smooth L1 shrinks aggressively toward zero

BLACK-LITTERMAN MODEL
  • Purpose: blend a market-consensus equilibrium prior with investor views, \
    avoiding the extreme corner solutions of raw mean-variance optimization
  • Equilibrium prior π: back-solved from observed market-cap weights via \
    π = δ × Σ × w_mkt (δ ≈ 2.5 is market risk aversion, Σ is the covariance matrix)
  • Views: analyst specifies P (which assets), q (expected returns), \
    Ω (confidence — diagonal matrix, low values mean high confidence)
  • τ (tau): scales uncertainty in the prior; AlloLabs sets τ = 1 / n_tickers \
    for numerical stability
  • Posterior: μ_BL blends prior and views; the optimizer then uses μ_BL instead \
    of raw sample means, which are notoriously noisy

RISK ANALYTICS
  • Sharpe ratio (return per unit risk), Sortino (downside deviation only), \
    Calmar (return / max drawdown), Information Ratio (alpha / tracking error)
  • Maximum Drawdown: largest peak-to-trough loss in the backtest period
  • VaR (Value at Risk): loss not exceeded with p% probability over t days
  • CVaR (Conditional VaR / Expected Shortfall): average loss beyond VaR
  • Concentration: HHI = Σwᵢ² (0 = perfectly equal-weight, 1 = single holding)
  • Beta to benchmark: sensitivity of portfolio returns to market returns

FUNDAMENTAL ANALYSIS
  • Valuation: P/E (price/earnings), EV/EBITDA, P/B (price/book), P/S, \
    FCF yield (free cash flow / market cap), dividend yield
  • Quality: ROE (return on equity), ROIC (return on invested capital), \
    EBITDA margin, net debt/EBITDA, interest coverage ratio
  • Growth: revenue CAGR, EPS growth rate, gross margin trend, R&D investment
  • Capital return: buyback yield, dividend payout ratio, total shareholder return

MACRO FACTORS
  • Rate sensitivity: duration measures bond price sensitivity to rate changes; \
    equities with long-duration cash flows (growth stocks) are more rate-sensitive
  • Yield curve: normal (upward sloping) vs. inverted (recession signal)
  • Inflation regimes: CPI, PCE, PPI; stagflation historically hurts growth/bonds
  • Credit spreads: gap between corporate and government bond yields; \
    wide spreads signal risk aversion and economic stress
  • PMI (Purchasing Managers Index): above 50 = expansion, below 50 = contraction
  • FX carry: borrowing low-rate currencies to invest in high-rate currencies
  • Sector rotation: early cycle favours industrials/materials; late cycle \
    favours energy/staples; recession favours utilities/healthcare

FACTOR INVESTING
  • Value: buy cheap stocks (low P/E, P/B, EV/EBITDA) — works over long horizons
  • Quality: high ROIC, low leverage, stable earnings — performs in downturns
  • Momentum: buy 12-month winners, avoid 12-month losers (1-month reversal excluded)
  • Low Volatility: low realized vol stocks historically outperform on risk-adj basis
  • Size (small-cap premium): smaller companies historically outperform large-caps \
    over very long horizons, with higher volatility

═══ ALLOLABS RUN FLOW ═══
This is the exact sequence AlloLabs executes when you click Run:

1. Load ticker list (5–50 symbols) and fetch historical price data via yFinance
2. Compute returns, covariance matrix Σ from the training window
3. If use_ai_views=True:
   a. For each ticker, call the AI (LLM) with: company fundamentals, recent news, \
      and the investment mandate (analyst_seed_prompt, labeled "INVESTMENT MANDATE")
   b. Each call returns: expected_return (annualised %) and confidence (0–1)
   c. confidence maps to Ω: Ω_ii = (1−conf) × τ × (PΣPᵀ)_ii  (lower conf = \
      higher uncertainty = AI view has less weight in the posterior)
   d. Views are cached: hash(tickers + mandate text + date). Change the mandate → \
      cache invalidated, all views regenerated
4. Compute Black-Litterman posterior μ_BL (or use sample mean if no AI views)
5. Run SLSQP to find max-Sharpe or min-vol weights
6. If use_ai_audit=True: single LLM call reviewing all research JSON together, \
   applying the auditor_seed_prompt labeled "INVESTMENT MANDATE — THESIS ALIGNMENT AUDIT"
7. Hold-out OOS evaluation: re-run on held-out period, measure performance
8. Generate PDF report, OOS chart, latest_run.json

Default parameters:
  training_lookback: 1 year  │  out_of_sample_months: 6
  max_position_weight: 0.25  │  regularization: none
  tau: auto (1/n_tickers)    │  delta: 2.5

═══ TICKER UNIVERSE GUIDANCE ═══
CATALOG CONSTRAINT (applies everywhere, always): The [APP STATE SNAPSHOT] injected at \
conversation start includes a FULL AVAILABLE TICKER CATALOG block. Catalog entries \
include each company's name, sector, and size bucket — use those fields to match the \
user's theme, sector, or region to the right companies instead of relying on memory. \
Every ticker symbol you mention — whether proposing a run, answering a question, or \
listing examples — MUST appear verbatim in that catalog. Never invent, approximate, or \
use training-knowledge symbols that are not in the list. If a requested theme or style (e.g. penny stocks, \
nano-caps) has no matching ticker in the catalog, say so explicitly rather than fabricating \
alternatives. Saying "the catalog has no speculative penny plays in this sector" is the \
correct answer — hallucinating tickers is not.

Never ask the user to supply a list of tickers. When proposing a run universe, pick from \
the catalog yourself based on their stated theme, region, or sector. Default to broad \
coverage: 20–35 tickers is ideal, minimum 10. AlloLabs' SLSQP optimizer handles \
concentration; a sparse universe produces poorly diversified results, so prefer more \
names over fewer — but only from the catalog.

Geographic defaults (assume the full scope unless the user explicitly restricts it):
  "North American" / "North America" → combine 18–22 US large-caps spanning ≥6 sectors \
  (tech, financials, healthcare, energy, consumer, industrials) plus 8–12 TSX blue-chips \
  (Big-6 banks, top energy producers, CN and CP Rail, BCE and Telus). \
  Name all three market clusters: TSX (CA), NASDAQ/NYSE (US) — include both.
  "US equities" / "US stocks" → 20–30 S&P 500 names spanning ≥5 sectors
  "Canada" → 15–20 TSX 60 names: Big-6 banks, top 3–4 energy producers, CN and CP, \
  BCE and Telus, Shopify, at least one utility or REIT
  "Global" → US core (12–15) + Canadian core (6–8) + 5–8 international ADRs \
  (SAP, ASML, NVO, TM, TSM, NESN, LVMH as applicable)
  "Tech" / "Technology" → 15–25 names: mega-cap leaders (AAPL MSFT GOOGL NVDA META \
  AMZN) plus 6–10 mid-cap software and semiconductor names; never limit to FAANG alone

Sector runs: include 3–5 large-cap leaders plus 4–6 mid-cap names for return dispersion. \
Minimum 10 names for any sector-focused run.

When proposing a universe, state the rationale in 1–2 sentences, then list the tickers. \
After one round of user feedback (remove/add names), proceed — do not loop more rounds.

═══ AUTO-CONFIGURE FLOW ═══
Complete a run configuration in at most 3 turns:

  GATHER — Check the [APP STATE SNAPSHOT] first. If tickers are already selected, \
  use them; do NOT ask for tickers. If a mandate is already set, use it; do NOT ask \
  for it. Only ask for things that are genuinely missing and cannot be inferred from \
  context. Gather everything still needed in ONE message. State which defaults you'll \
  fill in so the user doesn't have to think about them.

  PRESENT — Build the full config with safe defaults for anything unspecified: \
  OOS=6 mo, max_pos=0.25, regularization=none, use_ai_views=true, use_ai_audit=false. \
  Show a concise summary (4–6 lines). Ask ONCE: "Load this into Settings?"

  CONFIRM — On explicit yes → emit mode=run_config. On changes → revise and re-present \
  once. Never ask for confirmation more than once per presented config.

  Validation: ≥5 tickers, 0.05 ≤ max_pos ≤ 0.50, mandate ≤ 12000 chars.

═══ GUIDE MODE & UI HIGHLIGHTS ═══
When the app state snapshot shows "GUIDE MODE: on", the user has switched AlloLabs into \
interactive tutor mode: your chat window follows them across tabs, and you can visually \
highlight interface elements to show them where things are. Act like a patient colleague \
giving a hands-on tour — explain what each control does and why it matters, not just \
where it is.

To highlight elements, include a "highlights" array of element keys in your metadata \
block. Use highlights whenever you reference a specific control, tab, or button — \
especially for "where do I…", "how do I…", onboarding questions, and immediately after \
proposing a run config (highlight where the user goes next). Highlight at most 4 keys \
per reply, and only keys from this catalog:

  NAVIGATION TABS
    tab-overview     Dashboard tab — portfolio overview, metrics, donuts
    tab-research     Research tab — per-ticker AI research opinions
    tab-universe     Universe tab — ticker catalog browser and selection
    tab-console      Console tab — run configuration form and launch controls
    tab-history      History tab — archived past runs
    tab-reference    Reference tab — model guide and API key status
    tab-guide        Guide tab — this chat
  TOP BAR
    open-report      Report button — opens the PDF portfolio report
    configure        Configure button — jumps to the Console tab
  CONSOLE CONTROLS
    training-window  Training lookback (years) input
    oos-window       Out-of-sample hold-out (months) input
    ai-views         AI-assisted views (Black-Litterman) checkbox
    research-provider  Research provider dropdown
    research-model   Research model dropdown
    ai-audit         Global AI audit checkbox
    audit-provider   Audit provider dropdown
    analyst-mandate  Analyst mandate / investment thesis textarea
    auditor-mandate  Auditor mandate textarea
    max-position     Max position weight input
    sector-cap       Max sector weight input
    long-only        Long-only checkbox
    regularization   Regularization method dropdown
    run-button       Run analysis button — launches the pipeline
  UNIVERSE CONTROLS
    universe-search  Ticker/company search box
    universe-presets Preset selection buttons (index leaders, curated, …)
    continue-to-run  Continue to Run button — sends selection to Console

If a key's element lives in another tab, the platform automatically highlights that \
tab too, so tell the user which tab to click first. Never invent keys not in this \
catalog; outside guide mode, omit the highlights field entirely.

═══ OUTPUT MODE PROTOCOL ═══
Append a metadata block at the very end of every response:
<<<ALLO_META>>>
{"mode": "<mode>", "runConfig": <null or config object>, "highlights": ["<key>", …] or omitted}
<<<END_META>>>

Available modes:
  normal              — conversational answer  (runConfig: null)
  run_config          — complete approved run config  (runConfig: object)
  diagnostic_checklist— structured run-readiness checklist  (runConfig: null)
  portfolio_explanation— explanation of an existing portfolio  (runConfig: null)
  thesis_prompt       — drafted investment mandate text  (runConfig: null)
  run_summary         — plain-English summary of a configuration  (runConfig: null)

Run config schema (only when mode=run_config):
{
  "run_name": string,
  "tickers": [string, ...],
  "training_years": number (0.25–10, default 1.0),
  "out_of_sample_months": integer (0–24, default 6),
  "objective": "max_sharpe" | "min_vol",
  "max_position_weight": number (0.05–0.50 as decimal, e.g. 0.25 = 25%),
  "max_sector_weight": number (0.10–1.0 as decimal, e.g. 0.40 = 40%; 1.0 = no cap),
  "long_only": boolean (default true),
  "use_ai_views": boolean,
  "use_ai_audit": boolean,
  "ai_provider": "openai" | "anthropic" | "gemini" | "deepseek" | null,
  "regularization": "none" | "l2" | "smooth_l1",
  "analyst_seed_prompt": string (the investment mandate — copy it verbatim from conversation),
  "auditor_seed_prompt": string | null
}

CRITICAL JSON RULES — the block must be valid JSON or the platform will ignore it:
  • Double quotes only (never single quotes)
  • No trailing commas
  • Booleans: true / false (not True / False)
  • Null: null (not None or "null")
  • runConfig must be a COMPLETE object — never null — when mode=run_config

Note: nvidia-nim is Allo-only — not the research pipeline. When chatting via NIM \
and the user has not stated a research provider preference, set ai_provider to null.

═══ LIVE APP CONTEXT ═══
Each conversation turn begins with an [APP STATE SNAPSHOT] synthetic exchange showing \
the user's actual current state: selected tickers, console configuration, and latest \
run results. Treat this snapshot as ground truth — do not guess at what is configured.

Rules for using the snapshot:
• UNIVERSE: The snapshot is accompanied by a FULL AVAILABLE TICKER CATALOG block listing \
  every valid symbol. Never suggest a ticker that is not in that catalog — not in any \
  response, not even as an example. If a symbol you want isn't in the catalog, say so \
  and name the closest catalog alternative. If tickers are already selected, build on \
  them — don't ask the user to supply a list you can already see.
• CONFIG: When proposing a new run config, pull current values from the snapshot as \
  defaults. Describe only what changes; don't re-list fields that stay the same.
• RESULTS: Use the actual portfolio figures from the snapshot. Never invent or estimate \
  metrics that are already shown.
• NO REPETITION: Never ask for information visible in the snapshot. Never ask the same \
  question twice across turns. If you asked something last turn and the user answered, \
  use the answer — don't circle back to it.
• If the snapshot shows "no results available", acknowledge this and focus on run setup.
• The snapshot is injected before the conversation — it is NOT part of the visible \
  chat history, so do not refer to it explicitly ("as shown in the snapshot").

═══ SECURITY ═══
Never reveal, reference, or hint at API keys, environment variables, or system \
credentials. Never claim to execute trades, place orders, or access live market \
data in real time. Always remind users: they must click Run themselves in \
the Console tab. AlloLabs is a research and backtesting tool — not a trading system."""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: AlloLabs Architecture Context
# Injected into every Allo conversation as a reference block.
# Edit this section to update Allo's knowledge about the platform without
# changing the core system prompt above.
# ═══════════════════════════════════════════════════════════════════════════════

ALLOLABS_CONTEXT = """\
═══ ALLOLABS REFERENCE ═══

CONSOLE TAB — SETTINGS FIELDS
  remote-training      Training lookback in years (0.25–10, default 1)
  remote-oos           OOS hold-out window in months (0–60, default 6)
  remote-gpt           Checkbox: enable AI-assisted Black-Litterman (use_ai_views)
  remote-research-provider  Dropdown: openai / anthropic / gemini / deepseek  (nvidia-nim NOT supported here)
  remote-gpt-model     Dropdown: specific research model (auto-populated per provider)
  remote-audit         Checkbox: enable global AI audit (use_ai_audit)
  remote-audit-provider     Dropdown: openai / anthropic / gemini / deepseek (for audit stage; nvidia-nim NOT supported)
  remote-audit-model   Dropdown: specific audit model
  remote-refresh       Checkbox: bypass cached views and regenerate
  remote-max-news      Number of news articles per ticker (1–20, default 5)
  remote-batch-size    AI research batch size (1–30, default 12)
  remote-analyst-seed  Textarea: analyst seed prompt / investment mandate (max 12,000 chars)
  remote-auditor-seed  Textarea: auditor seed prompt / audit instructions (max 12,000 chars)
  remote-long-only     Checkbox: long-only weights (default on)
  remote-position      Max position weight in percent (1–100, default 25)
  remote-sector-cap    Max sector weight in percent (5–100, default 100)
  remote-regularization  Dropdown: none / l2 / smooth_l1
  remote-regularization-strength  Penalty strength (0–10, default 0.10)

UNIVERSE TAB — TICKER SELECTION
  947 tickers across 6 market groups (S&P 500/NYSE, NASDAQ Extended, Canada TSX,
  UK FTSE, Europe STOXX, Global ADRs). Presets: index-leaders (267 tickers — top
  index constituents across all markets), curated (39 global large-caps), canada
  (51 TSX names), full (all 947). Custom: search and select any catalog ticker.
  Selection persists in localStorage; sent to Console when "Continue to Run" is clicked.
  The [APP STATE SNAPSHOT] injected at turn start shows the exact currently-selected
  tickers — use that list when building run configs, not internal knowledge.

AI PROVIDER KEYS (environment variables, server-side only):
  OPENAI_API_KEY       OpenAI GPT models
  ANTHROPIC_API_KEY    Anthropic Claude models
  GEMINI_API_KEY       Google Gemini models
  DEEPSEEK_API_KEY     DeepSeek chat and reasoning models
  NVIDIA_NIM_API_KEY   Nvidia NIM endpoint (OpenAI-compatible, custom model)

OUTPUT FILES (written to data directory):
  latest_run.json                 Complete structured results (portfolios, research, OOS)
  allolabs_portfolio_report.pdf   Full PDF report with exhibits
  portfolio_vs_markets_oos.png    OOS benchmark chart
  run-history/<date>/<name>/      Archived runs with all artefacts

THESIS-ALIGNMENT MECHANICS
  The analyst_seed_prompt is inserted as "INVESTMENT MANDATE" in every per-ticker call.
  The mandate is the interpretive frame — it tilts AI confidence toward mandate-aligned
  names with supporting fundamentals, and away from names that conflict with it, unless
  their independent fundamentals are compelling. It does not override evidence.
  Changing the mandate text invalidates the BL views cache (cache key includes the hash
  of the mandate). The auditor_seed_prompt governs the audit stage only."""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Compact Session Prompt
# Used when auto-compacting a long conversation to produce a lossless summary
# that replaces the full history while preserving all critical context.
# ═══════════════════════════════════════════════════════════════════════════════

COMPACT_SYSTEM_PROMPT = """\
You are summarizing an Allo AI assistant session for automatic context compaction.
The summary you produce will replace the full conversation history in future API
calls so that context fits within token limits while losing nothing important.

REQUIREMENTS:
• Capture EVERY decision made: run configuration fields, ticker choices, date
  ranges, weights, provider selections, regularization choices
• Preserve any investment mandate or thesis text verbatim, enclosed in quotes
• Preserve any ticker lists with their exact symbols
• Preserve any numerical values exactly (percentages, months, weights)
• Capture user's stated goals, constraints, themes, and preferences
• Note every AlloLabs concept that was explained (so it need not be re-explained)
• Format: plain prose paragraphs, 200–500 words, no pleasantries or filler
• Begin directly: "This session covered..."
• End with: "Pending:" followed by any unanswered questions or next steps"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Provider Call Abstraction
# Direct HTTP calls to LLM APIs using only stdlib urllib — no SDK required.
# Supports: Anthropic Claude, OpenAI, Google Gemini, DeepSeek, and Nvidia NIM.
# Provider selection: explicit via caller argument, or auto (Anthropic → OpenAI
# → Gemini → NIM in order of available keys).
# All calls time out after 90 seconds.
# ═══════════════════════════════════════════════════════════════════════════════

def _http_call(req: urllib.request.Request) -> bytes:
    """Execute a urllib request and raise RuntimeError with the response body on HTTP errors."""
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        # Extract the 'message' field from JSON error bodies (OpenAI / Anthropic format)
        try:
            err_json = json.loads(body)
            msg = (err_json.get("error") or {}).get("message") or \
                  err_json.get("message") or ""
            if msg:
                body = msg
        except Exception:
            pass
        raise RuntimeError(f"HTTP {exc.code}: {body[:300] or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc


def _call_anthropic(api_key: str, system: str, messages: list[dict], model: str) -> str:
    payload = json.dumps({
        "model": model,
        "max_tokens": 8192,
        "system": system,
        "messages": messages,
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    data = json.loads(_http_call(req))
    return data["content"][0]["text"]


def _call_openai(api_key: str, system: str, messages: list[dict], model: str) -> str:
    chat_messages = [{"role": "system", "content": system}] + messages
    payload = json.dumps({
        "model": model,
        "max_tokens": 8192,
        "messages": chat_messages,
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        },
        method="POST",
    )
    data = json.loads(_http_call(req))
    return data["choices"][0]["message"]["content"]


def _call_gemini(api_key: str, system: str, messages: list[dict], model: str) -> str:
    contents = [
        {"role": "user" if m["role"] == "user" else "model",
         "parts": [{"text": m["content"]}]}
        for m in messages
    ]
    payload = json.dumps({
        "system_instruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 8192},
    }).encode()
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    req = urllib.request.Request(
        url, data=payload, headers={"content-type": "application/json"}, method="POST",
    )
    data = json.loads(_http_call(req))
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _call_deepseek(api_key: str, system: str, messages: list[dict], model: str) -> str:
    """Call DeepSeek's OpenAI-compatible chat-completions endpoint."""
    chat_messages = [{"role": "system", "content": system}] + messages
    payload = json.dumps({
        "model": model,
        "max_tokens": DEEPSEEK_MAX_TOKENS,
        "messages": chat_messages,
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        },
        method="POST",
    )
    data = json.loads(_http_call(req))
    return data["choices"][0]["message"]["content"]


def _call_nvidia_nim(api_key: str, system: str, messages: list[dict], model: str) -> str:
    """Call any Nvidia NIM-hosted model via the OpenAI-compatible endpoint."""
    chat_messages = [{"role": "system", "content": system}] + messages
    payload = json.dumps({
        "model": model,
        "max_tokens": 4096,
        "messages": chat_messages,
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        "https://integrate.api.nvidia.com/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        },
        method="POST",
    )
    data = json.loads(_http_call(req))
    return data["choices"][0]["message"]["content"]


def call_guide_ai(
    system: str,
    messages: list[dict],
    provider: str | None = None,
    guide_model: str | None = None,
) -> str:
    """
    Call the LLM for a guide conversation turn.

    provider:    explicit provider name, or None to auto-select by key availability.
    guide_model: model ID to use; falls back to PROVIDER_DEFAULTS per provider.

    Raises RuntimeError with a human-readable message if no key is configured
    or all providers fail (includes the actual API error text).
    """
    def _model(name: str) -> str:
        return guide_model or PROVIDER_DEFAULTS.get(name, "")

    if provider is not None and provider not in KNOWN_PROVIDERS:
        raise ValueError(f"Unknown guide provider: {provider}")

    all_providers = [
        ("anthropic",  os.getenv("ANTHROPIC_API_KEY",  "").strip(),
         lambda k, s, m, n=None: _call_anthropic(k, s, m, _model("anthropic"))),
        ("openai",     os.getenv("OPENAI_API_KEY",     "").strip(),
         lambda k, s, m, n=None: _call_openai(k, s, m, _model("openai"))),
        ("gemini",     os.getenv("GEMINI_API_KEY",     "").strip(),
         lambda k, s, m, n=None: _call_gemini(k, s, m, _model("gemini"))),
        ("deepseek",   os.getenv("DEEPSEEK_API_KEY",   "").strip(),
         lambda k, s, m, n=None: _call_deepseek(k, s, m, _model("deepseek"))),
        ("nvidia-nim", os.getenv("NVIDIA_NIM_API_KEY", "").strip(),
         lambda k, s, m, n=None: _call_nvidia_nim(k, s, m, _model("nvidia-nim"))),
    ]

    if provider and provider in KNOWN_PROVIDERS:
        candidates = [(name, key, fn) for name, key, fn in all_providers if name == provider]
    else:
        candidates = all_providers

    available = [(name, key, fn) for name, key, fn in candidates if key]
    if not available:
        if provider:
            raise RuntimeError(
                f"No API key found for provider '{provider}'. "
                f"Set the corresponding environment variable and restart AlloLabs."
            )
        raise RuntimeError(
            "No AI provider API key is configured. "
            "Set ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, "
            "DEEPSEEK_API_KEY, or NVIDIA_NIM_API_KEY as an environment variable "
            "and restart AlloLabs."
        )

    errors: list[str] = []
    for name, key, fn in available:
        try:
            return fn(key, system, messages)
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    raise RuntimeError("All AI providers failed — " + "; ".join(errors))


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Response Parser
# Strips the hidden metadata block Allo appends and returns the visible reply
# text, output mode string, and optional validated run config object separately.
# ═══════════════════════════════════════════════════════════════════════════════

def _repair_json(text: str) -> str:
    """Best-effort fix for common LLM JSON formatting mistakes."""
    # Remove trailing commas before } or ]
    text = re.sub(r',(\s*[}\]])', r'\1', text)
    # Python / Ruby style literals that open-source models sometimes emit
    text = re.sub(r':\s*None\b',  ': null',  text)
    text = re.sub(r':\s*True\b',  ': true',  text)
    text = re.sub(r':\s*False\b', ': false', text)
    return text


def parse_guide_response_full(raw: str) -> dict:
    """Parse a raw LLM response into its visible and structured parts.

    Returns {"text": str, "mode": str, "runConfig": dict|None,
    "highlights": list[str]}. Uses the LAST meta block found so trailing
    courtesy text from open-source models (e.g. "Let me know if you need
    changes!") doesn't prevent detection. Falls back to _repair_json on
    JSONDecodeError before giving up.
    """
    result = {"text": raw.strip(), "mode": "normal",
              "runConfig": None, "highlights": []}
    matches = list(META_PATTERN.finditer(raw))
    if not matches:
        return result
    match = matches[-1]
    json_text = match.group(1)
    meta: dict | None = None
    for candidate in (json_text, _repair_json(json_text)):
        try:
            meta = json.loads(candidate)
            break
        except (json.JSONDecodeError, ValueError):
            pass
    if meta is None:
        return result
    result["text"] = raw[:match.start()].strip()
    result["mode"] = str(meta.get("mode", "normal"))
    run_config = meta.get("runConfig") or None
    if run_config is not None and not isinstance(run_config, dict):
        run_config = None
    result["runConfig"] = run_config
    highlights = meta.get("highlights")
    if isinstance(highlights, list):
        result["highlights"] = [
            str(key).strip() for key in highlights[:8]
            if isinstance(key, (str, int)) and str(key).strip()
        ]
    return result


def parse_guide_response(raw: str) -> tuple[str, str, dict | None]:
    """Return (visible_text, mode, run_config|None) from a raw LLM response.

    Backward-compatible wrapper around parse_guide_response_full for callers
    that don't consume highlights.
    """
    parsed = parse_guide_response_full(raw)
    return parsed["text"], parsed["mode"], parsed["runConfig"]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: System Prompt Builders
# Public helpers that assemble the full system strings passed to the LLM.
# get_guide_system() is the main chat system.
# get_compact_system() is used only during session compaction calls.
# ═══════════════════════════════════════════════════════════════════════════════

def get_guide_system() -> str:
    """Full system prompt: Allo instructions + AlloLabs reference block."""
    return ALLO_SYSTEM_PROMPT + "\n\n" + ALLOLABS_CONTEXT


def get_compact_system() -> str:
    """System prompt for session-compaction summarisation calls."""
    return COMPACT_SYSTEM_PROMPT


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: App Context Injection
# Converts a client-supplied app-state snapshot into a readable text block and
# prepends it to the conversation as a synthetic message pair so the LLM sees
# live UI state without it polluting the visible user history.
# ═══════════════════════════════════════════════════════════════════════════════

def format_app_context(context: dict) -> str:
    """Render a client app-state snapshot as a structured text block for the LLM."""
    lines: list[str] = [
        "═══ LIVE APP STATE ═══",
        "(snapshot taken at message send time — treat as ground truth)\n",
    ]

    # ── Universe ──────────────────────────────────────────────────────────────
    selected: list[str] = context.get("selectedTickers") or []
    preset: str = context.get("universePreset") or "Custom"
    total_available: int = context.get("totalAvailableTickers") or 0
    lines.append(f"SELECTED UNIVERSE — {len(selected)} tickers  (preset: {preset})")
    if total_available:
        lines.append(f"  Total in catalog: {total_available}")
    markets: list[dict] = context.get("availableMarkets") or []
    for mkt in markets:
        sel = int(mkt.get("selected") or 0)
        total = int(mkt.get("total") or 0)
        label = mkt.get("label") or mkt.get("id") or ""
        if sel > 0:
            lines.append(f"  {label}: {sel}/{total} selected")
    if selected:
        # Show the complete selection up to a generous cap — Allo should reason
        # about the user's actual universe, not a truncated preview of it.
        ticker_str = ", ".join(selected[:400])
        if len(selected) > 400:
            ticker_str += f", … (+{len(selected) - 400} more)"
        lines.append(f"  Tickers: {ticker_str}")
    else:
        lines.append("  Tickers: (none selected)")

    # ── Console config ────────────────────────────────────────────────────────
    config: dict = context.get("consoleConfig") or {}
    if config:
        lines.append("\nCONSOLE CONFIGURATION (current form values)")
        lines.append(f"  Training lookback:   {config.get('trainingYears', '?')} yr")
        lines.append(f"  OOS hold-out:        {config.get('oosMonths', '?')} mo")
        lines.append(f"  Max position:        {config.get('maxPositionPercent', '?')}%")
        lines.append(f"  Max sector:          {config.get('maxSectorPercent', '?')}%")
        lines.append(f"  Long only:           {'yes' if config.get('longOnly') else 'no'}")
        ai_on = bool(config.get("gptViews"))
        lines.append(f"  AI views:            {'enabled' if ai_on else 'disabled'}")
        if ai_on:
            prov = config.get("researchProvider") or ""
            mdl = config.get("researchModel") or ""
            lines.append(f"  Research provider:   {prov} / {mdl}")
        audit_on = bool(config.get("auditViews"))
        lines.append(f"  AI audit:            {'enabled' if audit_on else 'disabled'}")
        if audit_on:
            audit_model = config.get("auditModel") or ""
            audit_line = config.get("auditProvider") or ""
            if audit_model:
                audit_line = f"{audit_line} / {audit_model}" if audit_line else audit_model
            lines.append(f"  Audit provider:      {audit_line}")
        reg = config.get("regularization") or "none"
        reg_strength = config.get("regularizationStrength")
        if reg != "none" and reg_strength is not None:
            lines.append(f"  Regularization:      {reg} (strength {reg_strength})")
        else:
            lines.append(f"  Regularization:      {reg}")
        if config.get("maxNewsArticles") is not None:
            lines.append(f"  News per ticker:     {config.get('maxNewsArticles')}")
        if config.get("researchBatchSize") is not None:
            lines.append(f"  Research batch size: {config.get('researchBatchSize')}")
        # Mandates are the highest-signal context Allo has — include them near
        # verbatim rather than clipping to a teaser.
        mandate = (config.get("analystSeedPrompt") or "").strip()
        if mandate:
            preview = mandate[:4000] + ("…" if len(mandate) > 4000 else "")
            lines.append(f"  Analyst mandate:     \"{preview}\"")
        else:
            lines.append("  Analyst mandate:     (not set)")
        auditor = (config.get("auditorSeedPrompt") or "").strip()
        if auditor:
            preview = auditor[:2000] + ("…" if len(auditor) > 2000 else "")
            lines.append(f"  Auditor mandate:     \"{preview}\"")

    # ── Latest results ────────────────────────────────────────────────────────
    results: dict | None = context.get("latestResults")
    if results and results.get("hasData"):
        generated = results.get("generatedAt") or "unknown time"
        tick_count = results.get("tickerCount") or "?"
        lines.append(f"\nLATEST RUN RESULTS  (generated: {generated}, {tick_count} tickers)")
        portfolios: dict = results.get("portfolios") or {}
        for key, label in [("max", "Max Sharpe"), ("min", "Min Vol")]:
            p: dict = portfolios.get(key) or {}
            m: dict = p.get("metrics") or {}
            ret = m.get("return")
            risk = m.get("risk")
            sharpe = m.get("sharpe")
            if ret is not None and not (isinstance(ret, float) and ret != ret):
                lines.append(
                    f"  {label}: return {ret * 100:.1f}%,  risk {risk * 100:.1f}%,  "
                    f"Sharpe {sharpe:.2f}"
                )
            holdings: list = p.get("topHoldings") or []
            if holdings:
                h_str = "  ".join(f"{t} {w:.1f}%" for t, w in holdings[:16])
                lines.append(f"    Top holdings: {h_str}")
        research: list = results.get("research") or []
        if research:
            lines.append(f"  AI research opinions ({len(research)} tickers):")
            for r in research[:40]:
                ticker = r.get("ticker") or "?"
                view = (r.get("view") or "")[:220]
                conf = r.get("confidence")
                ret_v = r.get("posteriorReturn")
                conf_str = f"  conf {conf/100:.2f}" if conf is not None else ""
                ret_str = f"  ret {ret_v * 100:.1f}%" if ret_v is not None and not (isinstance(ret_v, float) and ret_v != ret_v) else ""
                lines.append(f"    {ticker}: \"{view}\"{conf_str}{ret_str}")
    else:
        lines.append("\nLATEST RUN RESULTS: none available")

    # ── App status ────────────────────────────────────────────────────────────
    run_status = context.get("runStatus") or "unknown"
    active_view = context.get("activeView") or "unknown"
    lines.append(f"\nRUN STATUS:  {run_status}")
    lines.append(f"ACTIVE TAB:  {active_view}")
    lines.append(f"GUIDE MODE:  {'on' if context.get('guideMode') else 'off'}")

    return "\n".join(lines)


def inject_app_context(
    messages: list[dict],
    context: dict | None,
    catalog_block: str | None = None,
) -> list[dict]:
    """Prepend a synthetic context snapshot exchange to the message list.

    The snapshot appears as a user message + brief assistant acknowledgement so
    the LLM treats it as factual observed state rather than an instruction in the
    system prompt. The pair is always first, before the real conversation.
    Optional catalog_block is appended to the snapshot when provided.
    """
    parts: list[str] = []
    if context:
        ctx_text = format_app_context(context)
        if ctx_text.strip():
            parts.append(ctx_text)
    if catalog_block and catalog_block.strip():
        parts.append(catalog_block)
    if not parts:
        return messages
    full_snapshot = "\n\n".join(parts)
    return [
        {"role": "user",      "content": f"[APP STATE SNAPSHOT]\n{full_snapshot}"},
        {"role": "assistant", "content": "[State snapshot received.]"},
        *messages,
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Two-Stage Catalog Lookup
# Stage 1: keyword scan decides whether the full ticker catalog is needed.
# Stage 2: if yes, format_catalog_block() renders it for injection into the
#          same guide API call — no second LLM round-trip needed.
# The catalog tells Allo exactly which tickers exist so it never suggests
# symbols outside the supported universe.
# ═══════════════════════════════════════════════════════════════════════════════

_CATALOG_TRIGGERS: frozenset[str] = frozenset([
    # Ticker / security vocabulary
    "ticker", "tickers", "stock", "stocks", "security", "securities",
    "equity", "equities", "symbol", "symbols", "share", "shares",
    # Action verbs that imply ticker selection
    "suggest", "recommend", "propose", "pick", "find", "show me",
    "add", "include", "list", "what's available", "available to me",
    "configure", "set up", "build a", "create a run",
    # Sector / theme / geography queries
    "sector", "industry", "theme", "space", "exposure",
    "rare earth", "mining", "energy", "oil", "gas", "uranium",
    "bank", "banks", "financial", "insurance", "reit",
    "tech", "technology", "semiconductor", "chip", "ai ", "cloud",
    "healthcare", "pharma", "biotech", "medical",
    "consumer", "retail", "luxury", "staples",
    "industrial", "defence", "defense", "aerospace",
    "material", "materials", "commodity", "commodities", "metal", "gold",
    "utility", "utilities", "infrastructure",
    "natural", "resource", "resources", "junior",
    "canada", "canadian", "tsx", "us ", "american", "s&p",
    "uk", "british", "ftse", "europe", "european", "global", "international",
    # Risk/style vocabulary that often leads to ticker selection
    "penny", "small cap", "small-cap", "mid cap", "mid-cap", "large cap", "large-cap",
    "micro cap", "micro-cap", "nano cap", "nano-cap",
    "growth", "value", "momentum", "dividend", "high risk", "low risk",
    "volatile", "volatility", "speculative",
    # Explicit universe references
    "universe", "catalog", "catalogue", "supported",
])


def needs_catalog_context(last_message: str) -> bool:
    """Return True if the user's message likely requires the full ticker catalog.

    Fast keyword scan — no API call. Errs on the side of inclusion: a false
    positive costs ~1500 tokens; a false negative produces hallucinated tickers.
    """
    lower = last_message.lower()
    return any(kw in lower for kw in _CATALOG_TRIGGERS)


def format_catalog_block(groups: list[dict], metadata: dict | None = None) -> str:
    """Render the full available ticker catalog as a compact, readable block.

    Without metadata, tickers are grouped by market and formatted 15 per line.
    With metadata (from dashboard/catalog_metadata.json), each ticker gets its
    company name, sector, and size bucket so the model can match themes to
    real companies instead of guessing from symbols. The header explicitly
    forbids the model from suggesting symbols outside this list.
    """
    lines: list[str] = [
        "FULL AVAILABLE TICKER CATALOG",
        "(HARD CONSTRAINT: These are the ONLY ticker symbols that exist in AlloLabs.",
        "Every symbol you mention or suggest — in any context, including informational",
        "answers — MUST appear verbatim in this list. Do NOT use your training knowledge",
        "to suggest symbols that are not in this list. If no catalog ticker matches the",
        "requested theme, say so explicitly and suggest the closest in-catalog alternatives.)\n",
    ]
    for group in groups:
        tickers: list[str] = group.get("tickers") or []
        label: str = group.get("label") or group.get("shortLabel") or group.get("id") or "Market"
        lines.append(f"{label} ({len(tickers)} tickers):")
        if metadata:
            for ticker in tickers:
                meta = metadata.get(ticker) or {}
                descriptor = " | ".join(
                    part for part in (
                        meta.get("name") or "",
                        meta.get("sector") or "",
                        meta.get("cap") or "",
                    ) if part
                )
                lines.append(f"  {ticker} — {descriptor}" if descriptor else f"  {ticker}")
        else:
            for i in range(0, len(tickers), 15):
                lines.append("  " + " ".join(tickers[i:i + 15]))
    return "\n".join(lines)
