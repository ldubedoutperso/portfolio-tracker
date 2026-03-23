# Portfolio PEA Tracker

Application locale de suivi d'un PEA Boursorama.

## Installation

### Prérequis
- Python 3.10 ou supérieur

### Windows
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### macOS / Linux
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Lancement

```
streamlit run src/app.py
```

L'application s'ouvre automatiquement dans le navigateur sur http://localhost:8501

## Premier import

1. Exporter l'onglet Mouvements de Bourse.xlsx en CSV (séparateur `;`, encodage UTF-8)
2. Placer le fichier dans `data/inbox/`
3. Lancer l'application et cliquer sur "Verifier inbox"

## Mises à jour

1. Télécharger l'export CSV depuis Boursorama
2. Placer le fichier dans `data/inbox/`
3. Cliquer sur "Verifier inbox" — les doublons sont automatiquement ignorés

## Structure

```
portfolio-tracker/
├── src/
│   ├── models.py       # Dataclasses Operation, Position, Cycle
│   ├── db.py           # Accès SQLite
│   ├── importer.py     # Import CSV (initial + incrémental)
│   ├── calculator.py   # Algorithme CMP itératif
│   ├── quotes.py       # Cours temps réel via yfinance
│   └── app.py          # Application Streamlit
├── data/
│   ├── portfolio.db    # Base SQLite (créée automatiquement)
│   └── inbox/          # Dossier de dépôt des nouveaux CSV
├── tests/
│   ├── conftest.py     # Fixtures pytest
│   └── test_calculator.py
└── requirements.txt
```

## Tests

```
pytest tests/
```

## Format CSV Boursorama

- Séparateur : `;`
- Encodage : UTF-8 BOM
- En-tête : `"Date opération";"Date valeur";Opération;Valeur;"Code ISIN";Montant;Quantité;Cours`
