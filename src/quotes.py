import yfinance as yf

# Mapping ISIN -> ticker Yahoo Finance
# Note : certains tickers ETF luxembourgeois/irlandais sont non-standards,
# à compléter/corriger au fur et à mesure.
ISIN_TO_TICKER: dict[str, str] = {
    "LU1681043599": "CW8.PA",    # Amundi MSCI World Swap UCITS ETF EUR ACC
    "IE0002XZSHO1": "EUNL.DE",   # iShares MSCI World Swap PEA UCITS ETF EUR ACC (WPEA.PA hors service)
    "FR0000120271": "TTE.PA",    # TOTALENERGIES SE
    "FR0000125486": "DG.PA",     # VINCI
    "FR0000120503": "EN.PA",     # BOUYGUES
    "FR0000120073": "AI.PA",     # AIR LIQUIDE
    "FR0013258662": "AYV.PA",    # ALD/Ayvens (ALD.PA hors service après fusion SG)
    "FR0000131104": "BNP.PA",    # BNP PARIBAS
    "FR0011950732": "ELIOR.PA",  # ELIOR GROUP
    "FR0010112524": "NXI.PA",    # NEXITY
    "FR0000130809": "GLE.PA",    # SOCIETE GENERALE
    "NL00150001Q9": "STLAM.MI",  # STELLANTIS (Euronext Milan — STLAM.PA hors service sur yfinance)
    "NL0000226223": "STM.DE",    # STMICROELECTRONICS (STM.PA hors service — Xetra EUR)
    "FR0000124141": "VIE.PA",    # VEOLIA ENVIRONNEMENT
}

# Cache des tickers trouvés automatiquement (évite les recherches répétées)
_auto_ticker_cache: dict[str, str | None] = {}


def _find_ticker_auto(isin: str) -> str | None:
    """Tente de trouver automatiquement le ticker Yahoo Finance depuis l'ISIN."""
    if isin in _auto_ticker_cache:
        return _auto_ticker_cache[isin]
    try:
        # yfinance accepte parfois directement les ISIN comme ticker
        t = yf.Ticker(isin)
        info = t.fast_info
        price = info.get("last_price") or info.get("regularMarketPrice")
        if price and price > 0:
            _auto_ticker_cache[isin] = isin
            return isin
    except Exception:
        pass
    _auto_ticker_cache[isin] = None
    return None


def get_current_price(isin: str) -> float | None:
    ticker = ISIN_TO_TICKER.get(isin) or _find_ticker_auto(isin)
    if not ticker:
        return None
    try:
        t = yf.Ticker(ticker)
        return t.fast_info["last_price"]
    except Exception:
        return None


def get_prices_batch(isins: list[str]) -> dict[str, float | None]:
    return {isin: get_current_price(isin) for isin in isins}


def get_history(isin: str, start: str) -> list | None:
    """Retourne une liste de (date, prix_cloture) depuis start jusqu'a aujourd'hui."""
    ticker = ISIN_TO_TICKER.get(isin) or _find_ticker_auto(isin)
    if not ticker:
        return None
    try:
        hist = yf.Ticker(ticker).history(start=start, auto_adjust=False)
        if hist.empty:
            return None
        return list(zip(hist.index.date, hist["Close"].tolist()))
    except Exception:
        return None
