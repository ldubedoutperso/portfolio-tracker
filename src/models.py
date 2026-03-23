from dataclasses import dataclass
from datetime import date


@dataclass
class Operation:
    date_op: date
    op_type: str
    valeur: str
    isin: str
    montant: float
    quantite: float
    source_file: str | None = None


@dataclass
class Position:
    valeur: str
    isin: str
    quantity: float
    cmp: float
    total_dividends: float
    current_dividends: float
    open_date: date
    partial_pv: float
    partial_pv_entries: list  # list of (date, float) — one entry per partial vente

    @property
    def cost(self) -> float:
        return self.cmp * self.quantity

    @property
    def net_cost(self) -> float:
        return self.cost - self.current_dividends

    @property
    def pru_after_div(self) -> float:
        return self.net_cost / self.quantity if self.quantity > 0 else 0.0


@dataclass
class Cycle:
    valeur: str
    isin: str
    open_date: date
    close_date: date
    realized_pv: float
    dividends: float

    @property
    def net_result(self) -> float:
        return self.realized_pv + self.dividends
