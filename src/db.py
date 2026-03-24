import sqlite3
from datetime import date
from pathlib import Path

from src.models import Operation


class Database:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()

    def create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_op DATE NOT NULL,
                op_type TEXT NOT NULL,
                valeur TEXT NOT NULL,
                isin TEXT NOT NULL,
                montant REAL NOT NULL,
                quantite REAL NOT NULL,
                source_file TEXT,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date_op, isin, montant, quantite)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        self.conn.commit()

    def delete_setting(self, key: str) -> None:
        self.conn.execute("DELETE FROM settings WHERE key = ?", (key,))
        self.conn.commit()

    def insert_operation(self, op: Operation) -> bool:
        cursor = self.conn.execute(
            """INSERT OR IGNORE INTO operations
               (date_op, op_type, valeur, isin, montant, quantite, source_file)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                op.date_op.isoformat(),
                op.op_type,
                op.valeur,
                op.isin,
                op.montant,
                op.quantite,
                op.source_file,
            ),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def get_all_operations(self) -> list[Operation]:
        rows = self.conn.execute(
            "SELECT * FROM operations ORDER BY date_op ASC, id ASC"
        ).fetchall()
        return [
            Operation(
                date_op=date.fromisoformat(row["date_op"]),
                op_type=row["op_type"],
                valeur=row["valeur"],
                isin=row["isin"],
                montant=row["montant"],
                quantite=row["quantite"],
                source_file=row["source_file"],
            )
            for row in rows
        ]

    def get_operation_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM operations").fetchone()[0]

    def get_last_import(self) -> str | None:
        row = self.conn.execute(
            "SELECT MAX(datetime(imported_at, 'localtime')) FROM operations"
        ).fetchone()
        return row[0] if row else None
