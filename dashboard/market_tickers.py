"""
Comprehensive exchange ticker catalogs for the AlloLabs universe selector.

Tickers use Yahoo Finance format. Each exchange group is mutually exclusive —
no ticker appears in more than one group. Index constituent sub-lists drive
the "Index Leaders" quick-select preset.
"""
from __future__ import annotations

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: U.S. — S&P 500 / NYSE Large Cap
# Full S&P 500 composition (approx. 2025). NASDAQ-listed members of the
# S&P 500 (AAPL, MSFT, etc.) live here, not in the NASDAQ group.
# ═══════════════════════════════════════════════════════════════════════════════

US_SP500: list[str] = [
    # ── Information Technology ──────────────────────────────────────────────
    "AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CSCO", "ADBE", "ACN", "INTU", "IBM",
    "QCOM", "AMD", "TXN", "NOW", "AMAT", "ADI", "LRCX", "KLAC", "MU", "MRVL",
    "CDNS", "SNPS", "FTNT", "PANW", "CRWD", "WDAY", "INTC", "STX", "AKAM",
    "GEN", "MSI", "ZBRA", "TRMB", "TER", "NTAP", "SWKS", "QRVO", "KEYS",
    "EPAM", "DT", "GDDY", "IT", "LDOS", "PAYC", "TYL",
    "WEX", "ANET", "SMCI", "FFIV", "HPQ", "HPE", "GLW", "FSLR",
    # ── Communication Services ───────────────────────────────────────────────
    "META", "GOOGL", "GOOG", "NFLX", "CMCSA", "TMUS", "T", "VZ", "DIS",
    "CHTR", "WBD", "EA", "TTWO", "OMC", "PSKY", "MTCH",
    # ── Consumer Discretionary ───────────────────────────────────────────────
    "AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW", "BKNG", "TJX",
    "ORLY", "MAR", "AZO", "GM", "F", "HLT", "CMG", "EBAY", "ABNB",
    "TSCO", "YUM", "DRI", "PHM", "LEN", "NVR", "POOL", "RCL", "NCLH",
    "LVS", "CZR", "PVH", "RL", "ULTA", "DASH", "GPC", "DHI", "MHK",
    "BWA", "LKQ", "DPZ", "BBWI", "WSM",
    # ── Consumer Staples ─────────────────────────────────────────────────────
    "WMT", "COST", "KO", "PEP", "PM", "MO", "MDLZ", "KHC", "CL",
    "GIS", "KMB", "EL", "SYY", "ADM", "MKC", "CHD", "HSY",
    "CAG", "TSN", "CPB", "HRL", "SJM", "CLX", "LW", "STZ", "TAP",
    "KR", "MNST", "KDP",
    # ── Energy ───────────────────────────────────────────────────────────────
    "XOM", "CVX", "COP", "SLB", "EOG", "PSX", "MPC", "VLO", "OXY",
    "DVN", "FANG", "BKR", "TRGP", "KMI", "OKE", "WMB",
    "APA",     # ── Financials ───────────────────────────────────────────────────────────
    "JPM", "BAC", "WFC", "GS", "MS", "BLK", "AXP", "SCHW", "USB", "C",
    "COF", "PGR", "MET", "PRU", "AIG", "AMP", "TRV", "AFL", "CB",     "ALL", "HIG", "ACGL", "AON", "BEN", "BRO", "CBOE", "CINF", "EG",
    "FITB", "CPAY", "GL", "HBAN", "ICE", "IVZ", "KEY", "LNC", "MCO",
    "MTB", "PFG", "RF", "RJF", "SPGI", "STT", "TROW", "WRB", "WTW",
    "AJG", "BK", "SYF", "BNY", "BRK-B",
    # ── Healthcare ───────────────────────────────────────────────────────────
    "UNH", "LLY", "JNJ", "ABT", "MRK", "TMO", "DHR", "ABBV", "CVS",
    "MDT", "BSX", "ELV", "HCA", "SYK", "ISRG", "AMGN", "GILD", "REGN",
    "VRTX", "BIIB", "IQV", "MCK", "CI", "HUM", "MOH", "ZBH", "BAX",
    "BDX", "CAH", "CRL", "DGX", "DVA", "EW", "HSIC", "IDXX", "ILMN",
    "INCY", "LH", "MTD", "PODD", "RMD", "STE", "TECH", "UHS", "VTRS",
    "A", "WST", "ZTS", "DXCM", "ALGN", "MRNA", "RVTY",     "ALNY", "INSM",
    # ── Industrials ──────────────────────────────────────────────────────────
    "HON", "UNP", "UPS", "GE", "CAT", "RTX", "GD", "DE", "LMT", "BA",
    "EMR", "ETN", "ITW", "PH", "ROK", "AME", "CARR", "OTIS", "CSX",
    "FDX", "DAL", "UAL", "LUV", "FAST", "PCAR", "IR", "CTAS", "VRSK",
    "CPRT", "ODFL", "WAB", "DOV", "SWK", "GWW", "XYL", "AOS", "FTV",
    "PWR", "JBHT", "SNA", "TXT", "HII", "HUBB", "MAS", "ALLE", "CMI",
    "TDG", "TDY", "LHX", "AXON", "ROP", "GEV", "SAIA", "URI", "IEX", "JCI",
    # ── Materials ────────────────────────────────────────────────────────────
    "LIN", "SHW", "APD", "ECL", "DD", "PPG", "NEM", "FCX", "NUE",
    "VMC", "ALB", "CE", "CF", "FMC", "IFF", "EMN", "LYB", "MOS",
    "BALL", "IP", "RPM", "PKG", "AVY", "SW", "DOW",
    # ── Real Estate ──────────────────────────────────────────────────────────
    "AMT", "PLD", "CCI", "EQIX", "PSA", "DLR", "SPG", "O", "WELL",
    "EQR", "AVB", "EXR", "SBAC", "ARE", "VTR", "BXP", "FRT", "HST",
    "IRM", "KIM", "MAA", "NNN", "UDR", "VICI", "CPT", "WPC", "INVH",
    "CBRE",
    # ── Utilities ────────────────────────────────────────────────────────────
    "NEE", "DUK", "SO", "D", "AEP", "EXC", "XEL", "SRE", "CEG",
    "AWK", "CMS", "CNP", "DTE", "EIX", "ETR", "FE", "LNT", "NI",
    "NRG", "PEG", "PNW", "PPL", "WEC", "AEE",
]

