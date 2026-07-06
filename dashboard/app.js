const emptyPortfolio = {
  metrics: { return: "--", risk: "--", sharpe: "--", concentration: "--" },
  metricValues: { return: NaN, risk: NaN, sharpe: NaN, concentration: NaN },
  note: "Run an analysis to populate the portfolio allocation and sector breakdown.",
  holdings: [],
  sectors: [],
  markets: [],
  currencies: []
};

let portfolioData = { max: emptyPortfolio, min: emptyPortfolio };
let researchData = [];
let performanceCache = null;
const companyDetailsCache = new Map();
let companyModalTrigger = null;
const UNIVERSE_STORAGE_KEY = "allolabs-universe-selection-v1";
let universeCatalogData = null;
let selectedUniverseTickers = new Set();
let pendingUniverseConfig = null;
let activeUniverseMarket = "all";
// Groups collapsed in the accordion. "all markets" view starts all collapsed;
// a specific market filter auto-expands that group.
let collapsedGroups = new Set();

const AI_MODELS = {
  openai: [
    ["gpt-5.5", "GPT-5.5", "audit"],
    ["gpt-5.4", "GPT-5.4", "both"],
    ["gpt-5.4-mini", "GPT-5.4 mini", "research"],
    ["gpt-5.4-nano", "GPT-5.4 nano", "research"]
  ],
  anthropic: [
    ["claude-fable-5", "Claude Fable 5", "audit"],
    ["claude-opus-4-8", "Claude Opus 4.8", "both"],
    ["claude-sonnet-4-6", "Claude Sonnet 4.6", "both"],
    ["claude-haiku-4-5", "Claude Haiku 4.5", "research"]
  ],
  gemini: [
    ["gemini-3.5-flash", "Gemini 3.5 Flash", "both"],
    ["gemini-3.1-pro-preview", "Gemini 3.1 Pro Preview", "audit"],
    ["gemini-3.1-flash-lite", "Gemini 3.1 Flash-Lite", "research"],
    ["gemini-3-flash-preview", "Gemini 3 Flash Preview", "both"],
    ["gemini-2.5-pro", "Gemini 2.5 Pro", "audit"],
    ["gemini-2.5-flash", "Gemini 2.5 Flash", "research"],
    ["gemini-2.5-flash-lite", "Gemini 2.5 Flash-Lite", "research"]
  ],
  deepseek: [
    ["deepseek-chat", "DeepSeek Chat", "research"],
    ["deepseek-reasoner", "DeepSeek Reasoner", "audit"]
  ]
};

const MODEL_GUIDE = [
  {
    provider: "OpenAI", model: "GPT-5.5", id: "gpt-5.5", role: "audit",
    context: "1.05M", output: "128K", status: "Current",
    inputs: "Text + image",
    strength: "Highest OpenAI reasoning; strongest fit for full-universe audit.",
    weakness: "Highest cost; unnecessary for routine batched stock views."
  },
  {
    provider: "OpenAI", model: "GPT-5.4", id: "gpt-5.4", role: "both",
    context: "1.05M", output: "128K", status: "Current",
    inputs: "Text + image",
    strength: "Strong professional reasoning with a better cost balance than 5.5.",
    weakness: "Slower and more expensive than mini for high-volume research."
  },
  {
    provider: "OpenAI", model: "GPT-5.4 mini", id: "gpt-5.4-mini", role: "research",
    context: "400K", output: "128K", status: "Current",
    inputs: "Text + image",
    strength: "Fast, capable, and economical for batched equity analysis.",
    weakness: "Less reliable than frontier models for subtle global calibration."
  },
  {
    provider: "OpenAI", model: "GPT-5.4 nano", id: "gpt-5.4-nano", role: "research",
    context: "400K", output: "128K", status: "Current",
    inputs: "Text + image",
    strength: "Lowest-cost OpenAI option for simple extraction and ranking.",
    weakness: "Least nuanced option; usually a poor fit for the final audit layer."
  },
  {
    provider: "Anthropic", model: "Claude Fable 5", id: "claude-fable-5", role: "audit",
    context: "1M", output: "128K", status: "GA",
    inputs: "Text + image",
    strength: "Anthropic's highest-capability widely released model.",
    weakness: "Premium cost and excessive capacity for ordinary research batches."
  },
  {
    provider: "Anthropic", model: "Claude Opus 4.8", id: "claude-opus-4-8", role: "both",
    context: "1M", output: "128K", status: "Current",
    inputs: "Text + image",
    strength: "Deep reasoning and long-context consistency for difficult audits.",
    weakness: "Higher latency and cost than Sonnet."
  },
  {
    provider: "Anthropic", model: "Claude Sonnet 4.6", id: "claude-sonnet-4-6", role: "both",
    context: "1M", output: "64K", status: "Current",
    inputs: "Text + image",
    strength: "Excellent speed/intelligence balance; sensible research default.",
    weakness: "Lower maximum output and peak capability than Opus or Fable."
  },
  {
    provider: "Anthropic", model: "Claude Haiku 4.5", id: "claude-haiku-4-5", role: "research",
    context: "200K", output: "64K", status: "Current",
    inputs: "Text + image",
    strength: "Fastest Claude option and efficient for many small batches.",
    weakness: "Smallest Claude context and less cross-sectional nuance."
  },
  {
    provider: "Google", model: "Gemini 3.1 Pro Preview", id: "gemini-3.1-pro-preview", role: "audit",
    context: "1,048,576", output: "65,536", status: "Preview",
    inputs: "Multimodal",
    strength: "Google's complex-reasoning choice for large global audits.",
    weakness: "Preview behavior and availability can change."
  },
  {
    provider: "Google", model: "Gemini 3.5 Flash", id: "gemini-3.5-flash", role: "both",
    context: "1,048,576", output: "65,536", status: "Stable",
    inputs: "Multimodal",
    strength: "Frontier-level speed and strong scale economics.",
    weakness: "May be less deliberate than Pro on difficult portfolio-wide edits."
  },
  {
    provider: "Google", model: "Gemini 3.1 Flash-Lite", id: "gemini-3.1-flash-lite", role: "research",
    context: "1,048,576", output: "65,536", status: "Stable",
    inputs: "Multimodal",
    strength: "Low latency and cost for lightweight structured research.",
    weakness: "Designed for simpler work, not deep audit judgment."
  },
  {
    provider: "Google", model: "Gemini 3 Flash Preview", id: "gemini-3-flash-preview", role: "both",
    context: "1,048,576", output: "65,536", status: "Preview",
    inputs: "Multimodal",
    strength: "Fast, broadly capable structured-output model with a large context window.",
    weakness: "Preview lifecycle is less predictable than stable Gemini releases."
  },
  {
    provider: "Google", model: "Gemini 2.5 Pro", id: "gemini-2.5-pro", role: "audit",
    context: "1,048,576", output: "65,536", status: "Stable",
    inputs: "Multimodal",
    strength: "Mature high-capability model for complex portfolio-wide reasoning.",
    weakness: "Older and generally slower or costlier than the Flash family."
  },
  {
    provider: "Google", model: "Gemini 2.5 Flash", id: "gemini-2.5-flash", role: "research",
    context: "1,048,576", output: "65,536", status: "Stable",
    inputs: "Multimodal",
    strength: "Mature price-performance model with broad structured-output support.",
    weakness: "Older generation with less advanced reasoning than 3.x models."
  },
  {
    provider: "Google", model: "Gemini 2.5 Flash-Lite", id: "gemini-2.5-flash-lite", role: "research",
    context: "1,048,576", output: "65,536", status: "Stable",
    inputs: "Multimodal",
    strength: "Lowest-cost mature Gemini option for large batches of simple views.",
    weakness: "Less suitable for subtle forecasts or final cross-universe calibration."
  },
  {
    provider: "DeepSeek", model: "DeepSeek Chat", id: "deepseek-chat", role: "research",
    context: "128K", output: "8K", status: "Current",
    inputs: "Text",
    strength: "Economical JSON-mode model for high-volume equity research batches.",
    weakness: "Shorter output ceiling makes it a weaker fit for full-universe audits."
  },
  {
    provider: "DeepSeek", model: "DeepSeek Reasoner", id: "deepseek-reasoner", role: "audit",
    context: "128K", output: "64K", status: "Current",
    inputs: "Text",
    strength: "Deliberate reasoning and long output capacity for portfolio-wide audits.",
    weakness: "Reasoning tokens increase latency and consume part of the output allowance."
  }
];

const PROVIDER_KEY_SETUP = {
  openai:       { label: "OpenAI",       environment: "OPENAI_API_KEY" },
  anthropic:    { label: "Anthropic",    environment: "ANTHROPIC_API_KEY" },
  gemini:       { label: "Google Gemini", environment: "GEMINI_API_KEY" },
  deepseek:     { label: "DeepSeek",     environment: "DEEPSEEK_API_KEY" },
  "nvidia-nim": { label: "Nvidia NIM",   environment: "NVIDIA_NIM_API_KEY", note: "Allo (Guide tab) only — not available for research or audit pipeline" },
};
let providerKeyStatusSignature = "";
const operatingSystem = /Mac/i.test(navigator.platform)
  ? "macos"
  : /Linux/i.test(navigator.platform) ? "linux" : "windows";

function providerSetupCommand(environment, persistent = false) {
  if (operatingSystem !== "windows") {
    return persistent
      ? `Add export ${environment}="paste-key-here" to your shell profile, then relaunch AlloLabs`
      : `export ${environment}="paste-key-here"`;
  }
  if (persistent) {
    return `[Environment]::SetEnvironmentVariable("${environment}", "paste-key-here", "User")`;
  }
  return `$env:${environment} = "paste-key-here"`;
}

function renderProviderKeyStatus(providerKeys = null, apiVersion = 0) {
  const container = document.getElementById("provider-key-status");
  if (!container) return;
  const signature = JSON.stringify({ apiVersion: Number(apiVersion || 0), providerKeys });
  if (signature === providerKeyStatusSignature) return;
  providerKeyStatusSignature = signature;
  const supportsStatus = Number(apiVersion || 0) >= 14 && providerKeys;
  const unavailablePreview = Number(apiVersion || 0) > 0
    ? `Restart dashboard (connected server is API v${apiVersion})`
    : "Connect to the dashboard server";
  container.innerHTML = Object.entries(PROVIDER_KEY_SETUP).map(([provider, setup]) => {
    const keyStatus = supportsStatus ? providerKeys[provider] : null;
    const detected = Boolean(keyStatus?.active);
    const stateLabel = keyStatus ? (detected ? "Detected" : "Not detected") : "Unavailable";
    const stateClass = detected ? "detected" : keyStatus ? "not-detected" : "unknown";
    const preview = detected ? keyStatus.preview : keyStatus ? "No key detected" : unavailablePreview;
    const environment = keyStatus?.environment || setup.environment;
    const source = detected ? (keyStatus.source || "Dashboard environment") : "Not configured";
    return `
      <article class="provider-key-card ${stateClass}">
        <div class="provider-key-card-heading">
          <div>
            <strong>${escapeHtml(setup.label)}</strong>
            <code>${escapeHtml(environment)}</code>
          </div>
          <span class="provider-key-state ${stateClass}"><i></i>${stateLabel}</span>
        </div>
        ${setup.note ? `<p class="provider-key-scope-note">${escapeHtml(setup.note)}</p>` : ""}
        <div class="provider-key-preview">
          <small>Censored preview</small>
          <code>${escapeHtml(preview || "No key detected")}</code>
          <span>${escapeHtml(source)}</span>
        </div>
        <details class="provider-key-instructions"${detected ? "" : " open"}>
          <summary>${detected ? "Replace key or review setup" : "How to configure"}</summary>
          <p>For a temporary key, relaunch AlloLabs from the same terminal. Persistent environment setup varies by operating system and desktop session.</p>
          <label>
            <span>${operatingSystem === "windows" ? "Current PowerShell session" : "Current terminal session"}</span>
            <code>${escapeHtml(providerSetupCommand(environment))}</code>
            <button type="button" data-copy-provider-command="${escapeHtml(providerSetupCommand(environment))}">Copy</button>
          </label>
          <label>
            <span>${operatingSystem === "windows" ? "Persistent Windows user variable" : "Persistent shell environment"}</span>
            <code>${escapeHtml(providerSetupCommand(environment, true))}</code>
            <button type="button" data-copy-provider-command="${escapeHtml(providerSetupCommand(environment, true))}">Copy</button>
          </label>
          <small>Replace <b>paste-key-here</b> locally. Never commit API keys to GitHub.</small>
        </details>
      </article>
    `;
  }).join("");
}

function renderModelGuide() {
  const container = document.getElementById("model-guide");
  if (!container) return;
  const providers = ["OpenAI", "Anthropic", "Google", "DeepSeek"];
  container.innerHTML = providers.map((provider) => `
    <section class="model-provider">
      <div class="model-provider-heading">
        <p class="eyebrow">${provider}</p>
        <strong>${MODEL_GUIDE.filter((item) => item.provider === provider).length} available models</strong>
      </div>
      <div class="model-table">
        <div class="model-row model-header">
          <span>Model / role</span><span>Published limits</span><span>Strength</span><span>Weakness</span>
        </div>
        ${MODEL_GUIDE.filter((item) => item.provider === provider).map((item) => `
          <article class="model-row">
            <div class="model-identity">
              <strong>${item.model}</strong>
              <code>${item.id}</code>
              <span class="model-role ${item.role}">${item.role === "both" ? "Research + audit" : item.role}</span>
            </div>
            <div class="model-specs">
              <span><small>Context</small><b>${item.context}</b></span>
              <span><small>Max output</small><b>${item.output}</b></span>
              <span><small>Status</small><b>${item.status}</b></span>
              <span><small>Input</small><b>${item.inputs}</b></span>
            </div>
            <p class="model-strength">${item.strength}</p>
            <p class="model-weakness">${item.weakness}</p>
          </article>
        `).join("")}
      </div>
    </section>
  `).join("");
}

function populateModelSelect(select, stage, provider, preferredModel) {
  const models = AI_MODELS[provider] || [];
  select.innerHTML = models.map(([value, label, recommendation]) => {
    const isRecommended = recommendation === stage || recommendation === "both";
    return `<option value="${value}">${label}${isRecommended ? " · Recommended" : ""}</option>`;
  }
  ).join("");
  if (models.some(([value]) => value === preferredModel)) select.value = preferredModel;
}

const TSX_60_MEMBERS = new Set([
  "RY.TO", "TD.TO", "BMO.TO", "BNS.TO", "NA.TO", "CM.TO", "ENB.TO", "TRP.TO",
  "SU.TO", "CNQ.TO", "CVE.TO", "POW.TO", "SLF.TO", "MFC.TO", "FFH.TO", "BAM.TO",
  "BN.TO", "FTS.TO", "EMA.TO", "TRI.TO", "CSU.TO", "WCN.TO", "WSP.TO", "CNR.TO",
  "CP.TO", "ATD.TO", "DOL.TO", "QSR.TO", "MRU.TO", "SHOP.TO", "GIB-A.TO",
  "WPM.TO", "FNV.TO", "AEM.TO", "ABX.TO", "TECK-B.TO", "NTR.TO", "CCO.TO",
  "BCE.TO", "T.TO", "RCI-B.TO", "CLS.TO", "GWO.TO", "IFC.TO", "IMO.TO"
]);

const NASDAQ_100_MEMBERS = new Set([
  "AAPL", "ADBE", "ADI", "ADP", "AMAT", "AMD", "AMGN", "AMZN", "APP", "ARM", "ASML",
  "AVGO", "BKNG", "CDW", "CHTR", "CMCSA", "COST", "CPRT", "CRWD", "CSCO", "CSX",
  "CDNS", "CTAS", "DASH", "DDOG", "DXCM", "EA", "EXC", "FAST", "FANG", "FTNT", "GILD",
  "GOOG", "GOOGL", "IDXX", "INTC", "INTU", "ISRG", "KDP", "KLAC", "LRCX", "MAR", "MCHP",
  "MDLZ", "META", "MNST", "MRVL", "MSFT", "MU", "NFLX", "NVDA", "NXPI", "ODFL",
  "ORLY", "PANW", "PAYX", "PCAR", "PEP", "PLTR", "QCOM", "REGN", "ROP", "ROST",
  "SBUX", "SHOP", "SNPS", "TEAM", "TMUS", "TSLA", "TTWO", "TXN", "VRTX", "WBD",
  "WDAY", "XEL", "ZS"
]);

const SP_500_MEMBERS = new Set([
  "AAPL", "ABBV", "ABT", "ACN", "ADBE", "AIG", "AMD", "AMGN", "AMT", "AMZN",
  "AMAT", "AVGO", "AXP", "BA", "BAC", "BNY", "BKNG", "BLK", "BMY", "BRK-B", "C", "CAT",
  "CL", "CMCSA", "COF", "COP", "COST", "CRM", "CSCO", "CVS", "CVX", "DHR",
  "DE", "DIS", "DOW", "DUK", "EMR", "FDX", "GD", "GE", "GEV", "GILD", "GM",
  "GOOG", "GOOGL", "GS", "HD", "HON", "IBM", "INTC", "INTU", "JNJ", "JPM",
  "KHC", "KO", "LIN", "LLY", "LMT", "LOW", "MA", "MCD", "MDT", "META",
  "MET", "MMM", "MO", "MRK", "MS", "MSFT", "NEE", "NFLX", "NKE", "NOW", "NVDA", "ORCL",
  "PEP", "PFE", "PG", "PM", "QCOM", "RTX", "SBUX", "SCHW", "SO", "SPG", "T",
  "TGT", "TMO", "TMUS", "TSLA", "TXN", "UBER", "UNH", "UNP", "UPS", "USB", "V", "VZ",
  "WFC", "WMT", "XOM"
]);

const FTSE_100_MEMBERS = new Set([
  "AZN.L", "ULVR.L", "SHEL.L", "BP.L", "HSBA.L", "GSK.L", "RIO.L", "BATS.L",
  "DGE.L", "GLEN.L", "AAL.L", "LSEG.L", "NG.L", "VOD.L", "REL.L", "CPG.L",
  "BAE.L", "SMIN.L", "IMB.L", "CRH.L", "LLOY.L", "RR.L", "SN.L"
]);

const EURO_STOXX_50_MEMBERS = new Set([
  "ASML.AS", "SAP.DE", "SIE.DE", "AIR.PA", "OR.PA", "MC.PA", "SAN.PA", "BNP.PA",
  "ENGI.PA", "AI.PA", "ALV.DE", "DTE.DE", "EL.PA", "RMS.PA", "DG.PA",
  "SAF.PA", "SU.PA", "TTE.PA", "ENEL.MI", "ISP.MI", "ENI.MI", "RACE.MI",
  "STLAM.MI", "ABI.BR", "PHIA.AS", "AD.AS", "MUV2.DE", "RHM.DE",
  "IBE.MC", "ITX.MC"
]);

const ADR_REFERENCES = {
  BHP: ["S&P/ASX 200", "EWA"],
  MUFG: ["TOPIX / Nikkei 225", "EWJ"],
  NVO: ["OMX Copenhagen 25", "EDEN"],
  RHHBY: ["Swiss Market Index", "EWL"],
  SONY: ["TOPIX / Nikkei 225", "EWJ"],
  TM: ["TOPIX / Nikkei 225", "EWJ"],
  TSM: ["TAIEX", "EWT"]
};

const MARKET_COLORS = {
  "Nasdaq-100":    "#4f8ff7",
  "S&P 500":       "#2563eb",
  "S&P/TSX":       "#f87171",
  "FTSE 100":      "#8b5cf6",
  "LSE":           "#a78bfa",
  "Euro STOXX 50": "#10b981",
  "Europe":        "#059669",
  "Global ADR":    "#f59e0b",
  "NYSE / Other":  "#64748b",
};
const CURRENCY_COLORS = {
  USD:   "#4f8ff7",
  CAD:   "#f87171",
  GBP:   "#8b5cf6",
  EUR:   "#10b981",
  CHF:   "#f59e0b",
  Other: "#64748b",
};

