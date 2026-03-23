from collections import defaultdict

from src.models import Cycle, Operation, Position


def calculate_portfolio(
    operations: list[Operation],
) -> tuple[list[Position], list[Cycle]]:
    """
    Parcourt les opérations chronologiquement par valeur.
    Retourne les positions actuelles et les cycles soldés.

    Base de calcul : ABS(montant) — frais de courtage inclus.
    """
    by_valeur: dict[str, list[Operation]] = defaultdict(list)

    def sort_key(op: Operation):
        # Même jour : ACHAT (0) avant COUPONS (1) avant VENTE (2)
        if op.op_type.startswith("ACHAT"):
            type_order = 0
        elif op.op_type == "COUPONS":
            type_order = 1
        else:
            type_order = 2
        return (op.date_op, type_order)

    for op in sorted(operations, key=sort_key):
        if op.op_type.startswith(("ACHAT", "VENTE", "COUPONS")):
            by_valeur[op.valeur].append(op)

    positions_actuelles: list[Position] = []
    cycles_soldes: list[Cycle] = []

    for valeur, ops in by_valeur.items():
        qty = 0.0
        stock = 0.0
        cmp = 0.0

        cycle_open_date = None
        cycle_pv = 0.0
        cycle_divs = 0.0
        total_divs = 0.0
        partial_entries: list = []  # (date, pv) for each partial vente on open position
        last_isin = ops[0].isin

        for op in ops:
            last_isin = op.isin

            if op.op_type.startswith("ACHAT"):
                cost = abs(op.montant)
                stock += cost
                qty += op.quantite
                cmp = stock / qty
                if cycle_open_date is None:
                    cycle_open_date = op.date_op

            elif op.op_type.startswith("VENTE"):
                pv = op.montant - (cmp * op.quantite)
                cycle_pv += pv
                stock -= cmp * op.quantite
                qty -= op.quantite

                if abs(qty) < 0.001:  # Position entierement soldee
                    cycles_soldes.append(
                        Cycle(
                            valeur=valeur,
                            isin=op.isin,
                            open_date=cycle_open_date,
                            close_date=op.date_op,
                            realized_pv=cycle_pv,
                            dividends=cycle_divs,
                        )
                    )
                    qty = 0.0
                    stock = 0.0
                    cmp = 0.0
                    cycle_open_date = None
                    cycle_pv = 0.0
                    cycle_divs = 0.0
                    partial_entries = []
                else:
                    # Vente partielle : on enregistre la date et la PV
                    partial_entries.append((op.date_op, pv))

            elif op.op_type == "COUPONS":
                total_divs += op.montant
                cycle_divs += op.montant

        if qty > 0.001:
            positions_actuelles.append(
                Position(
                    valeur=valeur,
                    isin=last_isin,
                    quantity=qty,
                    cmp=cmp,
                    total_dividends=total_divs,
                    current_dividends=cycle_divs,
                    open_date=cycle_open_date,
                    partial_pv=cycle_pv,
                    partial_pv_entries=partial_entries,
                )
            )

    return positions_actuelles, cycles_soldes