# Top ~100 S&P 500 by market cap — used for the Index Leaders preset
SP500_TOP100: list[str] = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "BRK-B", "LLY", "AVGO",
    "TSLA", "JPM", "UNH", "V", "XOM", "COST", "MA", "PG", "JNJ", "HD",
    "ABBV", "NFLX", "BAC", "WMT", "CVX", "MRK", "KO", "ORCL", "CRM", "PEP",
    "TMO", "ACN", "CSCO", "GE", "IBM", "MCD", "ABT", "DHR", "PM", "TXN",
    "LIN", "AMD", "GS", "NOW", "INTU", "VZ", "BKNG", "NEE", "AMGN", "MS",
    "AXP", "ISRG", "RTX", "BLK", "T", "SPGI", "QCOM", "PFE", "LOW", "CAT",
    "UBER", "SCHW", "HON", "UNP", "DE", "SYK", "CMCSA", "BA", "ETN", "AMAT",
    "COP", "VRTX", "TJX", "CB", "PGR", "GILD", "BSX", "REGN", "ELV",
    "ADI", "C", "KLAC", "LRCX", "NKE", "MU", "ADP", "PANW", "WFC",
    "SO", "BMY", "ICE", "MCO", "AON", "DUK", "CEG", "NOC", "USB", "CL",
]