function classifyTicker(ticker) {
  const t = String(ticker).toUpperCase();
  if (t.endsWith(".TO")) return { market: "S&P/TSX",      currency: "CAD" };
  if (t.endsWith(".L"))  return { market: FTSE_100_MEMBERS.has(t) ? "FTSE 100" : "LSE", currency: "GBP" };
  if (/\.(DE|PA|AS|MC|BR|IT|CO)$/.test(t)) return { market: EURO_STOXX_50_MEMBERS.has(t) ? "Euro STOXX 50" : "Europe", currency: "EUR" };
  if (t.endsWith(".SW")) return { market: EURO_STOXX_50_MEMBERS.has(t) ? "Euro STOXX 50" : "Europe", currency: "CHF" };
  if (ADR_REFERENCES[t]) return { market: "Global ADR",   currency: "USD" };
  if (NASDAQ_100_MEMBERS.has(t)) return { market: "Nasdaq-100", currency: "USD" };
  if (SP_500_MEMBERS.has(t))     return { market: "S&P 500",    currency: "USD" };
  return                          { market: "NYSE / Other", currency: "USD" };
}

function marketMetadata(ticker, listing = {}) {
  const normalized = String(ticker || "").toUpperCase();
  const dynamicExchange = listing.exchange || listing.fullExchangeName;
  const dynamicCountry = listing.country;
  const dynamicFlag = listing.flag;
  const dynamicSource = listing.source || "Ticker reference";
  if (normalized.endsWith(".TO")) {
    return {
      flag: dynamicFlag || "🇨🇦",
      market: String(dynamicCountry || "CANADA").toUpperCase(),
      exchange: dynamicExchange || "Toronto Stock Exchange (TSX)",
      source: dynamicSource,
      references: TSX_60_MEMBERS.has(normalized)
        ? ["S&P/TSX 60", "XIU.TO"]
        : ["S&P/TSX Composite", "XIC.TO"]
    };
  }
  if (normalized.endsWith(".L")) {
    return {
      flag: dynamicFlag || "🇬🇧",
      market: String(dynamicCountry || "UNITED KINGDOM").toUpperCase(),
      exchange: dynamicExchange || "London Stock Exchange (LSE)",
      source: dynamicSource,
      references: FTSE_100_MEMBERS.has(normalized) ? ["FTSE 100", "ISF.L"] : ["FTSE All-Share", "ISF.L"]
    };
  }
  if (normalized.endsWith(".PA")) {
    return {
      flag: dynamicFlag || "🇫🇷",
      market: String(dynamicCountry || "FRANCE").toUpperCase(),
      exchange: dynamicExchange || "Euronext Paris",
      source: dynamicSource,
      references: EURO_STOXX_50_MEMBERS.has(normalized) ? ["EURO STOXX 50", "FEZ"] : ["CAC 40 / Europe", "EWQ"]
    };
  }
  if (normalized.endsWith(".AS")) {
    return {
      flag: dynamicFlag || "🇳🇱",
      market: String(dynamicCountry || "NETHERLANDS").toUpperCase(),
      exchange: dynamicExchange || "Euronext Amsterdam",
      source: dynamicSource,
      references: EURO_STOXX_50_MEMBERS.has(normalized) ? ["EURO STOXX 50", "FEZ"] : ["AEX / Europe", "EWN"]
    };
  }
  if (normalized.endsWith(".DE")) {
    return {
      flag: dynamicFlag || "🇩🇪",
      market: String(dynamicCountry || "GERMANY").toUpperCase(),
      exchange: dynamicExchange || "Xetra / Frankfurt",
      source: dynamicSource,
      references: EURO_STOXX_50_MEMBERS.has(normalized) ? ["DAX / EURO STOXX 50", "EWG / FEZ"] : ["DAX", "EWG"]
    };
  }
  if (normalized.endsWith(".MI")) {
    return {
      flag: dynamicFlag || "🇮🇹",
      market: String(dynamicCountry || "ITALY").toUpperCase(),
      exchange: dynamicExchange || "Borsa Italiana",
      source: dynamicSource,
      references: EURO_STOXX_50_MEMBERS.has(normalized) ? ["FTSE MIB / EURO STOXX 50", "EWI / FEZ"] : ["FTSE MIB", "EWI"]
    };
  }
  if (normalized.endsWith(".MC")) {
    return { flag: dynamicFlag || "🇪🇸", market: String(dynamicCountry || "SPAIN").toUpperCase(), exchange: dynamicExchange || "Bolsa de Madrid", source: dynamicSource, references: ["IBEX 35 / EURO STOXX 50", "EWP / FEZ"] };
  }
  if (normalized.endsWith(".CO")) {
    return { flag: dynamicFlag || "🇩🇰", market: String(dynamicCountry || "DENMARK").toUpperCase(), exchange: dynamicExchange || "Nasdaq Copenhagen", source: dynamicSource, references: ["OMX Copenhagen 25", "EDEN"] };
  }
  if (normalized.endsWith(".BR")) {
    return { flag: dynamicFlag || "🇧🇪", market: String(dynamicCountry || "BELGIUM").toUpperCase(), exchange: dynamicExchange || "Euronext Brussels", source: dynamicSource, references: ["BEL 20 / Europe", "EWK"] };
  }
  if (normalized.endsWith(".SW")) {
    return { flag: dynamicFlag || "🇨🇭", market: String(dynamicCountry || "SWITZERLAND").toUpperCase(), exchange: dynamicExchange || "SIX Swiss Exchange", source: dynamicSource, references: ["SMI", "EWL"] };
  }
  if (ADR_REFERENCES[normalized]) {
    return {
      flag: dynamicFlag || "🇺🇸",
      market: String(dynamicCountry || "UNITED STATES").toUpperCase(),
      exchange: dynamicExchange || "NYSE / Nasdaq / OTC ADR",
      source: dynamicSource,
      references: ADR_REFERENCES[normalized]
    };
  }

  const references = [];
  if (SP_500_MEMBERS.has(normalized)) references.push("S&P 500", "SPY");
  if (NASDAQ_100_MEMBERS.has(normalized)) references.push("Nasdaq-100", "QQQ");
  if (!references.length) references.push("U.S. Total Market", "VTI");
  return {
    flag: dynamicFlag || "🇺🇸",
    market: String(dynamicCountry || "UNITED STATES").toUpperCase(),
    exchange: dynamicExchange || "NYSE / Nasdaq",
    source: dynamicSource,
    references
  };
}

function financeClass(value, neutral = false) {
  const numeric = Number(value);
  if (neutral || !Number.isFinite(numeric) || numeric === 0) return "finance-neutral";
  return numeric > 0 ? "finance-positive" : "finance-negative";
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  })[character]);
}

function companyLogoUrl(ticker) {
  const normalizedTicker = String(ticker || "").trim().toUpperCase();
  return `/resources/company-logos/${encodeURIComponent(normalizedTicker)}.png`;
}

function animateValue(element, newText) {
  if (element.textContent === newText) return;
  element.classList.remove("counter-flash");
  void element.offsetWidth;
  element.textContent = newText;
  element.classList.add("counter-flash");
}

function setFinanceValue(elementId, value, text, neutral = false) {
  const element = document.getElementById(elementId);
  animateValue(element, text);
  element.classList.remove("finance-positive", "finance-negative", "finance-neutral");
  element.classList.add(financeClass(value, neutral));
}

const pageTitles = {
  overview: "Dashboard",
  research: "Research",
  universe: "Universe",
  console: "Console",
  history: "History",
  reference: "Reference",
  guide: "Guide"
};

const viewAliases = {
  portfolios: "overview",
  models: "reference",
  report: "reference"
};

function showView(viewName) {
  const resolved = viewAliases[viewName] || viewName;
  if (!pageTitles[resolved]) return;
  document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
  const viewId = resolved === "reference" ? "report-view" : `${resolved}-view`;
  const target = document.getElementById(viewId);
  if (target) {
    target.style.animation = "none";
    void target.offsetWidth;
    target.style.animation = "";
    target.classList.add("active");
  }
  document.querySelector(`[data-view="${resolved}"]`)?.classList.add("active");
  document.getElementById("page-title").textContent = pageTitles[resolved];
  history.replaceState(null, "", `#${resolved}`);
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (resolved === "history" && runnerConnected) loadHistoryCatalog();
  if (resolved === "guide") guideLoadMemory();
  alloDockSync(resolved);
}

const donutSegments = {};

function renderDonut(donutId, legendId, segments) {
  donutSegments[donutId] = segments;
  const donut = document.getElementById(donutId);
  const legend = document.getElementById(legendId);
  if (!donut) return;
  let runningTotal = 0;
  const stops = segments.map(([, value, color]) => {
    const start = runningTotal;
    runningTotal += value;
    return `${color} ${start}% ${runningTotal}%`;
  });
  donut.style.background = stops.length
    ? `conic-gradient(${stops.join(",")})`
    : "rgba(255,255,255,0.04)";
  if (legend) {
    legend.innerHTML = segments.length
      ? segments.map(([label, value, color]) => `
          <div class="sector-item">
            <i class="sector-swatch" style="background:${color}"></i>
            <span>${escapeHtml(label)}</span>
            <strong class="finance-neutral">${value.toFixed(1)}%</strong>
          </div>`).join("")
      : '<span class="terminal-muted">Awaiting run</span>';
  }
}

function renderPortfolio(key) {
  const data = portfolioData[key];
  const isMin = key === "min";
  setFinanceValue("portfolio-return", data.metricValues.return, data.metrics.return);
  setFinanceValue("portfolio-risk", data.metricValues.risk, data.metrics.risk, true);
  setFinanceValue("portfolio-sharpe", data.metricValues.sharpe, data.metrics.sharpe);
  setFinanceValue("portfolio-concentration", data.metricValues.concentration, data.metrics.concentration, true);
  document.getElementById("portfolio-note").textContent = data.note;

  const visibleHoldings = data.holdings.filter(([, weight]) => Math.abs(weight) > 0.01);
  document.getElementById("holding-count").textContent = `${visibleHoldings.length} above 0.01%`;
  const maxWeight = Math.max(1e-9, ...visibleHoldings.map((holding) => Math.abs(holding[1])));
  document.getElementById("holdings-bars").innerHTML = visibleHoldings.length ? visibleHoldings.map(([ticker, weight]) => `
    <div class="holding-row ${isMin ? "min" : ""}">
      <button class="holding-ticker" type="button" data-company-ticker="${escapeHtml(ticker)}" title="Open ${escapeHtml(ticker)} company details">${escapeHtml(ticker)}</button>
      <div class="bar-track"><div class="bar-fill${weight < 0 ? " negative" : ""}" style="width:${(Math.abs(weight) / maxWeight) * 100}%"></div></div>
      <span class="holding-weight ${financeClass(weight)}">${weight.toFixed(2)}%</span>
    </div>
  `).join("") : '<div class="empty-state">No completed allocation is available.</div>';

  renderDonut("sector-donut", "sector-legend", data.sectors);
  renderDonut("market-donut", "market-legend", data.markets);
  renderDonut("currency-donut", "currency-legend", data.currencies);
}

// Tiered search: 0=exact, 1=prefix, 2=ticker-contains, 3=secondary-contains, 4=fuzzy
function rankSearch(items, rawQuery, tickerFn, secondaryFn) {
  if (!rawQuery || !rawQuery.trim()) return items;
  const q = rawQuery.trim().toUpperCase();
  function isSubseq(str) {
    let qi = 0;
    const s = str.toUpperCase();
    for (let i = 0; i < s.length && qi < q.length; i++) {
      if (s[i] === q[qi]) qi++;
    }
    return qi === q.length;
  }
  const scored = [];
  for (const item of items) {
    const t = tickerFn(item).toUpperCase();
    const sec = secondaryFn ? secondaryFn(item).toUpperCase() : "";
    let score;
    if (t === q)              score = 0;
    else if (t.startsWith(q)) score = 1;
    else if (t.includes(q))   score = 2;
    else if (sec.includes(q)) score = 3;
    else if (isSubseq(t))     score = 4;
    else if (sec && isSubseq(sec)) score = 5;
    else continue;
    scored.push({ item, score });
  }
  scored.sort((a, b) => a.score - b.score || tickerFn(a.item).localeCompare(tickerFn(b.item)));
  return scored.map((s) => s.item);
}

function renderResearch(query = "") {
  const filtered = rankSearch(
    researchData,
    query,
    (item) => item.ticker,
    (item) => `${item.industry} ${item.thesis}`
  );
  const container = document.getElementById("research-list");
  if (!filtered.length) {
    const hasQuery = query.trim().length > 0;
    container.innerHTML = `<div class="empty-state">${hasQuery ? "No research views match that search." : "No completed research run is available."}</div>`;
    return;
  }
  container.innerHTML = filtered.map((item) => `
    <article class="research-card">
      <div class="ticker-block">
        <div class="ticker-line">
          <button class="research-ticker" type="button" data-company-ticker="${escapeHtml(item.ticker)}" data-company-context="research" title="Open ${escapeHtml(item.ticker)} company details">${escapeHtml(item.ticker)}</button>
          <span class="market-flag" title="${escapeHtml(item.exchange)}">${escapeHtml(item.flag)}</span>
        </div>
        <span>${escapeHtml(item.industry)}</span>
        <div class="market-meta">
          <span class="market-badge">${escapeHtml(item.market)}</span>
          <span class="exchange-label">${escapeHtml(item.exchange)}${item.listingDetails ? ` · ${escapeHtml(item.listingDetails)}` : ""}</span>
          <span class="listing-source">${item.source === "Yahoo Finance" ? "YF LIVE" : "FALLBACK"}</span>
        </div>
        <div class="index-strip">
          <small>INDEX / ETF</small>
          ${item.references.map((reference) => `<b>${escapeHtml(reference)}</b>`).join("")}
        </div>
      </div>
      <div class="research-thesis">${escapeHtml(item.thesis)}</div>
      <div class="research-stat"><span>Posterior return</span><strong class="${financeClass(item.posteriorValue)}">${escapeHtml(item.posterior)}</strong></div>
      <div class="research-stat">
        <span>Confidence</span><strong class="finance-neutral">${Number(item.confidence)}%</strong>
        <div class="confidence-track"><i style="width:${Number(item.confidence)}%"></i></div>
      </div>
    </article>
  `).join("");
}

function formatPercent(value, digits = 1) {
  return Number.isFinite(Number(value)) ? `${(Number(value) * 100).toFixed(digits)}%` : "N/A";
}

function formatDuration(config) {
  const training = Number(config.trainingYears);
  const trainingText = training < 1
    ? `${Math.round(training * 12)} months`
    : `${training.toFixed(training % 1 ? 2 : 0)} ${training === 1 ? "year" : "years"}`;
  const oos = Number(config.oosMonths);
  return {
    training: trainingText,
    oos: oos === 0 ? "Disabled" : `${oos} ${oos === 1 ? "month" : "months"}`
  };
}

function livePortfolio(portfolio, metrics) {
  const holdings = (portfolio.holdings || []).map((item) => [
    item.ticker,
    Number(item.weight) * 100
  ]);
  const grossWeight = holdings.reduce((sum, item) => sum + Math.abs(item[1]), 0);
  const topFive = holdings.slice(0, 5).reduce((sum, item) => sum + Math.abs(item[1]), 0);
  const palette = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#06b6d4", "#f87171", "#ec4899", "#64748b"];
  return {
    metricValues: {
      return: Number(metrics.return),
      risk: Number(metrics.risk),
      sharpe: Number(metrics.sharpe),
      concentration: grossWeight ? topFive / grossWeight : 0
    },
    metrics: {
      return: formatPercent(metrics.return),
      risk: formatPercent(metrics.risk),
      sharpe: Number(metrics.sharpe).toFixed(2),
      concentration: `${(grossWeight ? topFive / grossWeight * 100 : 0).toFixed(1)}%`
    },
    note: `Largest gross sector share is ${portfolio.sectors?.[0]?.sector || "unclassified"} at ${formatPercent(portfolio.sectors?.[0]?.weight || 0)}. Maximum absolute position was constrained by the completed run configuration.`,
    holdings,
    sectors: (portfolio.sectors || []).map((item, index) => [
      item.sector,
      Number(item.weight) * 100,
      palette[index % palette.length]
    ]),
    ...(() => {
      const mkt = {}, cur = {};
      for (const [ticker, weight] of holdings) {
        const abs = Math.abs(weight);
        const { market, currency } = classifyTicker(ticker);
        mkt[market] = (mkt[market] || 0) + abs;
        cur[currency] = (cur[currency] || 0) + abs;
      }
      const total = Object.values(mkt).reduce((s, v) => s + v, 0) || 1;
      const toRows = (map, colorMap) =>
        Object.entries(map)
          .sort((a, b) => b[1] - a[1])
          .map(([label, abs]) => [label, (abs / total) * 100, colorMap[label] || "#64748b"]);
      return { markets: toRows(mkt, MARKET_COLORS), currencies: toRows(cur, CURRENCY_COLORS) };
    })()
  };
}

// The performance payload keys its series by name; the benchmark is whichever
// series is not one of the two model portfolios. Shared by the chart renderer
// and the interactive tooltip so the lookup stays consistent.
function benchmarkSeriesName(series) {
  return Object.keys(series || {}).find((name) => !["Max_Sharpe", "Min_Vol"].includes(name));
}

