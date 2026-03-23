import yfinance as yf

# Mapping ISIN -> ticker Yahoo Finance
# Note : certains tickers ETF luxembourgeois/irlandais sont non-standards,
# à compléter/corriger au fur et à mesure.
ISIN_TO_TICKER: dict[str, str] = {
    "LU1681043599": "CW8.PA",    # Amundi MSCI World Swap UCITS ETF EUR ACC
    "IE0002XZSHO1": "WPEA.PA",   # iShares MSCI World Swap PEA UCITS ETF EUR ACC
    "FR0000120271": "TTE.PA",    # TOTALENERGIES SE
    "FR0000125486": "DG.PA",     # VINCI
    "FR0000120503": "EN.PA",     # BOUYGUES
    "FR0000120073": "AI.PA",     # AIR LIQUIDE
    "FR0013258662": "ALD.PA",    # ALD
    "FR0000131104": "BNP.PA",    # BNP PARIBAS
    "FR0011950732": "ELIOR.PA",  # ELIOR GROUP
    "FR0010112524": "NXI.PA",    # NEXITY
    "FR0000130809": "GLE.PA",    # SOCIETE GENERALE
    "NL00150001Q9": "STLAM.PA",  # STELLANTIS
    "NL0000226223": "STM.PA",    # STMICROELECTRONICS
}


def get_current_price(isin: str) -> float | None:
    ticker = ISIN_TO_TICKER.get(isin)
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
