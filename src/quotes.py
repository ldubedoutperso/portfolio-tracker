import yfinance as yf

# Mapping ISIN -> ticker Yahoo Finance
# Note : certains tickers ETF luxembourgeois/irlandais sont non-standards,
# à compléter/corriger au fur et à mesure.
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
}


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