function chartPath(values, minimum, maximum) {
  if (!values?.length) return "";
  const left = 48;
  const right = 730;
  const top = 35;
  const bottom = 235;
  const span = maximum - minimum || 1;
  return values.map((rawValue, index) => {
    const x = left + (index / Math.max(values.length - 1, 1)) * (right - left);
    const y = bottom - ((Number(rawValue) - minimum) / span) * (bottom - top);
    return `${index === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
  }).join(" ");
}

function renderOverviewMetrics(results) {
  const mode = results.metricsMode || (
    results.oosMetrics ? "oos" :
    results.config?.gptViews ? "ai" : "historical"
  );
  const oosMonths = Number(results.config?.oosMonths || 0);
  const badge = document.getElementById("metrics-mode-badge");
  badge.dataset.mode = mode;

  let maxRet, maxRisk, maxSharpe, minRet, minRisk, minSharpe;

  if (mode === "oos" && results.oosMetrics) {
    ({ return: maxRet, risk: maxRisk, sharpe: maxSharpe } = results.oosMetrics.max);
    ({ return: minRet, risk: minRisk, sharpe: minSharpe } = results.oosMetrics.min);
    document.getElementById("overview-max-return-label").textContent = "Max Sharpe OOS return";
    document.getElementById("overview-max-risk-label").textContent   = "Max Sharpe OOS volatility";
    document.getElementById("overview-min-return-label").textContent = "Min Vol OOS return";
    document.getElementById("overview-min-risk-label").textContent   = "Min Vol OOS volatility";
    document.getElementById("overview-max-return-sub").innerHTML = `Realized Sharpe <span id="overview-max-sharpe">${Number(maxSharpe).toFixed(2)}</span>`;
    document.getElementById("overview-max-risk-sub").textContent  = "Realized annualized volatility";
    document.getElementById("overview-min-return-sub").innerHTML = `Realized Sharpe <span id="overview-min-sharpe">${Number(minSharpe).toFixed(2)}</span>`;
    document.getElementById("overview-min-risk-sub").textContent  = "Realized annualized volatility";
    badge.textContent = `Realized out-of-sample performance · ${oosMonths}-month test window`;
  } else if (mode === "ai") {
    ({ return: maxRet, risk: maxRisk, sharpe: maxSharpe } = results.metrics.max);
    ({ return: minRet, risk: minRisk, sharpe: minSharpe } = results.metrics.min);
    document.getElementById("overview-max-return-label").textContent = "Max Sharpe AI expected return";
    document.getElementById("overview-max-risk-label").textContent   = "Max Sharpe risk";
    document.getElementById("overview-min-return-label").textContent = "Min Vol AI expected return";
    document.getElementById("overview-min-risk-label").textContent   = "Min Vol risk";
    document.getElementById("overview-max-return-sub").innerHTML = `Sharpe <span id="overview-max-sharpe">${Number(maxSharpe).toFixed(2)}</span>`;
    document.getElementById("overview-max-risk-sub").textContent  = "Historical volatility estimate";
    document.getElementById("overview-min-return-sub").innerHTML = `Sharpe <span id="overview-min-sharpe">${Number(minSharpe).toFixed(2)}</span>`;
    document.getElementById("overview-min-risk-sub").textContent  = "Historical volatility estimate";
    badge.textContent = "AI-forecast returns · Historical volatility estimate";
  } else {
    ({ return: maxRet, risk: maxRisk, sharpe: maxSharpe } = results.metrics.max);
    ({ return: minRet, risk: minRisk, sharpe: minSharpe } = results.metrics.min);
    document.getElementById("overview-max-return-label").textContent = "Max Sharpe return";
    document.getElementById("overview-max-risk-label").textContent   = "Max Sharpe risk";
    document.getElementById("overview-min-return-label").textContent = "Min Vol return";
    document.getElementById("overview-min-risk-label").textContent   = "Min Vol risk";
    document.getElementById("overview-max-return-sub").innerHTML = `Sharpe <span id="overview-max-sharpe">${Number(maxSharpe).toFixed(2)}</span>`;
    document.getElementById("overview-max-risk-sub").textContent  = "Annualized volatility";
    document.getElementById("overview-min-return-sub").innerHTML = `Sharpe <span id="overview-min-sharpe">${Number(minSharpe).toFixed(2)}</span>`;
    document.getElementById("overview-min-risk-sub").textContent  = "Annualized volatility";
    badge.textContent = "In-sample training period estimates";
  }

  setFinanceValue("overview-max-return", maxRet, formatPercent(maxRet));
  setFinanceValue("overview-max-risk",   maxRisk, formatPercent(maxRisk), true);
  setFinanceValue("overview-min-return", minRet, formatPercent(minRet));
  setFinanceValue("overview-min-risk",   minRisk, formatPercent(minRisk), true);
}

function renderPerformance(performance) {
  if (!performance?.dates?.length || !performance.series) return;
  performanceCache = performance;
  const maxSeries = performance.series.Max_Sharpe || [];
  const minSeries = performance.series.Min_Vol || [];
  const benchmarkName = benchmarkSeriesName(performance.series);
  const benchmarkSeries = benchmarkName ? performance.series[benchmarkName] : [];
  const allValues = [...maxSeries, ...minSeries, ...benchmarkSeries].map(Number).filter(Number.isFinite);
  if (!allValues.length) return;
  const minimum = Math.min(...allValues);
  const maximum = Math.max(...allValues);
  document.getElementById("chart-max").setAttribute("d", chartPath(maxSeries, minimum, maximum));
  document.getElementById("chart-min").setAttribute("d", chartPath(minSeries, minimum, maximum));
  document.getElementById("chart-benchmark").setAttribute("d", chartPath(benchmarkSeries, minimum, maximum));

  if (maxSeries.length) {
    const areaPath = chartPath(maxSeries, minimum, maximum);
    const lastX = 48 + ((maxSeries.length - 1) / Math.max(maxSeries.length - 1, 1)) * (730 - 48);
    document.getElementById("chart-area").setAttribute("d", `${areaPath} L${lastX.toFixed(1)} 250 L48 250 Z`);
  }

  document.querySelectorAll(".chart-path").forEach((path) => {
    path.classList.remove("chart-draw");
    void path.offsetWidth;
    path.classList.add("chart-draw");
  });

  const dates = performance.dates;
  const labelIndexes = [...new Set([0, Math.floor((dates.length - 1) / 2), dates.length - 1])];
  document.getElementById("chart-axis-labels").innerHTML = labelIndexes.map((index, position) => {
    const date = new Date(dates[index]);
    const x = 48 + (index / Math.max(dates.length - 1, 1)) * (730 - 48);
    const anchor = position === 0 ? "start" : position === labelIndexes.length - 1 ? "end" : "middle";
    const label = date.toLocaleDateString(undefined, { month: "short", year: "numeric" });
    return `<text x="${x.toFixed(1)}" y="275" text-anchor="${anchor}">${label}</text>`;
  }).join("");
}

function applyLiveResults(results) {
  if (!results?.metrics || !results?.portfolios || !results?.config) return;
  const isExample = results.dataMode === "example";
  const isHistory = results.dataMode === "history";
  currentResultMode = isExample ? "example" : isHistory ? "history" : "live";
  currentResultGeneratedAt = results.generatedAt || null;
  currentHistoryRunId = isHistory ? (results.archive?.id || currentHistoryRunId) : null;
  const durations = formatDuration(results.config);
  document.getElementById("hero-training").textContent = durations.training;
  document.getElementById("hero-oos").textContent = durations.oos;
  document.getElementById("hero-cap").textContent = `${Number(results.config.maxPositionPercent).toFixed(0)}%`;
  document.getElementById("data-date").textContent = isExample
    ? `${results.snapshotLabel || "Bundled example"} · Data through ${results.dataThrough || "snapshot date"}`
    : isHistory
      ? `Archived ${new Date(results.generatedAt).toLocaleString()} · Data through ${results.dataThrough || "run date"}`
      : `Live run · Data through ${results.dataThrough || "latest completed run"}`;
  document.getElementById("data-mode").textContent = isExample
    ? "ALLOLABS SNAPSHOT"
    : isHistory ? "ALLOLABS HISTORY" : "ALLOLABS LIVE";
  document.getElementById("run-label").textContent = isExample
    ? "Bundled example portfolio"
    : isHistory ? "Archived model run" : "Latest model run";

  renderOverviewMetrics(results);

  portfolioData = {
    max: livePortfolio(results.portfolios.max, results.metrics.max),
    min: livePortfolio(results.portfolios.min, results.metrics.min)
  };
  const selectedPortfolio = document.querySelector("[data-portfolio].active")?.dataset.portfolio || "max";
  renderPortfolio(selectedPortfolio);

  researchData = (results.research || [])
    .filter((item) => item.view)
    .map((item) => {
      const market = marketMetadata(item.ticker, item.listing);
      return {
        ticker: item.ticker,
        industry: `${item.sector || "Unclassified"} / ${item.industry || "Not classified"}`,
        posterior: formatPercent(item.posteriorReturn),
        posteriorValue: Number(item.posteriorReturn),
        confidence: Math.round(Number(item.confidence || 0) * 100),
        thesis: item.view,
        listingDetails: [item.listing?.exchangeCode, item.listing?.currency].filter(Boolean).join(" · "),
        ...market
      };
    });
  renderResearch(document.getElementById("research-search").value);

  document.getElementById("remote-training").value = results.config.trainingYears;
  document.getElementById("remote-oos").value = results.config.oosMonths;
  document.getElementById("remote-position").value = results.config.maxPositionPercent;
  document.getElementById("remote-long-only").checked = results.config.longOnly !== false;
  document.getElementById("remote-gpt").checked = Boolean(results.config.gptViews);
  const researchProvider = results.config.researchProvider || "openai";
  document.getElementById("remote-research-provider").value = researchProvider;
  populateModelSelect(
    document.getElementById("remote-gpt-model"),
    "research",
    researchProvider,
    results.config.researchModel || results.config.gptModel || "gpt-5.4"
  );
  document.getElementById("remote-audit").checked = Boolean(results.config.auditViews);
  const auditProvider = results.config.auditProvider || "openai";
  document.getElementById("remote-audit-provider").value = auditProvider;
  populateModelSelect(
    document.getElementById("remote-audit-model"),
    "audit",
    auditProvider,
    results.config.auditModel || "gpt-5.5"
  );
  const legacySectorCapDisabled = results.config.sectorCapEnabled === false;
  document.getElementById("remote-sector-cap").value = legacySectorCapDisabled
    ? 100
    : (results.config.maxSectorPercent ?? 100);
  document.getElementById("remote-regularization").value = results.config.regularization || "none";
  document.getElementById("remote-regularization-strength").value = results.config.regularizationStrength ?? 0.10;
  document.getElementById("remote-refresh").checked = Boolean(results.config.refreshCache);
  document.getElementById("remote-analyst-seed").value = results.config.analystSeedPrompt || "";
  document.getElementById("remote-auditor-seed").value = results.config.auditorSeedPrompt || "";
  document.getElementById("remote-max-news").value = results.config.maxNewsArticles ?? 5;
  document.getElementById("remote-batch-size").value = results.config.researchBatchSize ?? 12;
  syncConfigurationControls();
  renderPerformance(results.performance);
}

document.querySelectorAll(".nav-item").forEach((item) => {
  item.addEventListener("click", () => showView(item.dataset.view));
});

document.querySelectorAll("[data-shortcut-view]").forEach((item) => {
  item.addEventListener("click", () => showView(item.dataset.shortcutView));
});

const functionViews = ["overview", "research", "universe", "console", "history", "reference", "guide"];
document.addEventListener("keydown", (event) => {
  const match = /^F([1-7])$/.exec(event.key);
  if (!match) return;
  event.preventDefault();
  showView(functionViews[Number(match[1]) - 1]);
});

function orderedUniverseSelection() {
  if (!universeCatalogData) return [...selectedUniverseTickers];
  return universeCatalogData.groups
    .flatMap((group) => group.tickers)
    .filter((ticker) => selectedUniverseTickers.has(ticker));
}

function matchingUniversePreset() {
  if (!universeCatalogData) return null;
  return universeCatalogData.presets.find((preset) =>
    preset.tickers.length === selectedUniverseTickers.size
    && preset.tickers.every((ticker) => selectedUniverseTickers.has(ticker))
  ) || null;
}

function saveUniverseSelection() {
  localStorage.setItem(UNIVERSE_STORAGE_KEY, JSON.stringify(orderedUniverseSelection()));
}

function setUniverseSelection(tickers, persist = true) {
  const allowed = universeCatalogData
    ? new Set(universeCatalogData.groups.flatMap((group) => group.tickers))
    : null;
  selectedUniverseTickers = new Set(
    (Array.isArray(tickers) ? tickers : [])
      .map((ticker) => String(ticker).trim().toUpperCase())
      .filter((ticker) => ticker && (!allowed || allowed.has(ticker)))
  );
  if (persist && universeCatalogData) saveUniverseSelection();
  renderUniverseSelector();
}

function universeSelectionLabel() {
  return matchingUniversePreset()?.label || "Custom universe";
}

function renderUniverseSelector() {
  const selectedCount = selectedUniverseTickers.size;
  document.getElementById("universe-selected-count").textContent = selectedCount;
  document.getElementById("console-universe-count").textContent = universeCatalogData
    ? `${selectedCount} securities · ${universeSelectionLabel()}`
    : "Connect to choose securities";
  document.getElementById("universe-selection-label").textContent = universeCatalogData
    ? universeSelectionLabel()
    : "No universe loaded";
  document.getElementById("universe-selection-detail").textContent = universeCatalogData
    ? `${selectedCount} of ${universeCatalogData.tickerCount} supported securities selected for the next run.`
    : "Connect to view available securities.";
  if (!universeCatalogData) return;

  const matchingPreset = matchingUniversePreset();
  document.getElementById("universe-presets").innerHTML = universeCatalogData.presets.map((preset) => `
    <button class="universe-preset${matchingPreset?.id === preset.id ? " active" : ""}" type="button" data-universe-preset="${escapeHtml(preset.id)}">
      <span>${escapeHtml(preset.label)}</span>
      <strong>${preset.tickers.length}</strong>
      <small>${escapeHtml(preset.description)}</small>
    </button>
  `).join("");

  document.getElementById("universe-market-jump").innerHTML = [
    `<button type="button" class="${activeUniverseMarket === "all" ? "active" : ""}" data-universe-market="all">All markets</button>`,
    ...universeCatalogData.groups.map((group) => {
      const count = group.tickers.filter((ticker) => selectedUniverseTickers.has(ticker)).length;
      return `<button type="button" class="${activeUniverseMarket === group.id ? "active" : ""}" data-universe-market="${escapeHtml(group.id)}">${escapeHtml(group.shortLabel)} <b>${count}/${group.tickers.length}</b></button>`;
    })
  ].join("");

  const query = document.getElementById("universe-search").value.trim().toUpperCase();
  const visibleGroups = universeCatalogData.groups.filter((group) =>
    activeUniverseMarket === "all" || activeUniverseMarket === group.id
  );

  const groupMarkup = visibleGroups.map((group) => {
    const tickers = query
      ? rankSearch(group.tickers, query, (t) => t, null)
      : group.tickers;
    if (!tickers.length) return "";
    const groupSelected = group.tickers.filter((ticker) => selectedUniverseTickers.has(ticker)).length;
    // Auto-expand when searching or when this specific market is focused
    const forceExpand = !!query || activeUniverseMarket === group.id;
    const isCollapsed = !forceExpand && collapsedGroups.has(group.id);
    return `
      <article class="universe-group${isCollapsed ? " collapsed" : ""}" data-universe-group="${escapeHtml(group.id)}">
        <header class="universe-group-header" data-universe-group-toggle="${escapeHtml(group.id)}">
          <div class="universe-group-title">
            <p class="eyebrow">${escapeHtml(group.shortLabel)}</p>
            <h4>${escapeHtml(group.label)}</h4>
            <span>${escapeHtml(group.description)}</span>
          </div>
          <div class="universe-group-actions">
            <strong>${groupSelected}/${group.tickers.length}</strong>
            <button class="universe-group-toggle-btn" type="button" aria-label="${isCollapsed ? "Expand" : "Collapse"}" data-universe-group-toggle="${escapeHtml(group.id)}">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="${isCollapsed ? "M3 5l4 4 4-4" : "M3 9l4-4 4 4"}" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </button>
            <button type="button" data-universe-group-action="select" data-universe-group-id="${escapeHtml(group.id)}">Select all</button>
            <button type="button" data-universe-group-action="clear" data-universe-group-id="${escapeHtml(group.id)}">Clear</button>
          </div>
        </header>
        <div class="universe-ticker-grid">
          ${tickers.map((ticker) => `
            <label class="universe-ticker${selectedUniverseTickers.has(ticker) ? " selected" : ""}">
              <input type="checkbox" data-universe-ticker="${escapeHtml(ticker)}"${selectedUniverseTickers.has(ticker) ? " checked" : ""}>
              <i aria-hidden="true">&#10003;</i>
              <span>${escapeHtml(ticker)}</span>
            </label>
          `).join("")}
        </div>
      </article>
    `;
  }).join("");
  document.getElementById("universe-groups").innerHTML = groupMarkup
    || '<div class="empty-state">No markets or tickers match that search.</div>';
}

async function loadUniverseCatalog() {
  universeCatalogData = await runnerRequest("/api/universe");
  // Start with all groups collapsed in the "all markets" view — each has 100+ tickers
  collapsedGroups = new Set(universeCatalogData.groups.map((g) => g.id));
  let selection = null;
  try {
    const stored = JSON.parse(localStorage.getItem(UNIVERSE_STORAGE_KEY) || "null");
    if (Array.isArray(stored)) {
      const supported = new Set(universeCatalogData.groups.flatMap((group) => group.tickers));
      const validStored = stored.filter((ticker) => supported.has(String(ticker).toUpperCase()));
      if (validStored.length >= 2) selection = validStored;
    }
  } catch {
    localStorage.removeItem(UNIVERSE_STORAGE_KEY);
  }
  if (!selection && pendingUniverseConfig?.selectedTickers) {
    selection = pendingUniverseConfig.selectedTickers;
  } else if (!selection && pendingUniverseConfig?.universe) {
    selection = universeCatalogData.presets.find(
      (preset) => preset.id === pendingUniverseConfig.universe
    )?.tickers;
  }
  if (!selection) selection = universeCatalogData.presets[0].tickers;
  pendingUniverseConfig = null;
  setUniverseSelection(selection, false);
}

document.getElementById("universe-presets").addEventListener("click", (event) => {
  const button = event.target.closest("[data-universe-preset]");
  if (!button || !universeCatalogData) return;
  const preset = universeCatalogData.presets.find((item) => item.id === button.dataset.universePreset);
  if (preset) setUniverseSelection(preset.tickers);
});

document.getElementById("universe-market-jump").addEventListener("click", (event) => {
  const button = event.target.closest("[data-universe-market]");
  if (!button) return;
  const newMarket = button.dataset.universeMarket;
  if (newMarket !== "all" && newMarket !== activeUniverseMarket) {
    // Auto-expand the selected market group, collapse all others
    collapsedGroups = new Set(
      (universeCatalogData?.groups || [])
        .map((g) => g.id)
        .filter((id) => id !== newMarket)
    );
  } else if (newMarket === "all") {
    // Returning to all-markets view: collapse everything (user can open as needed)
    collapsedGroups = new Set((universeCatalogData?.groups || []).map((g) => g.id));
  }
  activeUniverseMarket = newMarket;
  renderUniverseSelector();
});

document.getElementById("universe-groups").addEventListener("click", (event) => {
  // Accordion toggle — header click or toggle button click
  const toggle = event.target.closest("[data-universe-group-toggle]");
  if (toggle && !event.target.closest("[data-universe-group-action]")) {
    const groupId = toggle.dataset.universeGroupToggle;
    if (collapsedGroups.has(groupId)) collapsedGroups.delete(groupId);
    else collapsedGroups.add(groupId);
    renderUniverseSelector();
    return;
  }
  // Select / Clear action buttons
  const button = event.target.closest("[data-universe-group-action]");
  if (!button || !universeCatalogData) return;
  const group = universeCatalogData.groups.find((item) => item.id === button.dataset.universeGroupId);
  if (!group) return;
  const next = new Set(selectedUniverseTickers);
  group.tickers.forEach((ticker) => {
    if (button.dataset.universeGroupAction === "select") next.add(ticker);
    else next.delete(ticker);
  });
  setUniverseSelection([...next]);
});

document.getElementById("universe-groups").addEventListener("change", (event) => {
  const checkbox = event.target.closest("[data-universe-ticker]");
  if (!checkbox) return;
  const next = new Set(selectedUniverseTickers);
  if (checkbox.checked) next.add(checkbox.dataset.universeTicker);
  else next.delete(checkbox.dataset.universeTicker);
  setUniverseSelection([...next]);
});

document.getElementById("universe-search").addEventListener("input", renderUniverseSelector);
document.getElementById("universe-clear").addEventListener("click", () => setUniverseSelection([]));
renderUniverseSelector();

renderModelGuide();
renderProviderKeyStatus();

document.getElementById("provider-key-status")?.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy-provider-command]");
  if (!button) return;
  const originalLabel = button.textContent;
  try {
    await navigator.clipboard.writeText(button.dataset.copyProviderCommand);
    button.textContent = "Copied";
  } catch {
    button.textContent = "Unavailable";
  }
  window.setTimeout(() => {
    button.textContent = originalLabel;
  }, 1400);
});

function updateTerminalClock() {
  const clock = document.getElementById("terminal-clock");
  if (!clock) return;
  clock.textContent = `${new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Toronto",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  }).format(new Date())} ET`;
}

updateTerminalClock();
setInterval(updateTerminalClock, 1000);

document.querySelectorAll("[data-go]").forEach((item) => {
  item.addEventListener("click", (event) => {
    event.preventDefault();
    showView(item.dataset.go);
  });
});

document.getElementById("configure-button").addEventListener("click", () => showView("console"));
document.getElementById("open-report-button").addEventListener("click", () => {
  showView("reference");
  if (runnerConnected) refreshReportArtifacts();
});

document.querySelectorAll("[data-portfolio]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-portfolio]").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    renderPortfolio(button.dataset.portfolio);
  });
});

