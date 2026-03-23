from collections import namedtuple
from datetime import date

import pytest

from src.calculator import calculate_portfolio
from src.models import Operation

Portfolio = namedtuple("Portfolio", ["positions", "cycles"])


def make_op(date_op, op_type, valeur, isin, montant, quantite):
    return Operation(
        date_op=date_op,
        op_type=op_type,
        valeur=valeur,
        isin=isin,
        montant=montant,
        quantite=quantite,
    )


# Opérations de test construites pour produire les valeurs de référence de la spec.
#
# Positions ouvertes :
#   AM.M.WOR.ETF EUR C  : qty=16,  cmp=513.95          (8223.20 / 16)
#   TOTALENERGIES SE    : qty=37,  cmp=55.7715          (2063.5455 / 37)  + div 165.79
#   VINCI               : qty=7,   cmp=122.37           (856.59 / 7)      + div 6.30
#   ISHS VI-ISMWSPE EO  : qty=823, cmp=5.6497           (4649.7031 / 823)
#
# Cycles soldés :
#   AIR LIQUIDE    : 1 cycle  pv=3.24
#   STELLANTIS     : 3 cycles pv=13.94 + 5.00 + 19.00 = 37.94
#   NEXITY         : 2 cycles pv=10.14 + 50.14 = 60.28
#   BOUYGUES       : 1 cycle  pv=211.62  div=44.00
#   BNP PARIBAS    : 1 cycle  pv=7.59    div=9.20

TEST_OPERATIONS = [
    # --- Positions ouvertes ---
    # AM.M.WOR.ETF EUR C  (cmp = 8223.20 / 16 = 513.95)
    make_op(date(2020, 1, 15), "ACHAT COMPTANT", "AM.M.WOR.ETF EUR C", "LU1681043599", -8223.20, 16),
    # TOTALENERGIES SE  (cmp = 2063.5455 / 37 = 55.7715)
    make_op(date(2020, 2, 15), "ACHAT COMPTANT", "TOTALENERGIES SE", "FR0000120271", -2063.5455, 37),
    make_op(date(2021, 3, 15), "COUPONS", "TOTALENERGIES SE", "FR0000120271", 165.79, 0),
    # VINCI  (cmp = 856.59 / 7 = 122.37)
    make_op(date(2020, 3, 15), "ACHAT COMPTANT", "VINCI", "FR0000125486", -856.59, 7),
    make_op(date(2021, 4, 15), "COUPONS", "VINCI", "FR0000125486", 6.30, 0),
    # ISHS VI-ISMWSPE EO  (cmp = 4649.7031 / 823 = 5.6497)
    make_op(date(2020, 4, 15), "ACHAT COMPTANT ETR", "ISHS VI-ISMWSPE EO", "IE0002XZSHO1", -4649.7031, 823),
    # --- Cycles soldés ---
    # AIR LIQUIDE  : buy 10 @ 100€, sell 10 @ 1003.24€  → pv = 3.24
    make_op(date(2019, 1, 15), "ACHAT COMPTANT", "AIR LIQUIDE", "FR0000120073", -1000.00, 10),
    make_op(date(2019, 6, 15), "VENTE COMPTANT", "AIR LIQUIDE", "FR0000120073", 1003.24, 10),
    # STELLANTIS cycle 1 : buy 5 @ 10€, sell 5 @ 63.94€  → pv = 13.94
    make_op(date(2018, 1, 15), "ACHAT COMPTANT", "STELLANTIS", "NL00150001Q9", -50.00, 5),
    make_op(date(2018, 6, 15), "VENTE COMPTANT", "STELLANTIS", "NL00150001Q9", 63.94, 5),
    # STELLANTIS cycle 2 : buy 5 @ 10€, sell 5 @ 55.00€  → pv = 5.00
    make_op(date(2019, 1, 15), "ACHAT COMPTANT", "STELLANTIS", "NL00150001Q9", -50.00, 5),
    make_op(date(2019, 6, 15), "VENTE COMPTANT", "STELLANTIS", "NL00150001Q9", 55.00, 5),
    # STELLANTIS cycle 3 : buy 5 @ 10€, sell 5 @ 69.00€  → pv = 19.00
    make_op(date(2020, 1, 15), "ACHAT COMPTANT", "STELLANTIS", "NL00150001Q9", -50.00, 5),
    make_op(date(2020, 6, 15), "VENTE COMPTANT", "STELLANTIS", "NL00150001Q9", 69.00, 5),
    # NEXITY cycle 1 : buy 3 @ 100€, sell 3 @ 310.14€  → pv = 10.14
    make_op(date(2018, 1, 15), "ACHAT COMPTANT", "NEXITY", "FR0010112524", -300.00, 3),
    make_op(date(2018, 7, 15), "VENTE COMPTANT", "NEXITY", "FR0010112524", 310.14, 3),
    # NEXITY cycle 2 : buy 3 @ 100€, sell 3 @ 350.14€  → pv = 50.14
    make_op(date(2019, 1, 15), "ACHAT COMPTANT", "NEXITY", "FR0010112524", -300.00, 3),
    make_op(date(2019, 7, 15), "VENTE COMPTANT", "NEXITY", "FR0010112524", 350.14, 3),
    # BOUYGUES : buy 10 @ 100€, div 44€, sell 10 @ 1211.62€  → pv=211.62, div=44.00
    make_op(date(2018, 1, 15), "ACHAT COMPTANT", "BOUYGUES", "FR0000120503", -1000.00, 10),
    make_op(date(2018, 5, 15), "COUPONS", "BOUYGUES", "FR0000120503", 44.00, 0),
    make_op(date(2018, 12, 15), "VENTE COMPTANT", "BOUYGUES", "FR0000120503", 1211.62, 10),
    # BNP PARIBAS : buy 5 @ 20€, div 9.20€, sell 5 @ 107.59€  → pv=7.59, div=9.20
    make_op(date(2018, 1, 15), "ACHAT COMPTANT", "BNP PARIBAS", "FR0000131104", -100.00, 5),
    make_op(date(2018, 6, 15), "COUPONS", "BNP PARIBAS", "FR0000131104", 9.20, 0),
    make_op(date(2018, 11, 15), "VENTE COMPTANT", "BNP PARIBAS", "FR0000131104", 107.59, 5),
]


@pytest.fixture
def portfolio():
    positions, cycles = calculate_portfolio(TEST_OPERATIONS)
    return Portfolio(positions=positions, cycles=cycles)