# ── Additional S&P 400 mid-cap & notable NYSE stocks ────────────────────────
US_SP500 += [
    "ADP", "BMY", "NOC", "PG", "V", "MA", "CRM", "PLD", "ENPH",
    "MMM", "PFE", "TGT", "UBER", "PAYX", "CTSH", "ROST",
    # Relisted on NYSE from the LSE (formerly CRH.L / CCL.L)
    "CRH", "CCL",
    # S&P 400 / notable mid-cap additions
    "ACI", "ALLE", "AN", "ANF", "AEO", "ASH", "ATR", "AVNT", "BC", "BFH",
    "BJ", "BLDR", "BR", "BWA", "CACC", "CC", "CNXC", "CR", "CROX", "DKS",
    "DLB", "DORM", "DVA", "EPC", "EXP", "FTDR", "GNRC", "G", "HQY", "HRB",
    "HSY", "HUN", "IBP", "INGR", "ITRI", "JKHY", "KMPR", "KNX",
    "LECO", "LII", "MAN", "MCY", "MKL", "MSA", "MTZ", "MWA",
    "NAVI", "NVT", "OC", "ODFL", "ORI", "PATK", "PAYC", "PBF",
    "RGA", "RHI", "RGEN", "RLI", "RS", "RXO", "SFM", "SIG", "SM",
    "SNX", "SSD", "STLD", "SWX", "THC", "TOL", "TRMK", "TRN", "TXRH",
    "UFPI", "UMBF", "UNM", "WSO", "WTRG", "WTS",
]

# Deduplicate while preserving order
_seen: set[str] = set()
_deduped: list[str] = []
for _t in US_SP500:
    if _t not in _seen:
        _seen.add(_t)
        _deduped.append(_t)
US_SP500 = _deduped


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: U.S. — NASDAQ Extended
# Prominent NASDAQ-listed companies NOT in the S&P 500 above.
# Includes tech growth, recent IPOs, and international cos on NASDAQ.
# ═══════════════════════════════════════════════════════════════════════════════

US_NASDAQ_EXT: list[str] = [
    # ── Mega / Large growth ─────────────────────────────────────────────────
    "MELI", "PDD", "PLTR", "APP", "ARM", "DDOG", "ZS", "TEAM", "WDAY",
    "MRVL", "MPWR", "NXPI", "MCHP", "CDW", "GFS", "ON", "ROP", "SNPS",
    "CDNS", "FTNT", "CRWD", "PANW", "MDB", "ABNB", "DASH",
    # ── Cloud / SaaS growth ─────────────────────────────────────────────────
    "NET", "SNOW", "TTD", "OKTA", "DOCU", "TWLO", "GTM", "MNDY",
    "GTLB", "BILL", "BRZE", "TOST", "PATH", "FROG",     "DOMO", "PCTY", "ESTC", "CWAN", "FRSH", "HUBS",     # ── Fintech ─────────────────────────────────────────────────────────────
    "COIN", "AFRM", "UPST", "HOOD", "MQ", "LMND", "ROOT", "SOFI",
    "LC", "OPEN", "CBRE",
    # ── Consumer tech / EV / Mobility ───────────────────────────────────────
    "RIVN", "LCID", "CHWY", "RBLX", "DUOL", "LYFT", "U",
    # ── Healthcare tech / Biotech ───────────────────────────────────────────
    "AGEN", "RCKT", "ACAD", "KRYS", "IRDM", "IOVA",
    "RARE", "NTLA", "BEAM", "EDIT", "CRSP", "FATE", "KYMR",
    # ── Semiconductors (non S&P 500) ────────────────────────────────────────
    "WOLF", "CEVA", "AMBA", "FORM", "POWI", "SLAB", "DIOD", "SIMO",
    # ── International on NASDAQ (US-listed ADRs that trade as NASDAQ stocks)─
    "ASML", "TSM", "NVO", "BIDU", "JD", "SE", "CPNG", "GRAB",
]

# Deduplicate and remove any that leaked into US_SP500
_sp500_set = set(US_SP500)
US_NASDAQ_EXT = list(dict.fromkeys(t for t in US_NASDAQ_EXT if t not in _sp500_set))


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Canada — TSX (Composite + Extended)
# TSX 60 + TSX Composite 300 main names, in Yahoo Finance .TO / -UN.TO format.
# ═══════════════════════════════════════════════════════════════════════════════