document.getElementById("research-search").addEventListener("input", (event) => {
  renderResearch(event.target.value);
});

const remoteGptToggle = document.getElementById("remote-gpt");
const remoteAuditToggle = document.getElementById("remote-audit");
const remoteResearchProvider = document.getElementById("remote-research-provider");
const remoteAuditProvider = document.getElementById("remote-audit-provider");
const remoteGptModel = document.getElementById("remote-gpt-model");
const remoteAuditModel = document.getElementById("remote-audit-model");
const sectorCapInput = document.getElementById("remote-sector-cap");
const regularizationSelect = document.getElementById("remote-regularization");
const longOnlyToggle = document.getElementById("remote-long-only");
const regularizationStrength = document.getElementById("remote-regularization-strength");

function syncConfigurationControls() {
  remoteAuditToggle.disabled = !remoteGptToggle.checked;
  remoteResearchProvider.disabled = !remoteGptToggle.checked;
  remoteGptModel.disabled = !remoteGptToggle.checked;
  if (!remoteGptToggle.checked) remoteAuditToggle.checked = false;
  remoteAuditProvider.disabled = !remoteAuditToggle.checked;
  remoteAuditModel.disabled = !remoteAuditToggle.checked;
  regularizationStrength.disabled = regularizationSelect.value === "none";
}

remoteGptToggle.addEventListener("change", syncConfigurationControls);
remoteAuditToggle.addEventListener("change", syncConfigurationControls);
remoteResearchProvider.addEventListener("change", () => {
  populateModelSelect(remoteGptModel, "research", remoteResearchProvider.value);
  document.getElementById("remote-refresh").checked = true;
});
remoteAuditProvider.addEventListener("change", () => {
  populateModelSelect(remoteAuditModel, "audit", remoteAuditProvider.value);
});
remoteGptModel.addEventListener("change", () => {
  document.getElementById("remote-refresh").checked = true;
});
regularizationSelect.addEventListener("change", syncConfigurationControls);
populateModelSelect(remoteGptModel, "research", remoteResearchProvider.value, "gpt-5.4");
populateModelSelect(remoteAuditModel, "audit", remoteAuditProvider.value, "gpt-5.5");
syncConfigurationControls();
restoreConsoleConfig();

const runnerUrl = document.getElementById("runner-url");
const runnerToken = document.getElementById("runner-token");
const runnerState = document.getElementById("runner-state");
const runnerStart = document.getElementById("runner-start");
const runnerStop = document.getElementById("runner-stop");
const terminalOutput = document.getElementById("terminal-output");
const terminalRunId = document.getElementById("terminal-run-id");
const terminalLineCount = document.getElementById("terminal-line-count");
let runnerConnected = false;
let runnerOffset = 0;
let runnerPollTimer = null;
let terminalLines = 0;
let loadedResultRunId = null;
let legacyRunnerNoticeShown = false;
let pdfBlobUrl = null;
let chartBlobUrl = null;
let runnerCapabilities = {};
let artifactCompatibilityNoticeShown = false;
let analysisEnvironmentReady = false;
let currentResultMode = "empty";
let currentResultGeneratedAt = null;
let currentHistoryRunId = null;
let historyRuns = [];
let selectedHistoryRun = null;
let selectedHistoryResults = null;
const runProgressElement = document.getElementById("run-progress");
const runProgressTrack = document.getElementById("run-progress-track");
const runProgressFill = document.getElementById("run-progress-fill");
const runProgressStage = document.getElementById("run-progress-stage");
const runProgressPercent = document.getElementById("run-progress-percent");
const runProgressDetail = document.getElementById("run-progress-detail");
let runProgressTimer = null;
let runProgressState = null;

const hostedRunnerUrl = location.protocol === "http:" || location.protocol === "https:"
  ? location.origin
  : runnerUrl.value;
const desktopParameters = new URLSearchParams(location.search);
const desktopToken = desktopParameters.get("desktopToken");
const desktopMode = desktopParameters.get("desktop") === "1";
if (desktopToken) runnerToken.value = desktopToken;
runnerUrl.value = desktopMode
  ? hostedRunnerUrl
  : (localStorage.getItem("allolabs-runner-url") || hostedRunnerUrl);
if (desktopMode) {
  document.documentElement.dataset.desktop = "true";
  history.replaceState({}, document.title, `${location.pathname}${location.hash}`);
}

function runnerHeaders(includeJson = false) {
  const headers = {};
  if (includeJson) headers["Content-Type"] = "application/json";
  if (runnerToken.value) headers.Authorization = `Bearer ${runnerToken.value}`;
  return headers;
}

function runnerEndpoint(path) {
  return `${runnerUrl.value.trim().replace(/\/+$/, "")}${path}`;
}

function activateProjectLogo(apiVersion) {
  if (Number(apiVersion || 0) < 13) return;
  const logoPath = "/resources/allolabs-logo.png";
  document.querySelectorAll("[data-project-logo]").forEach((image) => {
    if (image.dataset.loaded === "true") return;
    const fallback = image.parentElement.querySelector(".brand-mark-fallback");
    image.addEventListener("load", () => {
      image.hidden = false;
      if (fallback) fallback.hidden = true;
      image.dataset.loaded = "true";
    }, { once: true });
    image.addEventListener("error", () => {
      image.hidden = true;
      if (fallback) fallback.hidden = false;
    }, { once: true });
    image.src = logoPath;
  });
  if (!document.querySelector('link[data-project-icon]')) {
    ["icon", "apple-touch-icon"].forEach((relationship) => {
      const icon = document.createElement("link");
      icon.rel = relationship;
      icon.href = logoPath;
      icon.dataset.projectIcon = "true";
      document.head.appendChild(icon);
    });
  }
}

// Wraps fetch with an AbortController timeout so a hung connection can never
// leave a spinner spinning forever. Rejects with the underlying error (an
// AbortError when the timeout fires).
function fetchWithTimeout(url, options = {}, timeoutMs = 30000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, { ...options, signal: controller.signal })
    .finally(() => clearTimeout(timer));
}

async function runnerRequest(path, options = {}, timeoutMs = 30000) {
  let response;
  try {
    response = await fetchWithTimeout(runnerEndpoint(path), {
      ...options,
      headers: { ...runnerHeaders(Boolean(options.body)), ...(options.headers || {}) }
    }, timeoutMs);
  } catch (networkError) {
    const error = new Error(
      networkError?.name === "AbortError"
        ? `Runner request timed out after ${Math.round(timeoutMs / 1000)}s`
        : "Network error — unable to reach the runner service"
    );
    error.cause = networkError;
    throw error;
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(payload.error || `Runner returned HTTP ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return payload;
}

function closeCompanyModal() {
  const modal = document.getElementById("company-modal");
  modal.hidden = true;
  document.body.classList.remove("modal-open");
  if (companyModalTrigger) companyModalTrigger.focus();
  companyModalTrigger = null;
}

function safeNewsUrl(value) {
  try {
    const url = new URL(String(value || ""));
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch {
    return "";
  }
}

function renderCompanyDetails(details) {
  const ratios = Object.entries(details.ratios || {});
  const news = (details.news || []).slice(0, 5);
  const logoUrl = companyLogoUrl(details.ticker);
  const fetchedAt = details.fetchedAt
    ? new Date(details.fetchedAt).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
    : "Current lookup";
  document.getElementById("company-modal-title").textContent = details.name || details.ticker;
  document.getElementById("company-modal-subtitle").textContent = details.ticker;
  document.getElementById("company-modal-body").innerHTML = `
    <section class="company-brand-card">
      <div class="company-logo-shell">
        <img id="company-logo" src="${escapeHtml(logoUrl)}" alt="${escapeHtml(details.name || details.ticker)} logo">
        <span id="company-logo-fallback">${escapeHtml(details.ticker.slice(0, 3))}</span>
      </div>
      <div>
        <span>Listed company</span>
        <strong>${escapeHtml(details.name || details.ticker)}</strong>
        <small>${escapeHtml(details.ticker)}</small>
      </div>
    </section>
    <section>
      <div class="company-section-title">
        <h3>Fundamental ratios</h3>
        <span>Same inputs supplied to AI research</span>
      </div>
      ${ratios.length ? `
        <div class="company-ratio-grid">
          ${ratios.map(([label, value]) => `
            <div class="company-ratio">
              <span>${escapeHtml(label)}</span>
              <strong>${escapeHtml(value)}</strong>
            </div>
          `).join("")}
        </div>
      ` : '<div class="company-empty">Yahoo Finance did not return ratio data for this security.</div>'}
    </section>
    <section>
      <div class="company-section-title">
        <h3>Latest headlines</h3>
        <span>Up to five Yahoo Finance stories</span>
      </div>
      ${news.length ? `
        <ol class="company-news-list">
          ${news.map((item) => {
            const articleUrl = safeNewsUrl(item.url);
            const headline = articleUrl
              ? `<a class="company-news-link" href="${escapeHtml(articleUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title)}</a>`
              : `<strong>${escapeHtml(item.title)}</strong>`;
            return `
            <li class="company-news-item${articleUrl ? " is-linked" : ""}">
              ${headline}
              <div class="company-news-meta">
                <span>${escapeHtml(item.source || "Unknown source")}</span>
                ${item.date ? `<span>${escapeHtml(item.date)}</span>` : ""}
                ${articleUrl ? "<span>Open article</span>" : ""}
              </div>
            </li>
          `;
          }).join("")}
        </ol>
      ` : '<div class="company-empty">No recent Yahoo Finance headlines were available.</div>'}
    </section>
    <div class="company-data-note">
      <span>${escapeHtml(details.source || "Yahoo Finance")} · fetched ${escapeHtml(fetchedAt)}</span>
      <a href="https://logo.dev" target="_blank" rel="noopener noreferrer">Locally cached logos provided by Logo.dev</a>
    </div>
  `;
  const logo = document.getElementById("company-logo");
  const fallback = document.getElementById("company-logo-fallback");
  logo.addEventListener("load", () => {
    logo.hidden = false;
    fallback.hidden = true;
  });
  logo.addEventListener("error", () => {
    logo.hidden = true;
    fallback.hidden = false;
  });
}

async function openCompanyModal(ticker, trigger) {
  const modal = document.getElementById("company-modal");
  companyModalTrigger = trigger;
  modal.hidden = false;
  document.body.classList.add("modal-open");
  document.getElementById("company-modal-title").textContent = ticker;
  document.getElementById("company-modal-subtitle").textContent = "Loading company snapshot";
  document.getElementById("company-modal-body").innerHTML = '<div class="company-loading">Loading fundamentals and recent headlines from Yahoo Finance...</div>';
  document.getElementById("company-modal-close").focus();

  if (!runnerConnected) {
    document.getElementById("company-modal-body").innerHTML = '<div class="company-error">Connect to the AlloLabs runner to load company details.</div>';
    return;
  }
  if (!runnerCapabilities.company_details) {
    document.getElementById("company-modal-body").innerHTML = '<div class="company-error">Restart the dashboard server to enable company-detail lookups.</div>';
    return;
  }
  if (trigger?.dataset.companyContext === "research" && !runnerCapabilities.research_company_details) {
    document.getElementById("company-modal-body").innerHTML = '<div class="company-error">Restart the dashboard server to enable company details from AI Research.</div>';
    return;
  }

  try {
    const historyQuery = currentHistoryRunId ? `&run=${encodeURIComponent(currentHistoryRunId)}` : "";
    const cacheKey = `${currentHistoryRunId || "current"}:${ticker}`;
    let details = companyDetailsCache.get(cacheKey);
    if (!details) {
      details = await runnerRequest(`/api/company?ticker=${encodeURIComponent(ticker)}${historyQuery}`);
      companyDetailsCache.set(cacheKey, details);
    }
    renderCompanyDetails(details);
  } catch (error) {
    document.getElementById("company-modal-subtitle").textContent = ticker;
    document.getElementById("company-modal-body").innerHTML = `<div class="company-error">${escapeHtml(error.message)}</div>`;
  }
}

document.getElementById("holdings-bars").addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-company-ticker]");
  if (trigger) openCompanyModal(trigger.dataset.companyTicker, trigger);
});
document.getElementById("research-list").addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-company-ticker]");
  if (trigger) openCompanyModal(trigger.dataset.companyTicker, trigger);
});
document.getElementById("company-modal-close").addEventListener("click", closeCompanyModal);
document.getElementById("company-modal").addEventListener("click", (event) => {
  if (event.target.id === "company-modal") closeCompanyModal();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !document.getElementById("company-modal").hidden) {
    closeCompanyModal();
  }
});

function setRunnerState(status, label) {
  runnerState.className = `runner-state ${status}`;
  runnerState.querySelector("strong").textContent = label;
  const running = status === "running";
  runnerStart.disabled = !runnerConnected || !analysisEnvironmentReady || running;
  runnerStop.disabled = !runnerConnected || !running;
}

function applyRunConfig(config) {
  if (!config) return;
  const durations = formatDuration(config);
  document.getElementById("hero-training").textContent = durations.training;
  document.getElementById("hero-oos").textContent = durations.oos;
  document.getElementById("hero-cap").textContent = `${Number(config.maxPositionPercent).toFixed(0)}%`;
}

function estimatedUniverseSize(config = {}) {
  if (Array.isArray(config.selectedTickers)) return config.selectedTickers.length;
  if (config.universe === "canada") return 51;
  if (config.universe === "curated") return 39;
  return universeCatalogData?.tickerCount || 285;
}

function buildRunProgressPlan(config = {}) {
  const universeSize = estimatedUniverseSize(config);
  const stages = [
    { id: "setup", label: "Starting run", seconds: 6 },
    {
      id: "data",
      label: "Downloading and cleaning market data",
      seconds: 24 + Math.max(0, Number(config.trainingYears || 1) - 1) * 4
    }
  ];
  if (config.gptViews) {
    const batchCount = Math.ceil(universeSize / 12);
    const researchSeconds = config.refreshCache
      ? 25 + universeSize * 0.75 + batchCount * 30
      : 18 + universeSize * 0.18 + batchCount * 10;
    stages.push({
      id: "research",
      label: "AI equity research",
      seconds: researchSeconds,
      detail: `${universeSize} securities · ${config.refreshCache ? "refresh requested" : "cache-aware"}`
    });
    if (config.auditViews) {
      stages.push({
        id: "audit",
        label: "Global AI consistency audit",
        seconds: 110 + universeSize * 0.8,
        detail: `${universeSize} views in one full-universe review`
      });
    }
  }
  stages.push({ id: "optimization", label: "Portfolio optimization", seconds: 22 });
  if (Number(config.oosMonths || 0) > 0) {
    stages.push({
      id: "oos",
      label: "Out-of-sample analysis",
      seconds: 32 + Number(config.oosMonths) * 1.5,
      detail: `${Number(config.oosMonths)}-month test window`
    });
  }
  stages.push({ id: "report", label: "Generating report artifacts", seconds: 24 });
  stages.push({ id: "results", label: "Publishing dashboard results", seconds: 8 });
  const totalSeconds = stages.reduce((sum, stage) => sum + stage.seconds, 0);
  let elapsed = 0;
  stages.forEach((stage) => {
    stage.start = elapsed / totalSeconds;
    elapsed += stage.seconds;
    stage.end = elapsed / totalSeconds;
  });
  return { stages, totalSeconds, universeSize };
}

function renderRunProgress() {
  if (!runProgressState) return;
  const state = runProgressState;
  const stage = state.plan.stages[state.stageIndex];
  if (!stage) return;
  const elapsedSeconds = Math.max(0, (Date.now() - state.stageStartedAt) / 1000);
  const timedFraction = Math.min(0.92, (1 - Math.exp(-elapsedSeconds / Math.max(stage.seconds, 1))) * 0.95);
  const stageFraction = Math.max(state.observedFraction, timedFraction);
  const calculated = (stage.start + (stage.end - stage.start) * stageFraction) * 100;
  state.displayed = Math.max(state.displayed, Math.min(calculated, 99));
  const rounded = Math.floor(state.displayed);
  runProgressFill.style.width = `${state.displayed.toFixed(2)}%`;
  runProgressTrack.setAttribute("aria-valuenow", String(rounded));
  runProgressPercent.textContent = `${rounded}%`;
  runProgressStage.textContent = state.stageLabel || stage.label;
  runProgressDetail.textContent = state.detail || stage.detail || "Estimated from terminal milestones and run configuration.";
}

function beginRunProgress(config, startedAt = Date.now()) {
  const plan = buildRunProgressPlan(config);
  runProgressState = {
    plan,
    stageIndex: 0,
    stageStartedAt: startedAt,
    observedFraction: 0,
    displayed: 0,
    stageLabel: plan.stages[0].label,
    detail: `Estimated run time ${Math.max(1, Math.round(plan.totalSeconds / 60))} min · ${plan.universeSize} security research universe`
  };
  runProgressElement.classList.remove("failed", "completed");
  clearInterval(runProgressTimer);
  runProgressTimer = setInterval(renderRunProgress, 700);
  renderRunProgress();
}

function setRunProgressStage(stageId, fraction = 0, detail = "") {
  if (!runProgressState) return;
  const nextIndex = runProgressState.plan.stages.findIndex((stage) => stage.id === stageId);
  if (nextIndex < 0 || nextIndex < runProgressState.stageIndex) return;
  if (nextIndex > runProgressState.stageIndex) {
    const previous = runProgressState.plan.stages[nextIndex - 1];
    runProgressState.displayed = Math.max(runProgressState.displayed, previous.end * 100);
    runProgressState.stageIndex = nextIndex;
    runProgressState.stageStartedAt = Date.now();
    runProgressState.observedFraction = 0;
  }
  runProgressState.observedFraction = Math.max(
    runProgressState.observedFraction,
    Math.min(Math.max(fraction, 0), 0.99)
  );
  runProgressState.stageLabel = runProgressState.plan.stages[nextIndex].label;
  if (detail) runProgressState.detail = detail;
  renderRunProgress();
}

