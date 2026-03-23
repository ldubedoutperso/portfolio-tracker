import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.db import Database
from src.models import Operation


def _parse_number(s: str) -> float:
    """
    Parse un nombre en format Boursorama (locale française ou anglaise).
    Gère : '-1 234,56', '-126,37', '-126.37', '44', '1\xa0234,56'.
    """
    s = s.strip()
    # Supprimer le symbole euro et les espaces insécables
    s = s.replace("€", "").replace("\xa0", "").replace("\u202f", "").strip()
    if "," in s:
        # Format français : la virgule est le séparateur décimal
        s = s.replace(" ", "").replace(",", ".")
    else:
        # Format anglo-saxon ou entier : supprimer les espaces milliers
        s = s.replace(" ", "")
    return float(s)


def import_csv(filepath: str, db: Database) -> tuple[int, int]:
    """
    Importe un fichier CSV Boursorama dans la base.
    Retourne (nb_importees, nb_doublons_ignores).
    """
    df = pd.read_csv(filepath, sep=";", encoding="utf-8-sig", dtype=str)

    inserted = 0
    duplicates = 0

    for _, row in df.iterrows():
        isin = str(row.get("Code ISIN", "")).strip()
        valeur = str(row.get("Valeur", "")).strip()
        op_type = str(row.get("Opération", "")).strip()

        # Normaliser les champs vides
        if isin == "nan":
            isin = ""
        if valeur == "nan":
            valeur = ""

        # Ignorer les lignes sans type d'opération (lignes vides du CSV)
        if not op_type or op_type == "nan":
            continue

        # Date
        date_str = str(row.get("Date opération", "")).strip()
        try:
            date_op = datetime.strptime(date_str, "%d/%m/%Y").date()
        except ValueError:
            continue

        # Montant
        montant_str = str(row.get("Montant", "0")).strip()
        try:
            montant = _parse_number(montant_str) if montant_str and montant_str != "nan" else 0.0
        except ValueError:
            continue

        # Quantité (0 pour les dividendes)
        qty_str = str(row.get("Quantité", "0")).strip()
        try:
            quantite = _parse_number(qty_str) if qty_str and qty_str != "nan" else 0.0
        except ValueError:
            quantite = 0.0

        op = Operation(
            date_op=date_op,
            op_type=op_type,
            valeur=valeur,
            isin=isin,
            montant=montant,
            quantite=quantite,
            source_file=Path(filepath).name,
        )

        if db.insert_operation(op):
            inserted += 1
        else:
            duplicates += 1

    return inserted, duplicates


def process_inbox(inbox_dir: str, db: Database) -> list[dict]:
    """
    Scanne data/inbox/, importe chaque .csv, déplace vers processed/.
    Retourne la liste des résultats par fichier.
    """
    inbox = Path(inbox_dir)
    processed_dir = inbox / "processed"
    processed_dir.mkdir(exist_ok=True)

    results = []
    for csv_file in sorted(inbox.glob("*.csv")):
        # Ignorer les fichiers déjà archivés (copie présente dans processed/)
        if (processed_dir / csv_file.name).exists():
            continue
        imported, duplicates = import_csv(str(csv_file), db)
        results.append(
            {
                "file": csv_file.name,
                "imported": imported,
                "duplicates": duplicates,
            }
        )
        # Copie vers processed/ pour archivage.
        # On ne supprime pas l'original (peut être verrouillé par OneDrive).
        # La contrainte UNIQUE en base garantit qu'un re-import sera ignoré.
        dest = processed_dir / csv_file.name
        shutil.copy2(str(csv_file), str(dest))

    return results