# TSX 60 — used for Index Leaders preset
TSX60: list[str] = [
    # ── Banks ────────────────────────────────────────────────────────────────
    "RY.TO", "TD.TO", "BNS.TO", "BMO.TO", "CM.TO", "NA.TO",
    # ── Insurance / Financial ────────────────────────────────────────────────
    "MFC.TO", "SLF.TO", "GWO.TO", "IFC.TO", "POW.TO", "FFH.TO", "IAG.TO",
    # ── Pipelines / Energy ───────────────────────────────────────────────────
    "ENB.TO", "TRP.TO", "CNQ.TO", "SU.TO", "CVE.TO", "IMO.TO", "TOU.TO",
    # ── Brookfield Asset Management family ───────────────────────────────────
    "BAM.TO", "BN.TO", "BIP-UN.TO", "BEP-UN.TO",
    # ── Utilities ────────────────────────────────────────────────────────────
    "FTS.TO", "EMA.TO", "PPL.TO", "H.TO",
    # ── Railroads / Transport ────────────────────────────────────────────────
    "CNR.TO", "CP.TO", "WCN.TO", "TFII.TO",
    # ── Technology ───────────────────────────────────────────────────────────
    "CSU.TO", "SHOP.TO", "OTEX.TO", "GIB-A.TO",
    # ── Gold / Silver / Mining ───────────────────────────────────────────────
    "ABX.TO", "AEM.TO", "WPM.TO", "FNV.TO", "K.TO",
    # ── Base Metals / Fertilizers ────────────────────────────────────────────
    "NTR.TO", "TECK-B.TO", "FM.TO",
    # ── Consumer / Retail ────────────────────────────────────────────────────
    "ATD.TO", "DOL.TO", "MRU.TO", "L.TO", "WN.TO", "QSR.TO",
    # ── Diversified ──────────────────────────────────────────────────────────
    "TRI.TO",
    # ── Telecom ──────────────────────────────────────────────────────────────
    "RCI-B.TO", "BCE.TO", "T.TO",
    # ── Industrials ──────────────────────────────────────────────────────────
    "WSP.TO", "MG.TO", "CLS.TO",
    # ── Uranium / Specialty ──────────────────────────────────────────────────
    "CCO.TO",
]

# TSX Composite Extended — additional TSX Composite 300 names
CANADA_TSX_ALL: list[str] = list(TSX60) + [
    # ── Energy Extended ──────────────────────────────────────────────────────
    "ARX.TO", "BTE.TO", "WCP.TO", "VET.TO", "TVE.TO",     "PSK.TO", "PEY.TO", "AAV.TO", "SGY.TO",
    # ── Gold / Precious Metals Extended ─────────────────────────────────────
    "LUC.TO", "ELD.TO", "AGI.TO", "OGC.TO",     "DPM.TO", "IMG.TO",     # ── Base Metals Extended ─────────────────────────────────────────────────
    "HBM.TO", "CS.TO", "LIF.TO",     # ── Technology Extended ───────────────────────────────────────────────────
    "LSPD.TO", "DCBO.TO", "GS.TO", "TOI.V", "DND.TO", "BB.TO",
    "CIGI.TO",     # ── Industrials Extended ─────────────────────────────────────────────────
    "STN.TO", "ATS.TO", "SJ.TO", "NFI.TO", "RUS.TO", "MTY.TO",
    "BYD.TO", "TIH.TO", "EIF.TO", "AC.TO",
    # ── Consumer Extended ─────────────────────────────────────────────────────
    "GFL.TO", "PZA.TO", "EMP-A.TO", "SAP.TO",
    # ── REITs ─────────────────────────────────────────────────────────────────
    "CAR-UN.TO", "HR-UN.TO", "AP-UN.TO", "SRU-UN.TO", "DIR-UN.TO",
    "CHP-UN.TO", "GRT-UN.TO", "MRT-UN.TO",
    "D-UN.TO",
    # ── Financial Extended ────────────────────────────────────────────────────
    "EQB.TO", "IGM.TO", "CG.TO",
    # ── Utilities Extended ───────────────────────────────────────────────────
    "AQN.TO", "NPI.TO", "ALA.TO", "BLX.TO",     # ── Healthcare ────────────────────────────────────────────────────────────
    "WELL.TO", "DRX.TO",
]

# Deduplicate
_seen_ca: set[str] = set()
_deduped_ca: list[str] = []
for _t in CANADA_TSX_ALL:
    if _t not in _seen_ca:
        _seen_ca.add(_t)
        _deduped_ca.append(_t)