function processRunProgressLine(text) {
  if (!runProgressState || !text) return;
  const line = String(text);
  let match;
  if (line.includes("Downloading training prices")) {
    setRunProgressStage("data", 0.08, "Downloading adjusted prices from Yahoo Finance");
  } else if (line.includes("Clean training universe")) {
    setRunProgressStage("data", 0.92, line.trim());
  } else if (line.includes("Applying AI-assisted Black-Litterman")) {
    setRunProgressStage("research", 0.02, "Preparing Black-Litterman research inputs");
  } else if ((match = line.match(/Generating (\d+) missing AI views/i))) {
    setRunProgressStage("research", 0.04, `Generating ${match[1]} uncached AI views`);
  } else if (line.includes("Fetching fundamentals and news")) {
    setRunProgressStage("research", 0.08, "Fetching fundamentals and five headlines per security");
  } else if ((match = line.match(/Sending .* request for tickers (\d+)-(\d+) of (\d+)/i))) {
    const completedBeforeBatch = Math.max(0, Number(match[1]) - 1);
    const total = Math.max(1, Number(match[3]));
    setRunProgressStage(
      "research",
      0.30 + 0.62 * (completedBeforeBatch / total),
      `AI research batch ${match[1]}-${match[2]} of ${match[3]}`
    );
  } else if ((match = line.match(/batch completed.*tickers|batch completed/i))) {
    setRunProgressStage("research", Math.min(0.96, runProgressState.observedFraction + 0.03), "Validating structured AI research output");
  } else if (line.includes("Loading cached Black-Litterman views")) {
    setRunProgressStage("research", 0.72, "Validating cached AI research views");
  } else if (line.includes("Black-Litterman analysis saved")) {
    setRunProgressStage("research", 0.99, "Black-Litterman research complete");
  } else if ((match = line.match(/Running global AI view audit.*across (\d+) securities/i))) {
    setRunProgressStage("audit", 0.03, `Auditing ${match[1]} views for consistency and bias`);
  } else if (line.includes("Global AI audit complete")) {
    setRunProgressStage("audit", 0.99, line.trim());
  } else if (line.includes("Running SLSQP optimisation engines")) {
    setRunProgressStage("optimization", 0.18, "Solving maximum-Sharpe and minimum-volatility portfolios");
  } else if (line.includes("IN-SAMPLE ASSET ALLOCATIONS")) {
    setRunProgressStage("optimization", 0.88, "Portfolio weights solved");
  } else if (line.includes("OUT-OF-SAMPLE TESTING") || line.includes("Fetching OOS portfolio prices")) {
    setRunProgressStage("oos", 0.08, "Downloading and aligning out-of-sample prices");
  } else if (line.includes("STATISTICAL SIGNIFICANCE")) {
    setRunProgressStage("oos", 0.68, "Running performance and significance analysis");
  } else if (line.includes("Generating equity curve chart")) {
    setRunProgressStage("oos", 0.84, "Rendering out-of-sample performance chart");
  } else if (line.includes("Chart saved") || line.includes("[CHART SKIPPED]") || line.includes("[OOS DISABLED]")) {
    if (runProgressState.plan.stages.some((stage) => stage.id === "oos")) {
      setRunProgressStage("oos", 0.99, "Out-of-sample stage complete");
    }
  } else if (line.includes("Generating portfolio allocation memorandum PDF") || line.includes("Generating portfolio summary PDF")) {
    setRunProgressStage("report", 0.12, "Building portfolio allocation memorandum");
  } else if (line.includes("Portfolio memorandum saved") || line.includes("Portfolio summary saved")) {
    setRunProgressStage("report", 0.94, "Portfolio memorandum saved");
  } else if (line.includes("Live dashboard results saved")) {
    setRunProgressStage("results", 0.96, "Publishing results to the dashboard");
  }
}

function finishRunProgress(status) {
  if (!runProgressState) return;
  clearInterval(runProgressTimer);
  runProgressTimer = null;
  if (status === "completed") {
    runProgressState.displayed = 100;
    runProgressElement.classList.add("completed");
    runProgressElement.classList.remove("failed");
    runProgressStage.textContent = "Run completed";
    runProgressDetail.textContent = "Results and report artifacts are ready.";
    runProgressFill.style.width = "100%";
    runProgressTrack.setAttribute("aria-valuenow", "100");
    runProgressPercent.textContent = "100%";
  } else {
    runProgressElement.classList.add("failed");
    runProgressElement.classList.remove("completed");
    runProgressStage.textContent = status === "stopped" ? "Run stopped" : "Run failed";
    runProgressDetail.textContent = "Progress stopped at the last confirmed terminal milestone.";
  }
}

function appendTerminal(text, kind = "") {
  if (!text) return;
  if (terminalLines === 0) terminalOutput.textContent = "";
  const line = document.createElement("span");
  if (kind) line.className = `terminal-${kind}`;
  line.textContent = `${text}\n`;
  terminalOutput.appendChild(line);
  terminalLines += 1;
  terminalLineCount.textContent = `${terminalLines} ${terminalLines === 1 ? "line" : "lines"}`;
  if (document.getElementById("terminal-autoscroll").checked) {
    terminalOutput.scrollTop = terminalOutput.scrollHeight;
  }
}

async function loadCompletedResults(status) {
  if (Number(status.api_version || 1) < 2) {
    if (!legacyRunnerNoticeShown) {
      appendTerminal("[relay] Runner update required. Restart server.py, then run the analysis again.", "error");
      legacyRunnerNoticeShown = true;
    }
    loadedResultRunId = status.run_id;
    return false;
  }
  try {
    const results = await runnerRequest("/api/results");
    applyLiveResults(results);
    loadedResultRunId = status.run_id || `persisted:${results.generatedAt || "latest"}`;
    appendTerminal(
      results.dataMode === "example"
        ? "[relay] Loaded bundled example portfolio and AI research"
        : "[relay] Dashboard updated with completed run results",
      "system"
    );
    await refreshReportArtifacts();
    if (runnerCapabilities.run_history) await loadHistoryCatalog();
    return true;
  } catch (error) {
    if (error.status === 404) {
      appendTerminal("[relay] Run completed, but no live result file exists. Run it once more after restarting the service.", "error");
      loadedResultRunId = status.run_id;
      return false;
    }
    throw error;
  }
}

async function fetchArtifact(path) {
  let response;
  try {
    response = await fetchWithTimeout(runnerEndpoint(path), { headers: runnerHeaders(false) });
  } catch (networkError) {
    const error = new Error(
      networkError?.name === "AbortError"
        ? "Artifact request timed out"
        : "Network error — unable to reach the runner service"
    );
    error.cause = networkError;
    throw error;
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const error = new Error(payload.error || `Artifact returned HTTP ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return response.blob();
}

function historyDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value || "Unknown date") : date.toLocaleString();
}

function historySettingLabel(key) {
  return String(key)
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/^./, (character) => character.toUpperCase());
}

function renderHistoryList() {
  const list = document.getElementById("history-list");
  document.getElementById("history-count").textContent = `${historyRuns.length} ${historyRuns.length === 1 ? "run" : "runs"}`;
  if (!historyRuns.length) {
    list.innerHTML = '<div class="empty-state">No completed runs have been archived yet.</div>';
    return;
  }
  list.innerHTML = historyRuns.map((run) => `
    <button class="history-run${selectedHistoryRun?.id === run.id ? " active" : ""}" type="button" data-history-run="${escapeHtml(run.id)}">
      <strong>${escapeHtml(historyDate(run.generatedAt))}</strong>
      <span>${escapeHtml(run.universe || "universe")} · ${escapeHtml(run.researchModel || "No AI views")}</span>
      <small>${Number(run.tickerCount || 0)} tickers · ${Number(run.opinionCount || 0)} AI opinions${run.auditEnabled ? " · audited" : ""}</small>
    </button>
  `).join("");
}

function historyPortfolioRows(results) {
  const rows = new Map();
  ["max", "min"].forEach((portfolioKey) => {
    (results.portfolios?.[portfolioKey]?.holdings || []).forEach((holding) => {
      const row = rows.get(holding.ticker) || {
        ticker: holding.ticker,
        sector: holding.sector || "Unclassified",
        max: 0,
        min: 0
      };
      row[portfolioKey] = Number(holding.weight || 0);
      rows.set(holding.ticker, row);
    });
  });
  return [...rows.values()].sort((left, right) =>
    Math.max(Math.abs(right.max), Math.abs(right.min)) - Math.max(Math.abs(left.max), Math.abs(left.min))
  );
}

function renderHistoryDetail(results, manifest) {
  const detail = document.getElementById("history-detail");
  const config = results.config || {};
  const portfolioRows = historyPortfolioRows(results);
  const opinions = (results.research || []).filter((item) => item.view);
  const configItems = Object.entries(config).map(([key, value]) => `
    <div class="history-config-item">
      <span>${escapeHtml(historySettingLabel(key))}</span>
      <strong>${escapeHtml(typeof value === "boolean" ? (value ? "Enabled" : "Disabled") : String(value === "" ? "Not supplied" : value))}</strong>
    </div>
  `).join("");
  const portfolioTable = portfolioRows.map((row) => `
    <tr>
      <td>${escapeHtml(row.ticker)}</td>
      <td>${escapeHtml(row.sector)}</td>
      <td class="${financeClass(row.max)}">${(row.max * 100).toFixed(3)}%</td>
      <td class="${financeClass(row.min)}">${(row.min * 100).toFixed(3)}%</td>
    </tr>
  `).join("");
  const opinionTable = opinions.map((item) => `
    <tr>
      <td>${escapeHtml(item.ticker)}</td>
      <td class="${financeClass(Number(item.posteriorReturn))}">${formatPercent(item.posteriorReturn)}</td>
      <td>${Math.round(Number(item.confidence || 0) * 100)}%</td>
      <td class="history-thesis">${escapeHtml(item.view)}</td>
    </tr>
  `).join("");
  detail.innerHTML = `
    <div class="history-detail-header">
      <div>
        <p class="eyebrow">Archived snapshot</p>
        <h3>${escapeHtml(historyDate(results.generatedAt))}</h3>
        <p>${escapeHtml(manifest.id)} · Data through ${escapeHtml(results.dataThrough || "unknown")}</p>
      </div>
      <div class="history-actions">
        <button class="button button-primary" type="button" data-history-action="dashboard">Load dashboard</button>
        <button class="button button-secondary" type="button" data-history-action="report"${manifest.artifacts?.pdf ? "" : " disabled"}>View report</button>
        <button class="button button-secondary" type="button" data-history-artifact="all-tickers">Ticker CSV</button>
        <button class="button button-secondary" type="button" data-history-artifact="ai-opinions">AI CSV</button>
        <button class="button button-secondary" type="button" data-history-artifact="config">Config CSV</button>
      </div>
    </div>
    <div class="history-stat-grid">
      <div class="history-stat"><span>Max Sharpe return</span><strong class="${financeClass(results.metrics.max.return)}">${formatPercent(results.metrics.max.return)}</strong></div>
      <div class="history-stat"><span>Max Sharpe risk</span><strong>${formatPercent(results.metrics.max.risk)}</strong></div>
      <div class="history-stat"><span>Min Vol return</span><strong class="${financeClass(results.metrics.min.return)}">${formatPercent(results.metrics.min.return)}</strong></div>
      <div class="history-stat"><span>Min Vol risk</span><strong>${formatPercent(results.metrics.min.risk)}</strong></div>
    </div>
    <h4 class="history-section-title">Run configuration</h4>
    <div class="history-config-grid">${configItems}</div>
    <h4 class="history-section-title">All portfolio holdings</h4>
    <div class="history-table-shell">
      <table class="history-table">
        <thead><tr><th>Ticker</th><th>Sector</th><th>Max Sharpe</th><th>Min Volatility</th></tr></thead>
        <tbody>${portfolioTable || '<tr><td colspan="4">No holdings stored.</td></tr>'}</tbody>
      </table>
    </div>
    <h4 class="history-section-title">AI opinions (${opinions.length})</h4>
    <div class="history-table-shell">
      <table class="history-table">
        <thead><tr><th>Ticker</th><th>View</th><th>Confidence</th><th>Rationale</th></tr></thead>
        <tbody>${opinionTable || '<tr><td colspan="4">AI views were disabled for this run.</td></tr>'}</tbody>
      </table>
    </div>
  `;
}

async function selectHistoryRun(historyId) {
  const manifest = historyRuns.find((run) => run.id === historyId);
  if (!manifest) return;
  selectedHistoryRun = manifest;
  renderHistoryList();
  document.getElementById("history-detail").innerHTML = '<div class="history-empty"><strong>Loading archived run</strong><span>Reading local results and configuration.</span></div>';
  try {
    const results = await runnerRequest(`/api/results?run=${encodeURIComponent(historyId)}`);
    selectedHistoryResults = results;
    renderHistoryDetail(results, manifest);
  } catch (error) {
    selectedHistoryResults = null;
    document.getElementById("history-detail").innerHTML = `<div class="history-empty"><strong>Could not load run</strong><span>${escapeHtml(error.message)}</span></div>`;
  }
}

async function loadHistoryCatalog() {
  if (!runnerConnected || !runnerCapabilities.run_history) {
    if (runnerConnected) {
      document.getElementById("history-list").innerHTML = '<div class="empty-state">Restart the dashboard service to enable run history.</div>';
    }
    return;
  }
  try {
    const payload = await runnerRequest("/api/history");
    historyRuns = Array.isArray(payload.runs) ? payload.runs : [];
    document.getElementById("history-folder").textContent = payload.folder || "Local run-history folder";
    if (selectedHistoryRun && !historyRuns.some((run) => run.id === selectedHistoryRun.id)) {
      selectedHistoryRun = null;
      selectedHistoryResults = null;
    }
    renderHistoryList();
    if (!selectedHistoryRun && historyRuns.length) await selectHistoryRun(historyRuns[0].id);
  } catch (error) {
    document.getElementById("history-list").innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
  }
}

async function downloadHistoryArtifact(kind) {
  if (!selectedHistoryRun) return;
  const blob = await fetchArtifact(`/api/history/artifact?run=${encodeURIComponent(selectedHistoryRun.id)}&kind=${encodeURIComponent(kind)}`);
  const names = { "all-tickers": "all-tickers.csv", "ai-opinions": "ai-opinions.csv", config: "run-config.csv" };
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${selectedHistoryRun.id.replace("/", "_")}_${names[kind] || "artifact"}`;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

document.getElementById("refresh-history").addEventListener("click", loadHistoryCatalog);
document.getElementById("history-list").addEventListener("click", (event) => {
  const button = event.target.closest("[data-history-run]");
  if (button) selectHistoryRun(button.dataset.historyRun);
});
document.getElementById("history-detail").addEventListener("click", async (event) => {
  const action = event.target.closest("[data-history-action]")?.dataset.historyAction;
  const artifact = event.target.closest("[data-history-artifact]")?.dataset.historyArtifact;
  try {
    if (artifact) await downloadHistoryArtifact(artifact);
    if (!action || !selectedHistoryResults || !selectedHistoryRun) return;
    applyLiveResults(selectedHistoryResults);
    if (action === "report") {
      showView("reference");
      await refreshReportArtifacts(selectedHistoryRun.id);
    } else {
      showView("overview");
    }
  } catch (error) {
    appendTerminal(`[relay] History: ${error.message}`, "error");
  }
});

function setReportState(status, label) {
  const element = document.getElementById("report-state");
  element.className = `runner-state ${status}`;
  element.querySelector("strong").textContent = label;
}

async function refreshReportArtifacts(historyId = currentHistoryRunId) {
  if (!runnerConnected) {
    setReportState("disconnected", "Runner disconnected");
    return;
  }
  if (!runnerCapabilities.artifacts) {
    setReportState("failed", "Runner restart required");
    document.getElementById("pdf-status").textContent = "Runner update required";
    document.getElementById("chart-status").textContent = "Runner update required";
    if (!artifactCompatibilityNoticeShown) {
      appendTerminal("[relay] Report viewer requires the updated runner. Stop server.py, restart it, then refresh this page.", "error");
      artifactCompatibilityNoticeShown = true;
    }
    return;
  }
  setReportState("running", "Loading artifacts");
  const historyQuery = historyId ? `?run=${encodeURIComponent(historyId)}` : "";

  try {
    const pdfBlob = await fetchArtifact(`/api/artifacts/pdf${historyQuery}`);
    if (pdfBlobUrl) URL.revokeObjectURL(pdfBlobUrl);
    pdfBlobUrl = URL.createObjectURL(pdfBlob);
    const viewer = document.getElementById("pdf-viewer");
    viewer.src = pdfBlobUrl;
    viewer.style.display = "block";
    document.getElementById("pdf-placeholder").style.display = "none";
    document.getElementById("pdf-status").textContent = `${(pdfBlob.size / 1024).toFixed(0)} KB`;
    document.getElementById("download-report").disabled = false;
  } catch (error) {
    if (pdfBlobUrl) {
      URL.revokeObjectURL(pdfBlobUrl);
      pdfBlobUrl = null;
    }
    const viewer = document.getElementById("pdf-viewer");
    viewer.removeAttribute("src");
    viewer.style.display = "none";
    document.getElementById("pdf-status").textContent = "Unavailable";
    document.getElementById("pdf-placeholder").style.display = "grid";
    document.getElementById("download-report").disabled = true;
    appendTerminal(`[relay] PDF: ${error.message}`, "error");
  }

  try {
    const chartBlob = await fetchArtifact(`/api/artifacts/chart${historyQuery}`);
    if (chartBlobUrl) URL.revokeObjectURL(chartBlobUrl);
    chartBlobUrl = URL.createObjectURL(chartBlob);
    const image = document.getElementById("report-chart");
    image.src = chartBlobUrl;
    image.style.display = "block";
    document.getElementById("chart-placeholder").style.display = "none";
    document.getElementById("chart-status").textContent = `${(chartBlob.size / 1024).toFixed(0)} KB`;
  } catch (error) {
    if (chartBlobUrl) {
      URL.revokeObjectURL(chartBlobUrl);
      chartBlobUrl = null;
    }
    const image = document.getElementById("report-chart");
    image.removeAttribute("src");
    image.style.display = "none";
    document.getElementById("chart-status").textContent = error.status === 404 ? "OOS disabled" : "Unavailable";
    document.getElementById("chart-placeholder").style.display = "grid";
    if (error.status !== 404) appendTerminal(`[relay] Chart: ${error.message}`, "error");
  }
  const readyLabel = currentResultMode === "example"
    ? "Example report ready"
    : currentResultMode === "history" ? "Archived report ready" : "Report ready";
  setReportState(pdfBlobUrl ? "connected" : "failed", pdfBlobUrl ? readyLabel : "Report unavailable");
}

async function pollRunner() {
  if (!runnerConnected) return;
  try {
    const [status, logs] = await Promise.all([
      runnerRequest("/api/status"),
      runnerRequest(`/api/logs?after=${runnerOffset}`)
    ]);
    if (
      (status.status === "running" || status.status === "stopping")
      && (!runProgressState || runProgressState.runId !== status.run_id)
    ) {
      beginRunProgress(status.config || {}, Number(status.started_at || 0) * 1000 || Date.now());
      runProgressState.runId = status.run_id;
    }
    if (
      status.status === "completed"
      && (!runProgressState || runProgressState.runId !== status.run_id)
    ) {
      beginRunProgress(status.config || {}, Number(status.started_at || 0) * 1000 || Date.now());
      runProgressState.runId = status.run_id;
    }
    logs.lines.forEach((entry) => {
      appendTerminal(entry.text, entry.stream === "system" ? "system" : entry.stream === "stderr" ? "error" : "");
      processRunProgressLine(entry.text);
      runnerOffset = Math.max(runnerOffset, entry.id);
    });
    terminalRunId.textContent = status.run_id ? `Run ${status.run_id}` : "No active run";
    runnerCapabilities = status.capabilities || {};
    activateProjectLogo(status.api_version);
    renderProviderKeyStatus(status.provider_keys, status.api_version);
    analysisEnvironmentReady = Boolean(status.analysis_environment?.ready);
    applyRunConfig(status.config);
    if (status.status === "running" || status.status === "stopping") {
      setRunnerState("running", status.status === "stopping" ? "Stopping" : "Running");
    } else if (status.status === "failed") {
      setRunnerState("failed", "Run failed");
      finishRunProgress("failed");
    } else {
      setRunnerState("connected", status.status === "completed" ? "Completed" : status.status === "stopped" ? "Stopped" : "Connected");
      if (status.status === "completed") {
        finishRunProgress("completed");
        triggerLogoAnimation("logo-pulse");
      }
      if (status.status === "stopped") finishRunProgress("stopped");
      if (status.status === "completed" && status.run_id !== loadedResultRunId) {
        await loadCompletedResults(status);
      }
    }
  } catch (error) {
    runnerConnected = false;
    setRunnerState("disconnected", "Disconnected");
    renderProviderKeyStatus();
    appendTerminal(`[relay] ${error.message}`, "error");
    triggerLogoAnimation("logo-shake");
    clearInterval(runnerPollTimer);
    runnerPollTimer = null;
  }
}

async function connectRunner() {
  localStorage.setItem("allolabs-runner-url", runnerUrl.value.trim());
  setRunnerState("disconnected", "Connecting");
  try {
    const status = await runnerRequest("/api/status");
    if (status.config && !pendingUniverseConfig) pendingUniverseConfig = status.config;
    await loadUniverseCatalog();
    runnerConnected = true;
    runnerCapabilities = status.capabilities || {};
    activateProjectLogo(status.api_version);
    renderProviderKeyStatus(status.provider_keys, status.api_version);
    analysisEnvironmentReady = Boolean(status.analysis_environment?.ready);
    runnerOffset = 0;
    appendTerminal(`[relay] Connected to ${runnerUrl.value.trim()}`, "system");
    if (analysisEnvironmentReady) {
      appendTerminal(
        `[relay] Analysis Python ${status.analysis_environment.version}: ${status.analysis_environment.python}`,
        "system"
      );
    } else {
      appendTerminal(
        `[relay] Analysis environment unavailable: ${status.analysis_environment?.error || "server update required"}`,
        "error"
      );
    }
    setRunnerState(status.status === "running" ? "running" : "connected", status.status === "running" ? "Running" : "Connected");
    clearInterval(runnerPollTimer);
    runnerPollTimer = setInterval(pollRunner, 900);
    await pollRunner();
    if (status.results_available && !loadedResultRunId) await loadCompletedResults(status);
  } catch (error) {
    runnerConnected = false;
    setRunnerState("failed", "Connection failed");
    renderProviderKeyStatus();
    appendTerminal(`[relay] ${error.message}`, "error");
  }
}

document.getElementById("runner-connect").addEventListener("click", connectRunner);
document.getElementById("refresh-report").addEventListener("click", () => refreshReportArtifacts());
document.getElementById("download-report").addEventListener("click", () => {
  if (pdfBlobUrl) window.open(pdfBlobUrl, "_blank", "noopener");
});

runnerStart.addEventListener("click", async () => {
  const config = {
    trainingYears: Number(document.getElementById("remote-training").value),
    oosMonths: Number(document.getElementById("remote-oos").value),
    maxPositionPercent: Number(document.getElementById("remote-position").value),
    longOnly: longOnlyToggle.checked,
    maxSectorPercent: Number(sectorCapInput.value),
    regularization: regularizationSelect.value,
    regularizationStrength: Number(regularizationStrength.value),
    universe: matchingUniversePreset()?.id || "custom",
    selectedTickers: orderedUniverseSelection(),
    gptViews: remoteGptToggle.checked,
    researchProvider: remoteResearchProvider.value,
    researchModel: remoteGptModel.value,
    auditViews: remoteAuditToggle.checked,
    auditProvider: remoteAuditProvider.value,
    auditModel: remoteAuditModel.value,
    refreshCache: document.getElementById("remote-refresh").checked,
    maxNewsArticles: Math.max(1, Math.min(20, parseInt(document.getElementById("remote-max-news").value) || 5)),
    researchBatchSize: Math.max(1, Math.min(30, parseInt(document.getElementById("remote-batch-size").value) || 12)),
    analystSeedPrompt: document.getElementById("remote-analyst-seed").value.trim(),
    auditorSeedPrompt: document.getElementById("remote-auditor-seed").value.trim()
  };
  try {
    if (config.trainingYears < 0.25 || config.trainingYears > 10) throw new Error("Training lookback must be between 0.25 and 10 years.");
    if (config.oosMonths < 0 || config.oosMonths > 60) throw new Error("OOS window must be between 0 and 60 months.");
    if (config.maxPositionPercent < 1 || config.maxPositionPercent > 100) throw new Error("Maximum position must be between 1% and 100%.");
    if (config.maxSectorPercent < 5 || config.maxSectorPercent > 100) throw new Error("Maximum sector weight must be between 5% and 100%.");
    if (config.regularizationStrength < 0 || config.regularizationStrength > 10) throw new Error("Regularization strength must be between 0 and 10.");
    if (config.selectedTickers.length < 2) throw new Error("Select at least two securities in the Universe tab before running AlloLabs.");
    if (config.auditViews && !config.gptViews) throw new Error("Global AI audit requires AI-assisted views.");
    if (config.analystSeedPrompt.length > 12000) throw new Error("Analyst seed prompt must be 12,000 characters or fewer.");
    if (config.auditorSeedPrompt.length > 12000) throw new Error("Auditor seed prompt must be 12,000 characters or fewer.");
    const result = await runnerRequest("/api/run", { method: "POST", body: JSON.stringify(config) });
    beginRunProgress(config);
    runProgressState.runId = result.run_id;
    applyRunConfig(config);
    runnerOffset = 0;
    terminalOutput.textContent = "";
    terminalLines = 0;
    terminalLineCount.textContent = "0 lines";
    terminalRunId.textContent = `Run ${result.run_id}`;
    appendTerminal(`[relay] Run ${result.run_id} accepted`, "system");
    setRunnerState("running", "Running");
    await pollRunner();
  } catch (error) {
    appendTerminal(`[relay] ${error.message}`, "error");
  }
});

runnerStop.addEventListener("click", async () => {
  try {
    await runnerRequest("/api/stop", { method: "POST" });
    setRunnerState("running", "Stopping");
    appendTerminal("[relay] Stop requested", "system");
  } catch (error) {
    appendTerminal(`[relay] ${error.message}`, "error");
  }
});

document.getElementById("terminal-clear").addEventListener("click", () => {
  terminalOutput.textContent = "";
  terminalLines = 0;
  terminalLineCount.textContent = "0 lines";
});

document.getElementById("terminal-copy").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(terminalOutput.innerText);
    appendTerminal("[relay] Output copied to clipboard", "system");
  } catch {
    appendTerminal("[relay] Clipboard access was unavailable", "error");
  }
});

