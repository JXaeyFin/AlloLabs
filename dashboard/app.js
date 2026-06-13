const emptyPortfolio = {
  metrics: { return: "--", risk: "--", sharpe: "--", concentration: "--" },
  metricValues: { return: NaN, risk: NaN, sharpe: NaN, concentration: NaN },
  note: "Run an analysis to populate the portfolio allocation and sector breakdown.",
  holdings: [],
  sectors: []
};

let portfolioData = { max: emptyPortfolio, min: emptyPortfolio };
let researchData = [];
const companyDetailsCache = new Map();
let companyModalTrigger = null;

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
  }
];

const PROVIDER_KEY_SETUP = {
  openai: { label: "OpenAI", environment: "OPENAI_API_KEY" },
  anthropic: { label: "Anthropic", environment: "ANTHROPIC_API_KEY" },
  gemini: { label: "Google Gemini", environment: "GEMINI_API_KEY" }
};
let providerKeyStatusSignature = "";

function providerSetupCommand(environment, persistent = false) {
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
        <div class="provider-key-preview">
          <small>Censored preview</small>
          <code>${escapeHtml(preview || "No key detected")}</code>
          <span>${escapeHtml(source)}</span>
        </div>
        <details class="provider-key-instructions"${detected ? "" : " open"}>
          <summary>${detected ? "Replace key or review setup" : "How to configure"}</summary>
          <p>For a temporary key, start the dashboard again from the same PowerShell window. For a persistent key, reopen PowerShell before restarting the dashboard.</p>
          <label>
            <span>Current PowerShell session</span>
            <code>${escapeHtml(providerSetupCommand(environment))}</code>
            <button type="button" data-copy-provider-command="${escapeHtml(providerSetupCommand(environment))}">Copy</button>
          </label>
          <label>
            <span>Persistent Windows user variable</span>
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
  const providers = ["OpenAI", "Anthropic", "Google"];
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

function setFinanceValue(elementId, value, text, neutral = false) {
  const element = document.getElementById(elementId);
  element.textContent = text;
  element.classList.remove("finance-positive", "finance-negative", "finance-neutral");
  element.classList.add(financeClass(value, neutral));
}

const pageTitles = {
  overview: "Overview",
  portfolios: "Portfolios",
  research: "AI Research",
  console: "Run Console",
  report: "Report",
  models: "Model Guide"
};

function showView(viewName) {
  if (!pageTitles[viewName]) return;
  document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
  document.getElementById(`${viewName}-view`)?.classList.add("active");
  document.querySelector(`[data-view="${viewName}"]`)?.classList.add("active");
  document.getElementById("page-title").textContent = pageTitles[viewName];
  history.replaceState(null, "", `#${viewName}`);
  window.scrollTo({ top: 0, behavior: "smooth" });
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

  let runningTotal = 0;
  const gradientStops = data.sectors.map(([, value, color]) => {
    const start = runningTotal;
    runningTotal += value;
    return `${color} ${start}% ${runningTotal}%`;
  });
  document.getElementById("sector-donut").style.background = gradientStops.length
    ? `conic-gradient(${gradientStops.join(",")})`
    : "#edf2f5";
  document.getElementById("sector-legend").innerHTML = data.sectors.length ? data.sectors.map(([sector, value, color]) => `
    <div class="sector-item">
      <i class="sector-swatch" style="background:${color}"></i>
      <span>${sector}</span>
      <strong class="finance-neutral">${value.toFixed(1)}%</strong>
    </div>
  `).join("") : '<span class="terminal-muted">Awaiting run</span>';
}

function renderResearch(query = "") {
  const normalized = query.trim().toLowerCase();
  const filtered = researchData.filter((item) =>
    `${item.ticker} ${item.industry} ${item.thesis}`.toLowerCase().includes(normalized)
  );
  const container = document.getElementById("research-list");
  if (!filtered.length) {
    container.innerHTML = `<div class="empty-state">${normalized ? "No research views match that search." : "No completed research run is available."}</div>`;
    return;
  }
  container.innerHTML = filtered.map((item) => `
    <article class="research-card">
      <div class="ticker-block">
        <div class="ticker-line">
          <button class="research-ticker" type="button" data-company-ticker="${escapeHtml(item.ticker)}" data-company-context="research" title="Open ${escapeHtml(item.ticker)} company details">${escapeHtml(item.ticker)}</button>
          <span class="market-flag" title="${escapeHtml(item.exchange)}">${item.flag}</span>
        </div>
        <span>${item.industry}</span>
        <div class="market-meta">
          <span class="market-badge">${item.market}</span>
          <span class="exchange-label">${item.exchange}${item.listingDetails ? ` · ${item.listingDetails}` : ""}</span>
          <span class="listing-source">${item.source === "Yahoo Finance" ? "YF LIVE" : "FALLBACK"}</span>
        </div>
        <div class="index-strip">
          <small>INDEX / ETF</small>
          ${item.references.map((reference) => `<b>${reference}</b>`).join("")}
        </div>
      </div>
      <div class="research-thesis">${item.thesis}</div>
      <div class="research-stat"><span>Posterior return</span><strong class="${financeClass(item.posteriorValue)}">${item.posterior}</strong></div>
      <div class="research-stat">
        <span>Confidence</span><strong class="finance-neutral">${item.confidence}%</strong>
        <div class="confidence-track"><i style="width:${item.confidence}%"></i></div>
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
  const palette = ["#f4f5f6", "#3ad17d", "#aeb5bd", "#737b85", "#d8dce0", "#ff5e68", "#555d66"];
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
    ])
  };
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

function renderPerformance(performance) {
  if (!performance?.dates?.length || !performance.series) return;
  const maxSeries = performance.series.Max_Sharpe || [];
  const minSeries = performance.series.Min_Vol || [];
  const benchmarkName = Object.keys(performance.series).find((name) => !["Max_Sharpe", "Min_Vol"].includes(name));
  const benchmarkSeries = benchmarkName ? performance.series[benchmarkName] : [];
  const allValues = [...maxSeries, ...minSeries, ...benchmarkSeries].map(Number).filter(Number.isFinite);
  if (!allValues.length) return;
  const minimum = Math.min(...allValues);
  const maximum = Math.max(...allValues);
  document.getElementById("chart-max").setAttribute("d", chartPath(maxSeries, minimum, maximum));
  document.getElementById("chart-min").setAttribute("d", chartPath(minSeries, minimum, maximum));
  document.getElementById("chart-benchmark").setAttribute("d", chartPath(benchmarkSeries, minimum, maximum));

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
  currentResultMode = isExample ? "example" : "live";
  const durations = formatDuration(results.config);
  document.getElementById("hero-training").textContent = durations.training;
  document.getElementById("hero-oos").textContent = durations.oos;
  document.getElementById("hero-cap").textContent = `${Number(results.config.maxPositionPercent).toFixed(0)}%`;
  document.getElementById("data-date").textContent = isExample
    ? `${results.snapshotLabel || "Bundled example"} · Data through ${results.dataThrough || "snapshot date"}`
    : `Live run · Data through ${results.dataThrough || "latest completed run"}`;
  document.getElementById("data-mode").textContent = isExample ? "WEALTHGPT SNAPSHOT" : "WEALTHGPT LIVE";
  document.getElementById("run-label").textContent = isExample ? "Bundled example portfolio" : "Latest model run";

  setFinanceValue("overview-max-return", results.metrics.max.return, formatPercent(results.metrics.max.return));
  setFinanceValue("overview-max-risk", results.metrics.max.risk, formatPercent(results.metrics.max.risk), true);
  setFinanceValue("overview-max-sharpe", results.metrics.max.sharpe, Number(results.metrics.max.sharpe).toFixed(2));
  setFinanceValue("overview-min-return", results.metrics.min.return, formatPercent(results.metrics.min.return));
  setFinanceValue("overview-min-risk", results.metrics.min.risk, formatPercent(results.metrics.min.risk), true);
  setFinanceValue("overview-min-sharpe", results.metrics.min.sharpe, Number(results.metrics.min.sharpe).toFixed(2));

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
  document.getElementById("remote-universe").value = results.config.universe;
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
  syncConfigurationControls();
  renderPerformance(results.performance);
}

document.querySelectorAll(".nav-item").forEach((item) => {
  item.addEventListener("click", () => showView(item.dataset.view));
});

document.querySelectorAll("[data-shortcut-view]").forEach((item) => {
  item.addEventListener("click", () => showView(item.dataset.shortcutView));
});

const functionViews = ["overview", "portfolios", "research", "console", "report", "models"];
document.addEventListener("keydown", (event) => {
  const match = /^F([1-6])$/.exec(event.key);
  if (!match) return;
  event.preventDefault();
  showView(functionViews[Number(match[1]) - 1]);
});

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
  showView("report");
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
runnerUrl.value = localStorage.getItem("wealthgpt-runner-url") || hostedRunnerUrl;

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
  const logoPath = "/resources/wealthgpt-logo.png";
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

async function runnerRequest(path, options = {}) {
  const response = await fetch(runnerEndpoint(path), {
    ...options,
    headers: { ...runnerHeaders(Boolean(options.body)), ...(options.headers || {}) }
  });
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
    document.getElementById("company-modal-body").innerHTML = '<div class="company-error">Connect to the WealthGPT runner to load company details.</div>';
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
    let details = companyDetailsCache.get(ticker);
    if (!details) {
      details = await runnerRequest(`/api/company?ticker=${encodeURIComponent(ticker)}`);
      companyDetailsCache.set(ticker, details);
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

function estimatedUniverseSize(universe) {
  if (universe === "canada") return 21;
  if (universe === "curated") return 39;
  return 249;
}

function buildRunProgressPlan(config = {}) {
  const universeSize = estimatedUniverseSize(config.universe);
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
  } else if (line.includes("Generating portfolio summary PDF")) {
    setRunProgressStage("report", 0.12, "Building portfolio summary PDF");
  } else if (line.includes("Portfolio summary saved")) {
    setRunProgressStage("report", 0.94, "Portfolio report saved");
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
  const response = await fetch(runnerEndpoint(path), { headers: runnerHeaders(false) });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const error = new Error(payload.error || `Artifact returned HTTP ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return response.blob();
}

function setReportState(status, label) {
  const element = document.getElementById("report-state");
  element.className = `runner-state ${status}`;
  element.querySelector("strong").textContent = label;
}

async function refreshReportArtifacts() {
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

  try {
    const pdfBlob = await fetchArtifact("/api/artifacts/pdf");
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
    const chartBlob = await fetchArtifact("/api/artifacts/chart");
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
  const readyLabel = currentResultMode === "example" ? "Example report ready" : "Report ready";
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
      if (status.status === "completed") finishRunProgress("completed");
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
    clearInterval(runnerPollTimer);
    runnerPollTimer = null;
  }
}

async function connectRunner() {
  localStorage.setItem("wealthgpt-runner-url", runnerUrl.value.trim());
  setRunnerState("disconnected", "Connecting");
  try {
    const status = await runnerRequest("/api/status");
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
document.getElementById("refresh-report").addEventListener("click", refreshReportArtifacts);
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
    universe: document.getElementById("remote-universe").value,
    gptViews: remoteGptToggle.checked,
    researchProvider: remoteResearchProvider.value,
    researchModel: remoteGptModel.value,
    auditViews: remoteAuditToggle.checked,
    auditProvider: remoteAuditProvider.value,
    auditModel: remoteAuditModel.value,
    refreshCache: document.getElementById("remote-refresh").checked
  };
  try {
    if (config.trainingYears < 0.25 || config.trainingYears > 10) throw new Error("Training lookback must be between 0.25 and 10 years.");
    if (config.oosMonths < 0 || config.oosMonths > 60) throw new Error("OOS window must be between 0 and 60 months.");
    if (config.maxPositionPercent < 1 || config.maxPositionPercent > 100) throw new Error("Maximum position must be between 1% and 100%.");
    if (config.maxSectorPercent < 5 || config.maxSectorPercent > 100) throw new Error("Maximum sector weight must be between 5% and 100%.");
    if (config.regularizationStrength < 0 || config.regularizationStrength > 10) throw new Error("Regularization strength must be between 0 and 10.");
    if (config.auditViews && !config.gptViews) throw new Error("Global AI audit requires AI-assisted views.");
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

const initialView = location.hash.replace("#", "");
showView(pageTitles[initialView] ? initialView : "overview");
renderPortfolio("max");
renderResearch();
if (location.protocol === "http:" || location.protocol === "https:") connectRunner();