CANADA_TSX_ALL = _deduped_ca


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: United Kingdom — FTSE (100 + 250 selected)
# Yahoo Finance appends .L for London Stock Exchange listings.
# ═══════════════════════════════════════════════════════════════════════════════

# FTSE 100 — used for Index Leaders preset
FTSE100: list[str] = [
    # ── Pharma / Healthcare ────────────────────────────────────────────────
    "AZN.L", "GSK.L", "SN.L", "HLN.L",     # ── Consumer Staples ─────────────────────────────────────────────────
    "ULVR.L", "DGE.L", "BATS.L", "IMB.L", "ABF.L", "RKT.L",
    "TSCO.L", "SBRY.L", "MKS.L",
    # ── Energy ──────────────────────────────────────────────────────────
    "SHEL.L", "BP.L",
    # ── Mining / Materials ───────────────────────────────────────────────
    "RIO.L", "GLEN.L", "AAL.L", "MNDI.L",
    # ── Financials ───────────────────────────────────────────────────────
    "HSBA.L", "LLOY.L", "BARC.L", "NWG.L", "STAN.L", "LSEG.L",
    "MNG.L", "ADM.L", "PRU.L", "III.L",
    # ── Industrials ──────────────────────────────────────────────────────
    "BA.L", "RR.L", "SMIN.L", "EXPN.L",
    "ITRK.L", "HLMA.L",
    # ── Telecom / Media ──────────────────────────────────────────────────
    "VOD.L", "BT-A.L", "WPP.L",
    # ── Utilities ────────────────────────────────────────────────────────
    "NG.L", "SSE.L", "UU.L", "SVT.L", "CNA.L",
    # ── Real Estate ──────────────────────────────────────────────────────
    "LAND.L", "BLND.L", "SGRO.L", "HMSO.L",
    # ── Consumer Discretionary ───────────────────────────────────────────
    "CPG.L", "JD.L", "BME.L", "OCDO.L", "EZJ.L", "IAG.L",
    "AUTO.L", "FLTR.L",
    # ── Technology / Data ────────────────────────────────────────────────
    "REL.L",
    # ── Diversified ──────────────────────────────────────────────────────
    ]

# FTSE 250 selected additions
UK_FTSE_ALL: list[str] = list(FTSE100) + [
    # ── FTSE 250 additions ────────────────────────────────────────────────
    "SDR.L", "WISE.L", "DPLM.L", "HIK.L", "WIZZ.L", "ATG.L",
    "HTG.L", "SPX.L",
    "BKG.L", "PSN.L", "TW.L", "RTO.L", "BTRW.L", "VTY.L",
    "BBOX.L", "PHP.L", "IHG.L",     "CKN.L", "WEIR.L", "DFS.L", "GNS.L",
    "INCH.L", "MTO.L", "CHG.L", "CLDN.L",
    "NXT.L", "PETS.L", "AAF.L", "SBRE.L",
]

# Deduplicate
_seen_uk: set[str] = set()
_deduped_uk: list[str] = []
for _t in UK_FTSE_ALL:
    if _t not in _seen_uk:
        _seen_uk.add(_t)
        _deduped_uk.append(_t)
UK_FTSE_ALL = _deduped_uk


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Europe — STOXX 600 main constituents
# Multi-exchange: .DE (Xetra), .PA (Euronext Paris), .AS (Amsterdam),
# .MI (Milan), .MC (Madrid), .BR (Brussels), .SW (Swiss Exchange).
# ═══════════════════════════════════════════════════════════════════════════════