/* === Interactive chart tooltip ================================= */
(function initChartTooltip() {
  const overlay = document.getElementById("chart-overlay");
  const tooltip = document.getElementById("chart-tooltip");
  const crosshair = document.getElementById("chart-crosshair");
  const dotMax = document.getElementById("chart-dot-max");
  const dotMin = document.getElementById("chart-dot-min");
  const dotBench = document.getElementById("chart-dot-bench");
  if (!overlay) return;

  const LEFT = 48, RIGHT = 730, TOP = 35, BOTTOM = 235;

  function yPos(val, min, max) {
    const span = max - min || 1;
    return BOTTOM - ((Number(val) - min) / span) * (BOTTOM - TOP);
  }

  overlay.addEventListener("mousemove", (event) => {
    if (!performanceCache?.dates?.length) return;
    const svg = overlay.closest("svg");
    const pt = svg.createSVGPoint();
    pt.x = event.clientX;
    pt.y = event.clientY;
    const svgPt = pt.matrixTransform(svg.getScreenCTM().inverse());

    const dataLen = performanceCache.dates.length;
    const index = Math.round(((svgPt.x - LEFT) / (RIGHT - LEFT)) * (dataLen - 1));
    const i = Math.max(0, Math.min(dataLen - 1, index));

    const maxSeries = performanceCache.series.Max_Sharpe || [];
    const minSeries = performanceCache.series.Min_Vol || [];
    const benchName = benchmarkSeriesName(performanceCache.series);
    const benchSeries = benchName ? performanceCache.series[benchName] : [];
    const allVals = [...maxSeries, ...minSeries, ...benchSeries].map(Number).filter(Number.isFinite);
    if (!allVals.length) return;
    const min = Math.min(...allVals);
    const max = Math.max(...allVals);

    const x = LEFT + (i / Math.max(dataLen - 1, 1)) * (RIGHT - LEFT);

    crosshair.setAttribute("x1", x);
    crosshair.setAttribute("x2", x);
    crosshair.setAttribute("visibility", "visible");

    if (maxSeries[i] != null) {
      dotMax.setAttribute("cx", x);
      dotMax.setAttribute("cy", yPos(maxSeries[i], min, max));
      dotMax.setAttribute("visibility", "visible");
    }
    if (minSeries[i] != null) {
      dotMin.setAttribute("cx", x);
      dotMin.setAttribute("cy", yPos(minSeries[i], min, max));
      dotMin.setAttribute("visibility", "visible");
    }
    if (benchSeries[i] != null) {
      dotBench.setAttribute("cx", x);
      dotBench.setAttribute("cy", yPos(benchSeries[i], min, max));
      dotBench.setAttribute("visibility", "visible");
    }

    const date = new Date(performanceCache.dates[i]);
    document.getElementById("chart-tooltip-date").textContent =
      date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
    document.getElementById("chart-tooltip-max").textContent =
      maxSeries[i] != null ? Number(maxSeries[i]).toFixed(4) : "--";
    document.getElementById("chart-tooltip-min").textContent =
      minSeries[i] != null ? Number(minSeries[i]).toFixed(4) : "--";
    document.getElementById("chart-tooltip-bench").textContent =
      benchSeries[i] != null ? Number(benchSeries[i]).toFixed(4) : "--";

    const chartWrap = svg.closest(".chart-wrap");
    const wrapRect = chartWrap.getBoundingClientRect();
    const svgRect = svg.getBoundingClientRect();
    const scale = svgRect.width / 760;
    let tooltipX = (x * scale) + (svgRect.left - wrapRect.left);
    const tooltipWidth = tooltip.offsetWidth || 180;
    if (tooltipX + tooltipWidth / 2 > wrapRect.width) tooltipX = wrapRect.width - tooltipWidth / 2 - 4;
    if (tooltipX - tooltipWidth / 2 < 0) tooltipX = tooltipWidth / 2 + 4;
    tooltip.style.left = `${tooltipX}px`;
    tooltip.style.top = "4px";
    tooltip.style.transform = "translateX(-50%)";
    tooltip.classList.add("visible");
  });

  overlay.addEventListener("mouseleave", () => {
    crosshair.setAttribute("visibility", "hidden");
    dotMax.setAttribute("visibility", "hidden");
    dotMin.setAttribute("visibility", "hidden");
    dotBench.setAttribute("visibility", "hidden");
    tooltip.classList.remove("visible");
  });
})();

/* === Interactive donut tooltip ================================= */
function initDonutInteraction(donutId, tooltipId, labelId, valueId) {
  const donut = document.getElementById(donutId);
  const tooltip = document.getElementById(tooltipId);
  if (!donut || !tooltip) return;

  donut.addEventListener("mousemove", (event) => {
    const segments = donutSegments[donutId] || [];
    const rect = donut.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const dx = event.clientX - cx;
    const dy = event.clientY - cy;
    const distance = Math.sqrt(dx * dx + dy * dy);
    const outerR = rect.width / 2;
    const innerR = outerR * 0.65;

    if (distance < innerR || distance > outerR) {
      tooltip.classList.remove("visible");
      return;
    }

    let angle = Math.atan2(dx, -dy) * (180 / Math.PI);
    if (angle < 0) angle += 360;

    let cumulative = 0;
    let found = null;
    for (const [label, value, color] of segments) {
      const segAngle = (value / 100) * 360;
      if (angle >= cumulative && angle < cumulative + segAngle) {
        found = { label, value, color };
        break;
      }
      cumulative += segAngle;
    }

    if (!found) { tooltip.classList.remove("visible"); return; }

    document.getElementById(labelId).textContent = found.label;
    document.getElementById(labelId).style.color = found.color;
    document.getElementById(valueId).textContent = `${found.value.toFixed(1)}%`;

    const layout = donut.closest(".donut-layout");
    const layoutRect = layout.getBoundingClientRect();
    tooltip.style.left = `${event.clientX - layoutRect.left + 14}px`;
    tooltip.style.top = `${event.clientY - layoutRect.top - 10}px`;
    tooltip.classList.add("visible");
  });

  donut.addEventListener("mouseleave", () => tooltip.classList.remove("visible"));
}

initDonutInteraction("sector-donut",   "donut-tooltip",          "donut-tooltip-sector",          "donut-tooltip-value");
initDonutInteraction("market-donut",   "market-donut-tooltip",   "market-donut-tooltip-label",    "market-donut-tooltip-value");
initDonutInteraction("currency-donut", "currency-donut-tooltip", "currency-donut-tooltip-label",  "currency-donut-tooltip-value");

/* === Splash screen with preloading ============================= */
(function initSplash() {
  const splash = document.getElementById("splash");
  const statusEl = document.getElementById("splash-status");
  if (!splash) return;
  if (sessionStorage.getItem("allolabs-splash-seen")) {
    splash.hidden = true;
    return;
  }

  let preloadDone = false;
  let animationDone = false;

  function updateStatus(text, ready) {
    if (!statusEl) return;
    statusEl.textContent = text;
    if (ready) statusEl.classList.add("ready");
  }

  function tryDismiss() {
    if (!preloadDone || !animationDone) return;
    updateStatus("Ready", true);
    setTimeout(() => {
      splash.classList.add("out");
      setTimeout(() => {
        splash.hidden = true;
        sessionStorage.setItem("allolabs-splash-seen", "1");
      }, 600);
    }, 400);
  }

  setTimeout(() => {
    animationDone = true;
    tryDismiss();
  }, 3800);

  (async function preload() {
    try {
      updateStatus("Connecting to runner...");
      const base = (location.protocol === "http:" || location.protocol === "https:")
        ? location.origin : "http://127.0.0.1:8765";
      const token = new URLSearchParams(location.search).get("desktopToken") || "";
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      // Short timeout: the splash overlay covers the whole UI, so a hung
      // request must never block dismissal.
      const response = await fetchWithTimeout(`${base}/api/status`, { headers }, 6000);
      const status = response.ok ? await response.json().catch(() => ({})) : {};

      if (status.provider_keys) {
        const providers = Object.values(status.provider_keys);
        const active = providers.filter((p) => p.active).length;
        updateStatus(`${active}/${providers.length} API keys detected`);
      } else {
        updateStatus("Runner connected");
      }

      if (status.results_available) {
        updateStatus("Loading portfolio data...");
        await fetchWithTimeout(`${base}/api/results`, { headers }, 6000);
        updateStatus("Portfolio data loaded");
      }
    } catch {
      updateStatus("Offline mode");
    }
    preloadDone = true;
    tryDismiss();
  })();
})();

/* === Living logo =============================================== */
const brandLogo = document.getElementById("brand-logo");

function triggerLogoAnimation(className) {
  if (!brandLogo) return;
  brandLogo.classList.remove("logo-breathe", "logo-bounce", "logo-pulse", "logo-shake");
  void brandLogo.offsetWidth;
  brandLogo.classList.add(className);
  brandLogo.addEventListener("animationend", () => {
    brandLogo.classList.remove(className);
  }, { once: true });
}

document.querySelectorAll(".nav-item").forEach((item) => {
  item.addEventListener("click", () => triggerLogoAnimation("logo-bounce"));
});
document.querySelectorAll("[data-shortcut-view]").forEach((item) => {
  item.addEventListener("click", () => triggerLogoAnimation("logo-bounce"));
});
document.querySelectorAll("[data-portfolio]").forEach((button) => {
  button.addEventListener("click", () => triggerLogoAnimation("logo-bounce"));
});

/* === Guide Mode — Allo AI assistant ============================== */

let guideHistory = [];
let guidePendingConfig = null;
let guideLoading = false;
let guideMemoryLoaded = false;
const GUIDE_COMPACT_THRESHOLD = 20;
const GUIDE_MEMORY_KEY = "allolabs_guide_memory";
const GUIDE_MEMORY_MAX = 4; // how many past session summaries to retain

/* SVG icon markup injected into each chat bubble */
const ALLO_ICON_SVG = `<svg class="guide-msg-icon" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <path fill="none" stroke="currentColor" stroke-width="24" stroke-linecap="butt" d="M17,52 A33,33 0 0,1 83,52"/>
  <rect fill="currentColor" x="5"  y="62" width="24" height="30"/>
  <rect fill="currentColor" x="71" y="62" width="24" height="30"/>
  <rect fill="currentColor" x="5"  y="84" width="90" height="8"/>
</svg>`;

const USER_ICON_SVG = `<svg class="guide-msg-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <circle cx="12" cy="7.5" r="4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
  <path d="M4.5 21c0-4.142 3.358-7.5 7.5-7.5s7.5 3.358 7.5 7.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
</svg>`;

const GUIDE_QUICK_ACTIONS = {
  explain_bl:
    "What is Black-Litterman and how does AlloLabs use it?",
  draft_thesis:
    "Help me draft an investment mandate for my AlloLabs run. Ask me what you need in one message, " +
    "then produce a compact mandate text I can paste into the analyst seed prompt field.",
  debug_alignment:
    "Help me debug thesis alignment. What do you need from me? " +
    "(My current mandate, what results look wrong, which tickers are misbehaving.)",
  design_universe:
    "Help me design a ticker universe. Ask me what you need in one message, " +
    "then suggest 15–25 tickers with a brief rationale.",
  explain_portfolio:
    "Explain the current portfolio: what the allocation implies, key exposures, " +
    "concentration risks, and how Max Sharpe and Min Vol differ.",
  auto_configure:
    "Configure an AlloLabs run for me. Ask me what you need in a single message, " +
    "use safe defaults for the rest, then show me the complete config and ask once if I'm ready to load it.",
  checklist:
    "Give me a concise run-readiness checklist for my next AlloLabs optimization."
};

function guideFormatText(text) {
  let html = escapeHtml(text);
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/`([^`\n]+)`/g, "<code>$1</code>");
  // Numbered lists
  html = html.replace(/((?:^|\n)\d+\.\s.+)+/g, (block) => {
    const items = block.trim().split(/\n(?=\d+\.\s)/);
    return "<ol>" + items.map(i => `<li>${i.replace(/^\d+\.\s/, "")}</li>`).join("") + "</ol>";
  });
  // Bullet lists
  html = html.replace(/((?:^|\n)[•\-]\s.+)+/g, (block) => {
    const items = block.trim().split(/\n(?=[•\-]\s)/);
    return "<ul>" + items.map(i => `<li>${i.replace(/^[•\-]\s/, "")}</li>`).join("") + "</ul>";
  });
  // Remaining newlines
  html = html.replace(/\n/g, "<br>");
  return html;
}

function guideAppendMessage(role, content) {
  const chat = document.getElementById("guide-chat");
  if (!chat) return;
  const empty = document.getElementById("guide-empty");
  if (empty) empty.remove();

  const isAllo = role === "allo" || role === "assistant";
  const cssRole = isAllo ? "allo" : "user";

  const wrap = document.createElement("div");
  wrap.className = `guide-message guide-message-${cssRole}`;

  const avatar = document.createElement("div");
  avatar.className = "guide-msg-avatar";
  avatar.innerHTML = isAllo ? ALLO_ICON_SVG : USER_ICON_SVG;

  const inner = document.createElement("div");
  inner.className = "guide-msg-inner";

  const label = document.createElement("span");
  label.className = "guide-message-label";
  label.textContent = isAllo ? "Allo" : "You";

  const body = document.createElement("div");
  body.className = "guide-message-body";
  if (isAllo) {
    body.innerHTML = guideFormatText(content);
  } else {
    body.textContent = content;
  }

  inner.appendChild(label);
  inner.appendChild(body);
  wrap.appendChild(avatar);
  wrap.appendChild(inner);
  chat.appendChild(wrap);
  chat.scrollTop = chat.scrollHeight;
}

function guideAppendCompactBadge(messageCount) {
  const chat = document.getElementById("guide-chat");
  if (!chat) return;
  const badge = document.createElement("div");
  badge.className = "guide-compact-badge";
  badge.textContent = `— ${messageCount} messages summarised —`;
  chat.appendChild(badge);
  chat.scrollTop = chat.scrollHeight;
}

function guideAppendMemoryBadge(count) {
  const chat = document.getElementById("guide-chat");
  if (!chat) return;
  const empty = document.getElementById("guide-empty");
  if (empty) empty.remove();
  const badge = document.createElement("div");
  badge.className = "guide-memory-badge";
  badge.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M12 2a10 10 0 1 0 10 10"/><path d="M12 6v6l4 2"/><path d="M18 2v4h4"/></svg> Memory from ${count} past ${count === 1 ? "session" : "sessions"} recalled`;
  chat.appendChild(badge);
  chat.scrollTop = chat.scrollHeight;
}

