import yfinance as yf

# Mapping ISIN -> ticker Yahoo Finance (overrides manuels, priorité sur le cache DB).
# Utiliser pour corriger les cas où l'auto-détection se trompe.
ISIN_TO_TICKER: dict[str, str] = {
    "LU1681043599": "CW8.PA",    # Amundi MSCI World Swap UCITS ETF EUR ACC
    "IE0002XZSHO1": "IE0002XZSHO1",  # iShares MSCI World Swap PEA UCITS ETF (WPEA.PA hors service, ISIN direct fonctionne)
    "FR0000120271": "TTE.PA",    # TOTALENERGIES SE
    "FR0000125486": "DG.PA",     # VINCI
    "FR0000120503": "EN.PA",     # BOUYGUES
    "FR0000120073": "AI.PA",     # AIR LIQUIDE
    "FR0013258662": "AYV.PA",    # ALD (fusionné dans Ayvens, ALD.PA hors service)
    "FR0000131104": "BNP.PA",    # BNP PARIBAS
    "FR0011950732": "ELIOR.PA",  # ELIOR GROUP
    "FR0010112524": "NXI.PA",    # NEXITY
    "FR0000130809": "GLE.PA",    # SOCIETE GENERALE
    "NL00150001Q9": "STLAM.MI",  # STELLANTIS (STLAM.PA hors service → Milan EUR)
    "NL0000226223": "STM.DE",    # STMICROELECTRONICS (STM.PA hors service → Xetra EUR)
    "FR0000124141": "VIE.PA",    # VEOLIA ENVIRONNEMENT
    "FR0000121667": "EL.PA",     # ESSILORLUXOTTICA
    "TUDI_FAIR_2": "",           # Non coté — ticker vide pour skip yfinance, valorisé au coût
}

_EUR_SUFFIXES = (".PA", ".AS", ".BR", ".LS", ".MC", ".MI", ".DE", ".F", ".VI")


def load_cache(db) -> None:
    """Charge le cache DB dans ISIN_TO_TICKER (les overrides manuels gardent priorité)."""
    for isin, ticker in db.get_all_cached_tickers().items():
        ISIN_TO_TICKER.setdefault(isin, ticker)


def _ticker_has_price(ticker: str) -> bool:
    try:
        t = yf.Ticker(ticker)
        if t.fast_info.get("last_price"):
            return True
        hist = t.history(period="5d", auto_adjust=False)
        return not hist.empty
    except Exception:
        return False


def _search_ticker(valeur: str) -> str | None:
    if not valeur:
        return None
    try:
        results = yf.Search(valeur, max_results=10).quotes or []
    except Exception:
        return None
    # 1. Priorité Euronext Paris (PEA-éligible)
    for r in results:
        sym = r.get("symbol", "")
        if sym.endswith(".PA"):
            return sym
    # 2. Fallback : autre place européenne EUR
    for r in results:
        sym = r.get("symbol", "")
        if any(sym.endswith(s) for s in _EUR_SUFFIXES):
            return sym
    return None


def discover_ticker(isin: str, valeur: str | None) -> str | None:
    """Tente de résoudre un ticker yfinance pour un ISIN. Stratégie hybride :
    1. Ticker(ISIN) direct (marche pour certains ETF)
    2. yf.Search par nom de valeur, priorité .PA
    """
    if isin and _ticker_has_price(isin):
        return isin
    if valeur:
        return _search_ticker(valeur)
    return None


def discover_and_cache(isin: str, valeur: str | None, db) -> str | None:
    """Résout un ticker et le persiste en DB. Renvoie None si rien trouvé."""
    if isin in ISIN_TO_TICKER:
        return ISIN_TO_TICKER[isin]
    ticker = discover_ticker(isin, valeur)
    if ticker:
        ISIN_TO_TICKER[isin] = ticker
        db.set_cached_ticker(isin, ticker)
    return ticker


def get_current_price(isin: str) -> float | None:
    ticker = ISIN_TO_TICKER.get(isin)
    if not ticker:
        return None
    try:
        t = yf.Ticker(ticker)
        price = t.fast_info.get("last_price")
        if price:
            return price
        # Fallback : dernier close de l'historique récent (ex: ISIN direct)
        hist = t.history(period="5d", auto_adjust=False)
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
        return None
    except Exception:
        return None


def get_prices_batch(isins: list[str]) -> dict[str, float | None]:
    return {isin: get_current_price(isin) for isin in isins}


def get_history(isin: str, start: str) -> list | None:
    """Retourne une liste de (date, prix_cloture) depuis start jusqu'a aujourd'hui."""
    ticker = ISIN_TO_TICKER.get(isin)
    if not ticker:
        return None
    try:
        hist = yf.Ticker(ticker).history(start=start, auto_adjust=False)
        if hist.empty:
            return None
        return list(zip(hist.index.date, hist["Close"].tolist()))
    except Exception:
        return None