# EuroStoxx 50 — used for Index Leaders preset
EUROSTOXX50: list[str] = [
    # ── Germany (.DE) ─────────────────────────────────────────────────────
    "SAP.DE", "ALV.DE", "SIE.DE", "MUV2.DE", "DTE.DE", "RHM.DE",
    "BAYN.DE", "MBG.DE", "BMW.DE", "IFX.DE", "DB1.DE", "BEI.DE",
    # ── France (.PA) ──────────────────────────────────────────────────────
    "AIR.PA", "OR.PA", "MC.PA", "SAN.PA", "BNP.PA", "ENGI.PA",
    "TTE.PA", "EL.PA", "RMS.PA", "SU.PA", "AI.PA", "DG.PA",
    "SAF.PA", "CS.PA", "ACA.PA",
    # ── Netherlands (.AS) ─────────────────────────────────────────────────
    "ASML.AS", "INGA.AS", "AD.AS",
    # ── Italy (.MI) ───────────────────────────────────────────────────────
    "ENEL.MI", "ISP.MI", "ENI.MI", "UCG.MI", "G.MI",
    # ── Spain (.MC) ───────────────────────────────────────────────────────
    "SAN.MC", "IBE.MC", "BBVA.MC", "ITX.MC",
    # ── Belgium (.BR) ─────────────────────────────────────────────────────
    "ABI.BR",
    # ── Switzerland (.SW) ─────────────────────────────────────────────────
    "NESN.SW", "NOVN.SW", "RO.SW", "UBSG.SW",
]

# Full STOXX 600 extended coverage
EUROPE_STOXX_ALL: list[str] = list(EUROSTOXX50) + [
    # ── Germany Extended ──────────────────────────────────────────────────
    "VOW3.DE", "HEN3.DE", "CON.DE", "MTX.DE", "FRE.DE", "ZAL.DE",
    "DHER.DE", "AFX.DE", "BOSS.DE", "MRK.DE", "FME.DE", "EVT.DE",
    "HEI.DE", "SHL.DE", "VNA.DE", "TEG.DE", "TUI1.DE",
    # ── France Extended ───────────────────────────────────────────────────
    "KER.PA", "DSY.PA", "HO.PA", "SGO.PA", "ML.PA", "RI.PA",
    "CAP.PA", "PUB.PA", "CA.PA", "VIE.PA", "WLN.PA", "GLE.PA",
    "SW.PA", "LR.PA", "BN.PA", "MT.AS",
    # ── Netherlands Extended ─────────────────────────────────────────────
    "PHIA.AS", "ABN.AS", "NN.AS", "AKZA.AS", "WKL.AS", "HEIA.AS",
    "URW.PA", "RAND.AS", "IMCD.AS", "BESI.AS",
    # ── Belgium Extended ──────────────────────────────────────────────────
    "UCB.BR", "COLR.BR", "KBC.BR", "AGS.BR", "SOLB.BR", "WDP.BR",
    # ── Switzerland Extended ──────────────────────────────────────────────
    "ZURN.SW", "ABBN.SW", "CFR.SW", "ALC.SW", "GEBN.SW",
    "LONN.SW", "SREN.SW", "SLHN.SW", "ADEN.SW", "SGKN.SW",
    # ── Italy Extended ────────────────────────────────────────────────────
    "RACE.MI", "STLAM.MI", "LDO.MI", "TIT.MI", "PST.MI",
    "BMED.MI", "PRY.MI", "CPR.MI", "MONC.MI",
    # ── Spain Extended ────────────────────────────────────────────────────
    "REP.MC", "ELE.MC", "TEF.MC", "FER.MC", "AMS.MC", "MAP.MC",
    # ── Scandinavia / Other ───────────────────────────────────────────────
    "NOKIA.HE", "NESTE.HE", "SAMPO.HE", "FORTUM.HE",
    "ERIC-B.ST", "VOLV-B.ST", "ATCO-A.ST", "SAND.ST", "ESSITY-B.ST",
    "NHY.OL", "DNB.OL", "TEL.OL", "EQNR.OL", "ORK.OL",
    "NOVO-B.CO", "DSV.CO", "CARL-B.CO", "MAERSK-B.CO",
]

# Deduplicate
_seen_eu: set[str] = set()
_deduped_eu: list[str] = []
for _t in EUROPE_STOXX_ALL:
    if _t not in _seen_eu:
        _seen_eu.add(_t)
        _deduped_eu.append(_t)
EUROPE_STOXX_ALL = _deduped_eu


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Global ADRs
# International market leaders trading as US-listed ADRs (no exchange suffix).
# Excludes companies that already appear in a regional group above.
# ═══════════════════════════════════════════════════════════════════════════════