function guideAnimateAlloMessage(text) {
  const chat = document.getElementById("guide-chat");
  if (!chat) return Promise.resolve();

  const empty = document.getElementById("guide-empty");
  if (empty) empty.remove();

  const wrap = document.createElement("div");
  wrap.className = "guide-message guide-message-allo";
  wrap.style.animation = "none"; // typing is its own entrance

  const avatar = document.createElement("div");
  avatar.className = "guide-msg-avatar";
  avatar.innerHTML = ALLO_ICON_SVG;

  const inner = document.createElement("div");
  inner.className = "guide-msg-inner";

  const label = document.createElement("span");
  label.className = "guide-message-label";
  label.textContent = "Allo";

  const body = document.createElement("div");
  body.className = "guide-message-body";

  inner.appendChild(label);
  inner.appendChild(body);
  wrap.appendChild(avatar);
  wrap.appendChild(inner);
  chat.appendChild(wrap);
  chat.scrollTop = chat.scrollHeight;

  const formattedHtml = guideFormatText(text);
  const totalChars = text.length;
  // Adaptive speed: 400ms minimum, ~1.5ms per char, 1800ms ceiling
  const duration = Math.min(Math.max(400, totalChars * 1.5), 1800);

  return new Promise((resolve) => {
    const startTime = performance.now();

    function tick(now) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease-out: fast start, gentle deceleration
      const eased = 1 - Math.pow(1 - progress, 1.7);
      const charsToShow = Math.floor(eased * totalChars);

      if (progress < 1) {
        body.textContent = text.slice(0, charsToShow) + "▋";
        // Only scroll if the user is already near the bottom
        if (chat.scrollHeight - chat.scrollTop - chat.clientHeight < 120) {
          chat.scrollTop = chat.scrollHeight;
        }
        requestAnimationFrame(tick);
      } else {
        body.innerHTML = formattedHtml;
        chat.scrollTop = chat.scrollHeight;
        resolve();
      }
    }

    requestAnimationFrame(tick);
  });
}

function guideSaveMemory(summary) {
  if (!summary) return;
  try {
    const stored = JSON.parse(localStorage.getItem(GUIDE_MEMORY_KEY) || "null");
    const memories = Array.isArray(stored) ? stored : [];
    memories.push({ summary, ts: Date.now() });
    while (memories.length > GUIDE_MEMORY_MAX) memories.shift();
    localStorage.setItem(GUIDE_MEMORY_KEY, JSON.stringify(memories));
  } catch {}
}

function guideLoadMemory() {
  if (guideMemoryLoaded) return;
  guideMemoryLoaded = true;
  try {
    const stored = JSON.parse(localStorage.getItem(GUIDE_MEMORY_KEY) || "null");
    if (!stored) return;
    const memories = (Array.isArray(stored) ? stored : []).filter((m) => m?.summary);
    if (memories.length === 0) return;
    const fmt = (ts) => ts ? new Date(ts).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "past session";
    const combined = memories.map((m) => `[${fmt(m.ts)}]\n${m.summary}`).join("\n\n");
    guideHistory.push(
      { role: "user",      content: `RECALLED MEMORY FROM PAST SESSIONS:\n${combined}` },
      { role: "assistant", content: "Past session context loaded — I have context from our previous conversations." },
    );
    guideAppendMemoryBadge(memories.length);
  } catch {}
}

function guideAppendConfigCard(config) {
  const chat = document.getElementById("guide-chat");
  if (!chat) return;

  let gridHtml = '<div class="guide-config-grid">';
  if (config.objective) gridHtml += `<div><span>Objective</span><strong>${config.objective === "max_sharpe" ? "Max Sharpe" : "Min Volatility"}</strong></div>`;
  if (config.tickers?.length) {
    const preview = config.tickers.slice(0, 8).join(", ") + (config.tickers.length > 8 ? `… +${config.tickers.length - 8}` : "");
    gridHtml += `<div><span>Tickers (${config.tickers.length})</span><strong>${escapeHtml(preview)}</strong></div>`;
  }
  if (config.out_of_sample_months != null) gridHtml += `<div><span>OOS window</span><strong>${escapeHtml(config.out_of_sample_months)} mo</strong></div>`;
  if (config.max_position_weight != null) gridHtml += `<div><span>Max position</span><strong>${Math.round(config.max_position_weight * 100)}%</strong></div>`;
  if (config.use_ai_views != null) gridHtml += `<div><span>BL AI views</span><strong>${config.use_ai_views ? "On" : "Off"}</strong></div>`;
  if (config.use_ai_audit != null) gridHtml += `<div><span>AI audit</span><strong>${config.use_ai_audit ? "On" : "Off"}</strong></div>`;
  if (config.regularization && config.regularization !== "none") gridHtml += `<div><span>Regularization</span><strong>${escapeHtml(String(config.regularization).toUpperCase())}</strong></div>`;
  if (config.ai_provider) gridHtml += `<div><span>Provider</span><strong>${escapeHtml(config.ai_provider)}</strong></div>`;
  gridHtml += "</div>";

  if (config.analyst_seed_prompt) {
    gridHtml += `<div class="guide-config-mandate"><p class="eyebrow">Investment mandate</p><p>${escapeHtml(config.analyst_seed_prompt)}</p></div>`;
  }

  const card = document.createElement("div");
  card.className = "guide-config-card";

  const header = document.createElement("div");
  header.className = "guide-config-card-header";
  header.innerHTML = `<p class="eyebrow">Run configuration ready</p><h3>${escapeHtml(config.run_name || "Guided Run")}</h3>`;

  const body = document.createElement("div");
  body.className = "guide-config-card-body";
  body.innerHTML = gridHtml;

  const actions = document.createElement("div");
  actions.className = "guide-config-actions";

  const loadBtn = document.createElement("button");
  loadBtn.className = "button button-primary";
  loadBtn.textContent = "Load into Settings";

  const dismissBtn = document.createElement("button");
  dismissBtn.className = "button button-secondary";
  dismissBtn.textContent = "Dismiss";

  loadBtn.addEventListener("click", () => {
    guideImportConfig(config, loadBtn);
  });
  dismissBtn.addEventListener("click", () => {
    card.style.transition = "opacity 0.18s ease, transform 0.18s ease";
    card.style.opacity = "0";
    card.style.transform = "translateY(-6px)";
    setTimeout(() => card.remove(), 200);
    if (guidePendingConfig === config) guidePendingConfig = null;
  });

  actions.appendChild(loadBtn);
  actions.appendChild(dismissBtn);
  card.appendChild(header);
  card.appendChild(body);
  card.appendChild(actions);
  chat.appendChild(card);
  chat.scrollTop = chat.scrollHeight;
}

// ─── Console & Guide Config Persistence ──────────────────────────────────────

const CONSOLE_CONFIG_STORAGE_KEY = "allolabs_console_cfg";
const GUIDE_CONFIG_STORAGE_KEY   = "allolabs_guide_cfg";

function saveConsoleConfig() {
  try {
    const g = (id) => document.getElementById(id);
    const cfg = {
      training:               g("remote-training")?.value,
      oos:                    g("remote-oos")?.value,
      gpt:                    g("remote-gpt")?.checked,
      researchProvider:       g("remote-research-provider")?.value,
      gptModel:               g("remote-gpt-model")?.value,
      audit:                  g("remote-audit")?.checked,
      auditProvider:          g("remote-audit-provider")?.value,
      auditModel:             g("remote-audit-model")?.value,
      refresh:                g("remote-refresh")?.checked,
      maxNews:                g("remote-max-news")?.value,
      batchSize:              g("remote-batch-size")?.value,
      analystSeed:            g("remote-analyst-seed")?.value,
      auditorSeed:            g("remote-auditor-seed")?.value,
      longOnly:               g("remote-long-only")?.checked,
      position:               g("remote-position")?.value,
      sectorCap:              g("remote-sector-cap")?.value,
      regularization:         g("remote-regularization")?.value,
      regularizationStrength: g("remote-regularization-strength")?.value,
    };
    localStorage.setItem(CONSOLE_CONFIG_STORAGE_KEY, JSON.stringify(cfg));
  } catch {}
}

function saveGuideConfig() {
  try {
    const cfg = {
      provider: document.getElementById("guide-provider")?.value ?? "",
      model:    document.getElementById("guide-model")?.value ?? "",
    };
    localStorage.setItem(GUIDE_CONFIG_STORAGE_KEY, JSON.stringify(cfg));
  } catch {}
}

function restoreConsoleConfig() {
  try {
    const raw = localStorage.getItem(CONSOLE_CONFIG_STORAGE_KEY);
    if (!raw) return;
    const cfg = JSON.parse(raw);
    const set = (id, key, checkbox) => {
      const el = document.getElementById(id);
      if (!el || cfg[key] == null) return;
      if (checkbox) el.checked = Boolean(cfg[key]);
      else el.value = cfg[key];
    };
    set("remote-training",               "training");
    set("remote-oos",                    "oos");
    set("remote-gpt",                    "gpt",     true);
    set("remote-audit",                  "audit",   true);
    set("remote-refresh",                "refresh", true);
    set("remote-long-only",              "longOnly", true);
    set("remote-max-news",               "maxNews");
    set("remote-batch-size",             "batchSize");
    set("remote-analyst-seed",           "analystSeed");
    set("remote-auditor-seed",           "auditorSeed");
    set("remote-position",               "position");
    set("remote-sector-cap",             "sectorCap");
    set("remote-regularization",         "regularization");
    set("remote-regularization-strength","regularizationStrength");
    if (cfg.researchProvider) {
      const el = document.getElementById("remote-research-provider");
      if (el) el.value = cfg.researchProvider;
      populateModelSelect(
        document.getElementById("remote-gpt-model"),
        "research", cfg.researchProvider, cfg.gptModel
      );
    }
    if (cfg.auditProvider) {
      const el = document.getElementById("remote-audit-provider");
      if (el) el.value = cfg.auditProvider;
      populateModelSelect(
        document.getElementById("remote-audit-model"),
        "audit", cfg.auditProvider, cfg.auditModel
      );
    }
    syncConfigurationControls();
  } catch {}
}

function restoreGuideConfig() {
  try {
    const raw = localStorage.getItem(GUIDE_CONFIG_STORAGE_KEY);
    if (!raw) return;
    const cfg = JSON.parse(raw);
    const provEl  = document.getElementById("guide-provider");
    const modelEl = document.getElementById("guide-model");
    if (provEl  && cfg.provider != null) provEl.value  = cfg.provider;
    if (modelEl && cfg.model    != null) {
      modelEl.value = cfg.model;
      if (provEl) {
        const def = GUIDE_PROVIDER_DEFAULTS[provEl.value] || "";
        modelEl.placeholder = def || "default";
      }
    }
  } catch {}
}

let _configSaveTimer = null;
function scheduleSave() {
  clearTimeout(_configSaveTimer);
  _configSaveTimer = setTimeout(() => { saveConsoleConfig(); saveGuideConfig(); }, 400);
}

// Save on window close
window.addEventListener("beforeunload", () => { saveConsoleConfig(); saveGuideConfig(); });

// Wire debounced save to every console field
[
  "remote-training", "remote-oos", "remote-gpt", "remote-research-provider",
  "remote-gpt-model", "remote-audit", "remote-audit-provider", "remote-audit-model",
  "remote-refresh", "remote-max-news", "remote-batch-size", "remote-analyst-seed",
  "remote-auditor-seed", "remote-long-only", "remote-position", "remote-sector-cap",
  "remote-regularization", "remote-regularization-strength",
].forEach((id) => {
  const el = document.getElementById(id);
  if (!el) return;
  el.addEventListener("change", scheduleSave);
  el.addEventListener("input",  scheduleSave);
});

// Wire debounced save to guide fields
document.getElementById("guide-provider")?.addEventListener("change", scheduleSave);
document.getElementById("guide-model")?.addEventListener("input",   scheduleSave);

// ─────────────────────────────────────────────────────────────────────────────

function guideSetLoading(loading) {
  guideLoading = loading;
  const status = document.getElementById("guide-status");
  const sendBtn = document.getElementById("guide-send");
  const input = document.getElementById("guide-input");
  if (status) status.hidden = !loading;
  if (loading) {
    const txt = document.getElementById("guide-status-text");
    if (txt) txt.textContent = "Allo is typing…";
  }
  if (sendBtn) sendBtn.disabled = loading;
  if (input) input.disabled = loading;
  document.querySelectorAll(".guide-action-btn").forEach((b) => { b.disabled = loading; });
}

function guideSetStatusText(text) {
  const el = document.getElementById("guide-status-text");
  if (el) el.textContent = text;
}

function guideClearError() {
  const el = document.getElementById("guide-error");
  if (el) { el.hidden = true; el.innerHTML = ""; }
}

