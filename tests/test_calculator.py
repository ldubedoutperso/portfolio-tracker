import pytest


def test_positions_actuelles(portfolio):
    pos = {p.valeur: p for p in portfolio.positions}

    # AM.M.WOR.ETF EUR C
    assert pos["AM.M.WOR.ETF EUR C"].quantity == 16
    assert pos["AM.M.WOR.ETF EUR C"].cmp == pytest.approx(513.95, abs=0.01)
    assert pos["AM.M.WOR.ETF EUR C"].current_dividends == pytest.approx(0.0, abs=0.01)

    # TOTALENERGIES SE
    assert pos["TOTALENERGIES SE"].quantity == 37
    assert pos["TOTALENERGIES SE"].cmp == pytest.approx(55.7715, abs=0.001)
    assert pos["TOTALENERGIES SE"].current_dividends == pytest.approx(165.79, abs=0.01)

    # VINCI
    assert pos["VINCI"].quantity == 7
    assert pos["VINCI"].cmp == pytest.approx(122.37, abs=0.01)
    assert pos["VINCI"].current_dividends == pytest.approx(6.30, abs=0.01)

    # ISHS VI-ISMWSPE EO
    assert pos["ISHS VI-ISMWSPE EO"].quantity == 823
    assert pos["ISHS VI-ISMWSPE EO"].cmp == pytest.approx(5.6497, abs=0.001)


def test_cycles_soldes(portfolio):
    cycles = portfolio.cycles

    # AIR LIQUIDE — 1 cycle
    al = [c for c in cycles if c.valeur == "AIR LIQUIDE"]
    assert len(al) == 1
    assert al[0].realized_pv == pytest.approx(3.24, abs=0.01)

    # STELLANTIS — 3 cycles
    st = [c for c in cycles if c.valeur == "STELLANTIS"]
    assert len(st) == 3
    assert sum(c.realized_pv for c in st) == pytest.approx(37.94, abs=0.01)

    # NEXITY — 2 cycles
    nx = [c for c in cycles if c.valeur == "NEXITY"]
    assert len(nx) == 2
    assert sum(c.realized_pv for c in nx) == pytest.approx(60.28, abs=0.01)

    # BOUYGUES — 1 cycle
    bo = [c for c in cycles if c.valeur == "BOUYGUES"]
    assert len(bo) == 1
    assert bo[0].realized_pv == pytest.approx(211.62, abs=0.01)
    assert bo[0].dividends == pytest.approx(44.00, abs=0.01)

    # BNP PARIBAS — 1 cycle
    bnp = [c for c in cycles if c.valeur == "BNP PARIBAS"]
    assert len(bnp) == 1
    assert bnp[0].realized_pv == pytest.approx(7.59, abs=0.01)
    assert bnp[0].dividends == pytest.approx(9.20, abs=0.01)


def test_position_properties(portfolio):
    pos = {p.valeur: p for p in portfolio.positions}

    # TOTALENERGIES : cost = 37 * 55.7715, net_cost = cost - 165.79
    tte = pos["TOTALENERGIES SE"]
    assert tte.cost == pytest.approx(55.7715 * 37, abs=0.01)
    assert tte.net_cost == pytest.approx(tte.cost - 165.79, abs=0.01)
    assert tte.pru_after_div == pytest.approx(tte.net_cost / 37, abs=0.001)


def test_cycle_net_result(portfolio):
    cycles = portfolio.cycles

    bo = [c for c in cycles if c.valeur == "BOUYGUES"][0]
    assert bo.net_result == pytest.approx(211.62 + 44.00, abs=0.01)

    bnp = [c for c in cycles if c.valeur == "BNP PARIBAS"][0]
    assert bnp.net_result == pytest.approx(7.59 + 9.20, abs=0.01)


def test_achat_etr_traite_comme_achat(portfolio):
    """ACHAT COMPTANT ETR doit être traité identiquement à ACHAT COMPTANT."""
    pos = {p.valeur: p for p in portfolio.positions}
    assert "ISHS VI-ISMWSPE EO" in pos
    assert pos["ISHS VI-ISMWSPE EO"].quantity == 823