GLOBAL_ADRS: list[str] = [
    # ── Japan ─────────────────────────────────────────────────────────────
    "TM", "SONY", "MUFG", "HMC", "SMFG", "MFG", "NTTYY", "NTDOY",
    "FANUY", "KYOCY", "HTHIY",
    # ── South Korea ───────────────────────────────────────────────────────
    "KB", "SHG", "KEP", "PKX",
    # ── Taiwan ────────────────────────────────────────────────────────────
    "UMC", "ASX", "HIMX",
    # ── China (US-listed ADRs) ────────────────────────────────────────────
    "BABA", "PDD", "JD", "BIDU", "NIO", "LI", "XPEV", "TME", "NTES",
    # ── India ─────────────────────────────────────────────────────────────
    "INFY", "WIT", "HDB", "IBN", "SIFY",
    # ── Brazil ────────────────────────────────────────────────────────────
    "VALE", "PBR", "PBR-A", "ITUB", "BBD", "ABEV",
    # ── Australia ─────────────────────────────────────────────────────────
    "BHP", "RIO",
    # ── UK / Europe (US-traded versions distinct from .L/.PA listings) ───
    "BTI", "DEO", "UL", "HSBC", "BCS", "LYG", "NGG", "AZN",
    "NVO", "RHHBY",
    # ── Other ─────────────────────────────────────────────────────────────
    "SE", "GRAB", "CPNG", "SAP",
]

# Deduplicate (and remove any already in other groups)
_all_above = _seen | _seen_ca | _seen_uk | _seen_eu | set(US_NASDAQ_EXT)
GLOBAL_ADRS = list(dict.fromkeys(t for t in GLOBAL_ADRS if t not in _all_above))


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Preset Ticker Collections
# Used by universe.py to populate quick-select preset buttons.
# ═══════════════════════════════════════════════════════════════════════════════

# Index Leaders preset — major benchmark index constituents across all markets
INDEX_LEADERS_TICKERS: list[str] = list(dict.fromkeys(
    SP500_TOP100
    + TSX60
    + FTSE100
    + EUROSTOXX50
    + ["TM", "SONY", "MUFG", "TSM", "NVO", "BABA", "VALE", "BHP", "RIO", "SAP", "ASML"]
))

# Curated cross-market starter set (legacy preset — kept for backward compat)
CURATED_RESEARCH_TICKERS: list[str] = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "LLY",
    "JPM", "XOM", "COST", "ISRG", "RY.TO", "TD.TO", "ENB.TO", "CNQ.TO",
    "BAM.TO", "MFC.TO", "FTS.TO", "CNR.TO", "CP.TO", "SHOP.TO", "CSU.TO",
    "AEM.TO", "NTR.TO", "AZN.L", "SHEL.L", "HSBA.L", "ULVR.L", "LSEG.L",
    "ASML.AS", "SAP.DE", "SIE.DE", "MC.PA", "BNP.PA", "NESN.SW",
    "NOVN.SW", "RHHBY", "UBSG.SW",
]

# Canada-only preset (legacy)
CANADA_RESEARCH_TICKERS: list[str] = [
    "RY.TO", "TD.TO", "BMO.TO", "BNS.TO", "NA.TO", "CM.TO",
    "ENB.TO", "TRP.TO", "SU.TO", "CNQ.TO", "CVE.TO", "TOU.TO",
    "POW.TO", "SLF.TO", "MFC.TO", "FFH.TO", "BAM.TO", "BN.TO",
    "BIP-UN.TO", "FTS.TO", "EMA.TO", "PPL.TO", "TRI.TO", "OTEX.TO",
    "CSU.TO", "WCN.TO", "WSP.TO", "CNR.TO", "CP.TO", "ATD.TO",
    "DOL.TO", "QSR.TO", "MRU.TO", "SHOP.TO", "GIB-A.TO", "WN.TO",
    "WPM.TO", "FNV.TO", "AEM.TO", "ABX.TO", "TECK-B.TO", "NTR.TO",
    "FM.TO", "CCO.TO", "BCE.TO", "T.TO", "RCI-B.TO", "CLS.TO",
    "GWO.TO", "IFC.TO", "IMO.TO",
]