function humanizeGuideError(raw) {
  if (!raw) return "An unknown error occurred.";
  const s = raw.toLowerCase();

  // No key configured at all
  if (s.includes("no ai provider api key") || s.includes("no api provider")) {
    return "No AI provider is configured. Add at least one API key (OpenAI, Anthropic, Gemini, or Nvidia NIM) in the Reference tab, then restart AlloLabs.";
  }
  // Specific provider key missing
  const noKeyMatch = raw.match(/No API key found for provider ['"]?(\S+?)['"]?\./i);
  if (noKeyMatch) {
    return `No API key is set for ${noKeyMatch[1]}. Add it in the Reference tab and restart AlloLabs.`;
  }
  // All providers failed — surface the individual reasons concisely
  if (s.includes("all ai providers failed")) {
    const reasons = raw.replace(/all ai providers failed\s*[—–-]\s*/i, "").trim();
    // Translate common sub-errors inline
    const cleaned = reasons
      .replace(/timed out|read operation timed out/gi, "timed out")
      .replace(/http 401[^;]*/gi, "invalid API key (401)")
      .replace(/http 429[^;]*/gi, "rate limit hit (429)")
      .replace(/http 400[^;]*/gi, "bad request (400)")
      .replace(/http 5\d\d[^;]*/gi, "server error (5xx)")
      .replace(/network error[^;]*/gi, "network unreachable");
    return `All providers failed: ${cleaned}`;
  }
  // Timeout
  if (s.includes("timed out") || s.includes("read operation")) {
    return "Allo timed out waiting for the AI provider. The service may be busy — use Resend to try again.";
  }
  // Auth
  if (s.includes("401") || s.includes("unauthorized") || s.includes("invalid api key") || s.includes("authentication")) {
    return "Authentication failed — your API key may be invalid or expired. Check the Reference tab.";
  }
  // Rate limit
  if (s.includes("429") || s.includes("rate limit") || s.includes("too many requests")) {
    return "Rate limit exceeded — the AI provider is throttling requests. Wait a moment and resend.";
  }
  // Bad request (usually a model name issue)
  if (s.includes("400") || s.includes("bad request")) {
    return "Bad request to the AI provider — your model name may be incorrect. Check the Model field in the Guide toolbar.";
  }
  // Server error
  if (s.includes("503") || s.includes("502") || s.includes("service unavailable")) {
    return "The AI provider is temporarily unavailable (5xx). Try again in a moment.";
  }
  // Not connected
  if (s.includes("not connected") || s.includes("connect in the console")) {
    return "Not connected to the AlloLabs server. Go to the Console tab and start the connection first.";
  }
  // Guide module missing
  if (s.includes("guide module unavailable") || s.includes("allolabs_guide")) {
    return "Guide module (allolabs_guide.py) is not installed. Reinstall AlloLabs.";
  }
  // Network-level error
  if (s.includes("network error") || s.includes("failed to fetch") || s.includes("networkerror")) {
    return "Network error — cannot reach the AlloLabs server. Is the app still running?";
  }
  // Context length
  if (s.includes("context") && (s.includes("length") || s.includes("limit") || s.includes("tokens"))) {
    return "Conversation is too long for this model's context window. The session will be compacted automatically — try sending again.";
  }
  return raw; // fall back to the raw message if nothing matched
}

function guideShowError(msg, retryText) {
  const el = document.getElementById("guide-error");
  if (!el) return;
  el.hidden = false;
  el.innerHTML = "";
  const msgSpan = document.createElement("span");
  msgSpan.textContent = humanizeGuideError(msg);
  el.appendChild(msgSpan);
  if (retryText) {
    const btn = document.createElement("button");
    btn.className = "guide-error-retry";
    btn.textContent = "Resend";
    btn.addEventListener("click", () => {
      el.hidden = true;
      guideSendMessage(retryText);
    });
    el.appendChild(btn);
  }
}


function _normalizeRunConfig(cfg) {
  // Accept camelCase or snake_case — open-source models use both
  return {
    ...cfg,
    training_years:      cfg.training_years      ?? cfg.trainingYears,
    out_of_sample_months:cfg.out_of_sample_months?? cfg.outOfSampleMonths ?? cfg.oosMonths,
    max_position_weight: cfg.max_position_weight ?? cfg.maxPositionWeight  ?? cfg.maxPosition,
    max_sector_weight:   cfg.max_sector_weight   ?? cfg.maxSectorWeight,
    long_only:           cfg.long_only           ?? cfg.longOnly,
    use_ai_views:        cfg.use_ai_views        ?? cfg.useAiViews         ?? cfg.useAIViews,
    use_ai_audit:        cfg.use_ai_audit        ?? cfg.useAiAudit         ?? cfg.useAIAudit,
    ai_provider:         cfg.ai_provider         ?? cfg.aiProvider,
    analyst_seed_prompt: cfg.analyst_seed_prompt ?? cfg.analystSeedPrompt  ?? cfg.mandate,
    auditor_seed_prompt: cfg.auditor_seed_prompt ?? cfg.auditorSeedPrompt,
  };
}

function guideImportConfig(config, feedbackBtn) {
  if (!config) return;
  config = _normalizeRunConfig(config);

  const setVal = (id, val) => { const el = document.getElementById(id); if (el && val != null) el.value = val; };
  const setChk = (id, val) => { const el = document.getElementById(id); if (el && val != null) { el.checked = Boolean(val); el.dispatchEvent(new Event("change")); } };

  // Numbers
  setVal("remote-training", config.training_years);
  setVal("remote-oos",      config.out_of_sample_months);
  if (config.max_position_weight != null)
    setVal("remote-position", Math.round(config.max_position_weight * 100));
  if (config.max_sector_weight != null)
    setVal("remote-sector-cap", Math.round(config.max_sector_weight * 100));

  // Checkboxes — set use_ai_views FIRST so syncConfigurationControls enables audit toggle
  setChk("remote-long-only", config.long_only);
  setChk("remote-gpt",       config.use_ai_views);
  setChk("remote-audit",     config.use_ai_audit);  // syncConfigurationControls runs on each dispatchEvent

  // Regularization
  if (config.regularization) {
    const el = document.getElementById("remote-regularization");
    if (el) { el.value = config.regularization; el.dispatchEvent(new Event("change")); }
  }

  // Seed prompts
  setVal("remote-analyst-seed",  config.analyst_seed_prompt);
  setVal("remote-auditor-seed",  config.auditor_seed_prompt);

  // Research provider — nvidia-nim is guide-only
  const prov = config.ai_provider;
  if (prov && prov !== "nvidia-nim") {
    const el = document.getElementById("remote-research-provider");
    if (el) {
      el.value = prov;
      populateModelSelect(document.getElementById("remote-gpt-model"), "research", prov);
    }
  }

  // Universe tickers — use the canonical setter so localStorage format is correct
  if (config.tickers?.length) {
    setUniverseSelection(config.tickers, true);
  }

  syncConfigurationControls();
  saveConsoleConfig();

  if (feedbackBtn) {
    feedbackBtn.textContent = "Loaded into Console!";
    feedbackBtn.disabled = true;
  }
  showView("console"); // immediate — no delay
}

const GUIDE_PROVIDER_DEFAULTS = {
  anthropic:   "claude-sonnet-4-6",
  openai:      "gpt-4o-mini",
  gemini:      "gemini-2.5-flash",
  deepseek:    "deepseek-chat",
  "nvidia-nim":"meta/llama-3.3-70b-instruct",
};

function guideGetProvider() {
  const sel = document.getElementById("guide-provider");
  const val = sel ? sel.value : "auto";
  return val === "auto" ? null : val;
}

function guideGetModel() {
  const el = document.getElementById("guide-model");
  return el ? el.value.trim() : "";
}

function gatherConsoleConfig() {
  return {
    trainingYears:         Number(document.getElementById("remote-training")?.value)  || 1,
    oosMonths:             Number(document.getElementById("remote-oos")?.value)        || 6,
    maxPositionPercent:    Number(document.getElementById("remote-position")?.value)   || 25,
    maxSectorPercent:      Number(sectorCapInput?.value)                               || 100,
    longOnly:              longOnlyToggle?.checked ?? true,
    regularization:        regularizationSelect?.value || "none",
    regularizationStrength: Number(regularizationStrength?.value) || 0,
    gptViews:              remoteGptToggle?.checked ?? false,
    researchProvider:      remoteResearchProvider?.value || "",
    researchModel:         document.getElementById("remote-gpt-model")?.value || "",
    auditViews:            remoteAuditToggle?.checked ?? false,
    auditProvider:         remoteAuditProvider?.value || "",
    maxNewsArticles:       Number(document.getElementById("remote-max-news")?.value)   || 5,
    researchBatchSize:     Number(document.getElementById("remote-batch-size")?.value) || 12,
    analystSeedPrompt:     document.getElementById("remote-analyst-seed")?.value?.trim() || "",
    auditorSeedPrompt:     document.getElementById("remote-auditor-seed")?.value?.trim() || "",
  };
}

function gatherLatestResults() {
  if (currentResultMode === "empty") return null;
  const hasMax = portfolioData.max.holdings.length > 0;
  if (!hasMax) return null;
  const genAt = currentResultGeneratedAt
    ? new Date(currentResultGeneratedAt).toLocaleString()
    : null;
  return {
    hasData: true,
    generatedAt: genAt,
    tickerCount: portfolioData.max.holdings.length,
    portfolios: {
      max: {
        metrics: portfolioData.max.metricValues,
        topHoldings: portfolioData.max.holdings.slice(0, 16),
      },
      min: {
        metrics: portfolioData.min.metricValues,
        topHoldings: portfolioData.min.holdings.slice(0, 16),
      },
    },
    research: (researchData || []).slice(0, 40).map((r) => ({
      ticker:         r.ticker,
      view:           r.thesis || "",
      confidence:     r.confidence ?? null,
      posteriorReturn: r.posteriorValue ?? null,
    })),
  };
}

function gatherAppContext() {
  if (!universeCatalogData) return null;
  const runStatusClass = runnerState?.className || "";
  const runStatus = !runnerConnected ? "disconnected"
    : runStatusClass.includes("running") ? "running"
    : "idle";
  const activeEl = document.querySelector(".nav-item.active[data-view]");
  const activeView = activeEl?.dataset?.view || "unknown";
  return {
    selectedTickers:       orderedUniverseSelection(),
    universePreset:        universeSelectionLabel(),
    totalAvailableTickers: universeCatalogData.tickerCount || 0,
    availableMarkets:      (universeCatalogData.groups || []).map((g) => ({
      id:       g.id,
      label:    g.shortLabel,
      total:    g.tickers.length,
      selected: g.tickers.filter((t) => selectedUniverseTickers.has(t)).length,
    })),
    consoleConfig:  gatherConsoleConfig(),
    latestResults:  gatherLatestResults(),
    runStatus,
    activeView,
    guideMode: guideModeEnabled,
  };
}

function guideAddRequestParams(body) {
  const provider = guideGetProvider();
  const model = guideGetModel();
  if (provider) body.provider = provider;
  if (model)    body.guideModel = model;
  const ctx = gatherAppContext();
  if (ctx) body.appContext = ctx;
  return body;
}

async function guideCompact() {
  if (guideHistory.length < 4 || !runnerConnected) return;
  const originalCount = guideHistory.length;
  try {
    const body = guideAddRequestParams({ messages: guideHistory });
    const response = await fetch(runnerEndpoint("/api/guide-compact"), {
      method: "POST",
      headers: runnerHeaders(true),
      body: JSON.stringify(body),
    });
    if (!response.ok) return; // silent failure — compaction is best-effort
    const data = await response.json();
    const summary = data.summary || "";
    if (!summary) return;
    guideSaveMemory(summary);
    const tail = guideHistory.slice(-4);
    guideHistory = [
      { role: "user",      content: `CONVERSATION SUMMARY (auto-compacted):\n${summary}` },
      { role: "assistant", content: "Summary acknowledged — I have full context of our previous discussion." },
      ...tail,
    ];
    guideAppendCompactBadge(originalCount - tail.length);
  } catch {}
}

async function guideApiCall(body) {
  const response = await fetch(runnerEndpoint("/api/guide"), {
    method: "POST",
    headers: runnerHeaders(true),
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    let msg = `Server error ${response.status}`;
    try { const errData = await response.json(); msg = errData.error || msg; } catch {}
    const err = new Error(msg);
    err.retryable = response.status >= 500; // 4xx = config issue, don't retry
    throw err;
  }
  return response.json();
}

async function guideSendMessage(text) {
  const trimmed = text?.trim();
  if (!trimmed || guideLoading) return;

  guideClearError();
  guideHistory.push({ role: "user", content: trimmed });
  guideAppendMessage("user", trimmed);

  const input = document.getElementById("guide-input");
  if (input) input.value = "";

  guideSetLoading(true);
  let responseHandled = false;

  // Retry schedule: [delay before attempt, status label]
  const RETRIES = [
    [0,    "Allo is typing…"],
    [3000, "Taking a little longer than usual…"],
    [5000, "Still working on it…"],
  ];

  try {
    if (!runnerConnected) throw new Error("Not connected to the runner. Connect in the Console tab first.");

    const body = guideAddRequestParams({ messages: guideHistory });
    let data = null;
    let lastErr = null;

    for (let i = 0; i < RETRIES.length; i++) {
      const [delay, label] = RETRIES[i];
      if (i > 0) {
        guideSetStatusText(label);
        await new Promise((r) => setTimeout(r, delay));
      }
      try {
        data = await guideApiCall(body);
        lastErr = null;
        break;
      } catch (err) {
        lastErr = err;
        if (err.retryable === false) break; // configuration error, no point retrying
        if (i === RETRIES.length - 1) break; // exhausted
      }
    }

    if (lastErr) throw lastErr;

    const reply = data.reply || "";
    const mode = data.mode || "normal";
    const runConfig = data.runConfig || null;

    guideHistory.push({ role: "assistant", content: reply });

    guideSetLoading(false);
    responseHandled = true;

    await guideAnimateAlloMessage(reply);

    if (mode === "run_config" && runConfig) {
      guidePendingConfig = runConfig;
      guideAppendConfigCard(runConfig);
    }

    if (guideModeEnabled) {
      alloApplyGuideDirection(data.targetView, data.highlights);
    }

    if (guideHistory.length >= GUIDE_COMPACT_THRESHOLD) {
      guideCompact();
    }
  } catch (err) {
    guideHistory.pop();
    guideShowError(err.message || "Allo is unavailable. Check your API key configuration.", trimmed);
  } finally {
    if (!responseHandled) guideSetLoading(false);
  }
}

document.getElementById("guide-send")?.addEventListener("click", () => {
  const el = document.getElementById("guide-input");
  if (el) guideSendMessage(el.value);
});

document.getElementById("guide-input")?.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    const el = document.getElementById("guide-input");
    if (el) guideSendMessage(el.value);
  }
});

document.getElementById("guide-clear")?.addEventListener("click", () => {
  guideHistory = [];
  guidePendingConfig = null;
  guideMemoryLoaded = false; // allow memory recall on next message
  const chat = document.getElementById("guide-chat");
  if (chat) {
    chat.innerHTML = `<div class="guide-empty" id="guide-empty">
      <span class="guide-empty-title">Ask Allo anything</span>
      <span class="guide-empty-sub">Portfolio theory, macro thesis, run configuration — or click a quick action above to get started.</span>
    </div>`;
  }
  guideClearError();
});

document.querySelectorAll(".guide-action-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const text = GUIDE_QUICK_ACTIONS[btn.dataset.action];
    if (text) guideSendMessage(text);
  });
});


// Update model placeholder when provider changes
document.getElementById("guide-provider")?.addEventListener("change", (e) => {
  const modelInput = document.getElementById("guide-model");
  if (!modelInput) return;
  const def = GUIDE_PROVIDER_DEFAULTS[e.target.value] || "";
  modelInput.placeholder = def || "default";
  // Only auto-fill if the field is empty or contained a previous default
  const prevDefault = Object.values(GUIDE_PROVIDER_DEFAULTS).includes(modelInput.value);
  if (!modelInput.value || prevDefault) modelInput.value = def;
});
restoreGuideConfig();

// Save + compact on tab/window hide
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    saveConsoleConfig();
    saveGuideConfig();
    if (guideHistory.length >= 10) guideCompact();
  }
});

/* ================================================================ */
/* Guide Mode — follow-me Allo dock and UI highlights               */
/* ================================================================ */

const GUIDE_MODE_KEY = "allolabs-guide-mode";
const ALLO_DOCK_POS_KEY = "allolabs-allo-dock-pos";

// Stable highlight keys Allo may reference. Keep in sync with the
// GUIDE MODE & UI HIGHLIGHTS catalog in allolabs_guide.py.
const ALLO_HIGHLIGHT_TARGETS = {
  "tab-overview":      { selector: '.nav-item[data-view="overview"]' },
  "tab-research":      { selector: '.nav-item[data-view="research"]' },
  "tab-universe":      { selector: '.nav-item[data-view="universe"]' },
  "tab-console":       { selector: '.nav-item[data-view="console"]' },
  "tab-history":       { selector: '.nav-item[data-view="history"]' },
  "tab-reference":     { selector: '.nav-item[data-view="reference"]' },
  "tab-guide":         { selector: '.nav-item[data-view="guide"]' },
  "open-report":       { selector: "#open-report-button" },
  "configure":         { selector: "#configure-button" },
  "training-window":   { selector: "#remote-training",          view: "console" },
  "oos-window":        { selector: "#remote-oos",               view: "console" },
  "ai-views":          { selector: "#remote-gpt",               view: "console" },
  "research-provider": { selector: "#remote-research-provider", view: "console" },
  "research-model":    { selector: "#remote-gpt-model",         view: "console" },
  "ai-audit":          { selector: "#remote-audit",             view: "console" },
  "audit-provider":    { selector: "#remote-audit-provider",    view: "console" },
  "analyst-mandate":   { selector: "#remote-analyst-seed",      view: "console" },
  "auditor-mandate":   { selector: "#remote-auditor-seed",      view: "console" },
  "max-position":      { selector: "#remote-position",          view: "console" },
  "sector-cap":        { selector: "#remote-sector-cap",        view: "console" },
  "long-only":         { selector: "#remote-long-only",         view: "console" },
  "regularization":    { selector: "#remote-regularization",    view: "console" },
  "run-button":        { selector: "#runner-start",             view: "console" },
  "universe-search":   { selector: "#universe-search",          view: "universe" },
  "universe-presets":  { selector: "#universe-presets",         view: "universe" },
  "continue-to-run":   { selector: '#universe-view [data-shortcut-view="console"]', view: "universe" },
};

const ALLO_GUIDE_TARGET_VIEWS = new Set([
  "overview", "research", "universe", "console", "history", "reference", "guide"
]);

let guideModeEnabled = localStorage.getItem(GUIDE_MODE_KEY) === "1";
let alloDockCollapsed = false;
let alloHighlightDismissController = null;

function currentViewName() {
  return document.querySelector(".nav-item.active[data-view]")?.dataset?.view || "overview";
}

function updateModeIndicators() {
  const note = document.querySelector(".sidebar-note");
  const noteLabel = note?.querySelector("strong");
  if (noteLabel) noteLabel.textContent = guideModeEnabled ? "Guide mode" : "Research mode";
  note?.classList.toggle("guide-mode-active", guideModeEnabled);
  const tape = document.getElementById("tape-mode");
  if (tape) tape.innerHTML = `<b>Mode</b> ${guideModeEnabled ? "Guide" : "Research"}`;
  const toggle = document.getElementById("guide-mode-toggle");
  if (toggle) toggle.checked = guideModeEnabled;
}

function setGuideMode(enabled) {
  guideModeEnabled = enabled;
  localStorage.setItem(GUIDE_MODE_KEY, enabled ? "1" : "0");
  updateModeIndicators();
  if (!enabled) alloClearHighlights();
  alloDockSync(currentViewName());
}

// ── Dock: the live chat nodes are REPARENTED between the Guide tab and the
// floating dock, so history, listeners, and in-flight requests carry over. ──

function alloChatNodes() {
  return [
    document.getElementById("guide-chat"),
    document.getElementById("guide-status"),
    document.getElementById("guide-error"),
    document.querySelector(".guide-input-row"),
  ].filter(Boolean);
}

function alloDockMount() {
  const dock = document.getElementById("allo-dock");
  const body = document.getElementById("allo-dock-body");
  if (!dock || !body || body.contains(document.getElementById("guide-chat"))) {
    if (dock) dock.hidden = false;
    return;
  }
  alloChatNodes().forEach((node) => body.appendChild(node));
  dock.hidden = false;
  alloDockRestorePosition();
}

function alloDockRestore() {
  const dock = document.getElementById("allo-dock");
  const anchor = document.getElementById("guide-inline-anchor");
  if (!dock || !anchor) return;
  if (dock.contains(document.getElementById("guide-chat"))) {
    let previous = anchor;
    alloChatNodes().forEach((node) => {
      previous.insertAdjacentElement("afterend", node);
      previous = node;
    });
  }
  dock.hidden = true;
}

function alloDockSync(viewName) {
  if (guideModeEnabled && viewName !== "guide") {
    alloDockMount();
  } else {
    alloDockRestore();
  }
}

function alloDockRestorePosition() {
  const dock = document.getElementById("allo-dock");
  if (!dock) return;
  let pos = null;
  try { pos = JSON.parse(localStorage.getItem(ALLO_DOCK_POS_KEY) || "null"); } catch { /* ignore */ }
  if (pos && Number.isFinite(pos.x) && Number.isFinite(pos.y)) {
    alloDockPlace(pos.x, pos.y);
  }
}

function alloDockPlace(x, y) {
  const dock = document.getElementById("allo-dock");
  if (!dock) return;
  const maxX = Math.max(0, window.innerWidth - dock.offsetWidth - 8);
  const maxY = Math.max(0, window.innerHeight - 60);
  const clampedX = Math.min(Math.max(x, 8), maxX);
  const clampedY = Math.min(Math.max(y, 8), maxY);
  dock.style.left = `${clampedX}px`;
  dock.style.top = `${clampedY}px`;
  dock.style.right = "auto";
  dock.style.bottom = "auto";
}

(function wireAlloDockDrag() {
  const header = document.getElementById("allo-dock-header");
  const dock = document.getElementById("allo-dock");
  if (!header || !dock) return;
  let dragOffsetX = 0;
  let dragOffsetY = 0;
  let dragging = false;

  header.addEventListener("pointerdown", (event) => {
    if (event.target.closest(".allo-dock-btn")) return;
    dragging = true;
    const rect = dock.getBoundingClientRect();
    dragOffsetX = event.clientX - rect.left;
    dragOffsetY = event.clientY - rect.top;
    header.setPointerCapture(event.pointerId);
  });
  header.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    alloDockPlace(event.clientX - dragOffsetX, event.clientY - dragOffsetY);
  });
  header.addEventListener("pointerup", (event) => {
    if (!dragging) return;
    dragging = false;
    header.releasePointerCapture(event.pointerId);
    const rect = dock.getBoundingClientRect();
    localStorage.setItem(ALLO_DOCK_POS_KEY, JSON.stringify({ x: rect.left, y: rect.top }));
  });
  window.addEventListener("resize", () => {
    if (!dock.hidden && dock.style.left) {
      const rect = dock.getBoundingClientRect();
      alloDockPlace(rect.left, rect.top);
    }
  });
})();

document.getElementById("allo-dock-collapse")?.addEventListener("click", () => {
  alloDockCollapsed = !alloDockCollapsed;
  document.getElementById("allo-dock")?.classList.toggle("collapsed", alloDockCollapsed);
  const btn = document.getElementById("allo-dock-collapse");
  if (btn) {
    btn.textContent = alloDockCollapsed ? "+" : "–";
    btn.title = alloDockCollapsed ? "Expand" : "Collapse";
  }
});

document.getElementById("allo-dock-goto")?.addEventListener("click", () => {
  showView("guide");
});

document.getElementById("guide-mode-toggle")?.addEventListener("change", (event) => {
  setGuideMode(event.target.checked);
});

// ── Highlights: slow pulsing glow on registry elements Allo points at. ──

function alloClearHighlights() {
  if (alloHighlightDismissController) {
    alloHighlightDismissController.abort();
    alloHighlightDismissController = null;
  }
  document.querySelectorAll(".allo-glow, .allo-glow-fading").forEach((el) => {
    el.classList.remove("allo-glow", "allo-glow-fading");
  });
}

function alloDismissHighlights() {
  const highlighted = [...document.querySelectorAll(".allo-glow")];
  if (!highlighted.length) return;
  alloHighlightDismissController = null;
  highlighted.forEach((el) => {
    el.classList.remove("allo-glow");
    el.classList.add("allo-glow-fading");
  });
  window.setTimeout(() => {
    highlighted.forEach((el) => el.classList.remove("allo-glow-fading"));
  }, 360);
}

function alloApplyHighlights(keys) {
  if (!Array.isArray(keys) || !keys.length) return;
  alloClearHighlights();
  const activeView = currentViewName();
  const targets = new Set();
  keys.slice(0, 6).forEach((key) => {
    const entry = ALLO_HIGHLIGHT_TARGETS[key];
    if (!entry) return;
    const el = document.querySelector(entry.selector);
    if (el) targets.add(el);
    // Element lives in another tab: also glow that tab so the user can find it.
    if (entry.view && entry.view !== activeView) {
      const tab = document.querySelector(`.nav-item[data-view="${entry.view}"]`);
      if (tab) targets.add(tab);
    }
  });
  targets.forEach((el) => {
    el.classList.add("allo-glow");
  });
  if (targets.size) {
    alloHighlightDismissController = new AbortController();
    document.addEventListener("pointerdown", alloDismissHighlights, {
      once: true,
      capture: true,
      signal: alloHighlightDismissController.signal,
    });
  }
}

function alloApplyGuideDirection(targetView, highlights) {
  const requestedView = typeof targetView === "string" ? targetView.trim() : "";
  if (ALLO_GUIDE_TARGET_VIEWS.has(requestedView) && requestedView !== currentViewName()) {
    showView(requestedView);
  }
  if (Array.isArray(highlights) && highlights.length) {
    alloApplyHighlights(highlights);
  }
}

updateModeIndicators();

/* ================================================================ */

const initialView = location.hash.replace("#", "");
const resolvedInitial = viewAliases[initialView] || initialView;
showView(pageTitles[resolvedInitial] ? resolvedInitial : "overview");
renderPortfolio("max");
renderResearch();
if (location.protocol === "http:" || location.protocol === "https:") connectRunner();
