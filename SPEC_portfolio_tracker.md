# Spec — Portfolio PEA Tracker

## Contexte

Application locale de suivi d'un PEA Boursorama.  
Langage : **Python 3.10+**  
Interface : **Streamlit** (web locale, navigateur)  
Stockage : **SQLite** (`data/portfolio.db`)  
Cross-platform : Windows / macOS / Linux

---

## Structure des fichiers

```
portfolio-tracker/
├── src/
│   ├── importer.py          # Import CSV (initial + incrémental)
│   ├── calculator.py        # Algorithme CMP itératif
│   ├── models.py            # Dataclasses Operation, Position, Cycle
│   ├── db.py                # Accès SQLite
│   ├── quotes.py            # Cours temps réel via yfinance
│   └── app.py               # Application Streamlit
├── data/
│   ├── portfolio.db         # Base SQLite (créée automatiquement)
│   └── inbox/               # Dossier de dépôt des nouveaux CSV Boursorama
├── tests/
│   └── test_calculator.py   # Tests de validation CMP
├── requirements.txt
└── README.md
```

---

## Source de données

### Format CSV unique (source de vérité)

Tous les imports utilisent le **même format CSV Boursorama** :
- Séparateur : point-virgule (`;`)
- Encodage : UTF-8 BOM (`utf-8-sig`)
- Dates : `dd/mm/yyyy`
- Cours : `"62,87 €"` (virgule décimale + symbole euro, entre guillemets)
- Montant : nombre décimal avec point (`-126.37`)

**En-tête :**
```
"Date opération";"Date valeur";Opération;Valeur;"Code ISIN";Montant;Quantité;Cours
```

**La base initiale** est constituée en copiant-collant l'onglet Mouvements de l'Excel en CSV avec ce format.  
**Les mises à jour** se font en déposant de nouveaux CSV Boursorama dans `data/inbox/`.

### Colonnes utilisées

| Colonne | Contenu | Utilisé |
|---|---|---|
| Date opération | Date de l'opération | ✅ |
| Date valeur | Date de valeur | ❌ ignoré |
| Opération | Type d'opération | ✅ |
| Valeur | Nom de la valeur | ✅ |
| Code ISIN | ISIN | ✅ |
| Montant | Montant en € (négatif = débit) | ✅ |
| Quantité | Nombre de titres | ✅ |
| Cours | Cours unitaire | ❌ ignoré (recalculé) |

### Types d'opérations

| Type (préfixe) | Traitement |
|---|---|
| `ACHAT COMPTANT` | Achat — montant négatif |
| `ACHAT COMPTANT ETR` | Achat ETF étranger — montant négatif |
| `VENTE COMPTANT` | Vente — montant positif |
| `COUPONS` | Dividende — montant positif |
| `VIR...` | Virement — **ignoré** pour le calcul portefeuille |
| `FRAIS...`, `*RETROC...`, `*FRAIS...` | Frais divers — **ignorés** |

---

## Base de données SQLite

### Table `operations`

```sql
CREATE TABLE operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_op DATE NOT NULL,
    op_type TEXT NOT NULL,
    valeur TEXT NOT NULL,
    isin TEXT NOT NULL,
    montant REAL NOT NULL,
    quantite REAL NOT NULL,
    source_file TEXT,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date_op, isin, montant, quantite)  -- clé de déduplication
);
```

---

## Algorithme CMP itératif (CRITIQUE)

**Base de calcul : `ABS(montant)` — frais de courtage inclus.** C'est la méthode officielle Boursorama, validée sur les données réelles.

```python
def calculate_portfolio(operations: list[Operation]) -> tuple[list[Position], list[Cycle]]:
    """
    Parcourt les opérations chronologiquement par valeur.
    Retourne les positions actuelles et les cycles soldés.
    """
    # Grouper par valeur, trier par date
    by_valeur = defaultdict(list)
    for op in sorted(operations, key=lambda x: x.date_op):
        if op.op_type.startswith(('ACHAT', 'VENTE', 'COUPONS')):
            by_valeur[op.valeur].append(op)

    positions_actuelles = []
    cycles_soldes = []

    for valeur, ops in by_valeur.items():
        # État courant
        qty = 0.0
        stock = 0.0   # valeur stock au CMP
        cmp = 0.0

        # Cycle en cours
        cycle_open_date = None
        cycle_pv = 0.0
        cycle_divs = 0.0
        total_divs = 0.0

        for op in ops:
            if op.op_type.startswith('ACHAT'):
                cost = abs(op.montant)
                stock += cost
                qty += op.quantite
                cmp = stock / qty
                if cycle_open_date is None:
                    cycle_open_date = op.date_op

            elif op.op_type.startswith('VENTE'):
                pv = op.montant - (cmp * op.quantite)
                cycle_pv += pv
                stock -= cmp * op.quantite
                qty -= op.quantite

                if abs(qty) < 0.001:  # Position soldée
                    cycles_soldes.append(Cycle(
                        valeur=valeur,
                        isin=op.isin,
                        open_date=cycle_open_date,
                        close_date=op.date_op,
                        realized_pv=cycle_pv,
                        dividends=cycle_divs,
                    ))
                    # Reset pour prochain cycle
                    qty = 0.0
                    stock = 0.0
                    cmp = 0.0
                    cycle_open_date = None
                    cycle_pv = 0.0
                    cycle_divs = 0.0

            elif op.op_type == 'COUPONS':
                # Ne modifie PAS le CMP
                total_divs += op.montant
                cycle_divs += op.montant

        # Position actuelle (qty > 0)
        if qty > 0.001:
            positions_actuelles.append(Position(
                valeur=valeur,
                isin=op.isin,
                quantity=qty,
                cmp=cmp,
                total_dividends=total_divs,
                current_dividends=cycle_divs,
                open_date=cycle_open_date,
                partial_pv=cycle_pv,
            ))

    return positions_actuelles, cycles_soldes
```

---

## Métriques calculées

### Positions actuelles

| Métrique | Calcul |
|---|---|
| Quantité | `qty` |
| PRU (CMP) | `cmp` |
| Coût position | `cmp × qty` |
| Dividendes totaux | Tous les COUPONS sur cette valeur |
| Dividendes position actuelle | COUPONS depuis le dernier passage à qty=0 |
| PRU après dividendes | `(coût - div_actuels) / qty` |
| Coût net | `coût - div_actuels` |
| PV ventes partielles | PV des ventes partielles du cycle actuel |
| Cours actuel | Yahoo Finance (via `yfinance`) |
| PV latente | `(cours_actuel - cmp) × qty` |
| PV latente % | `(cours_actuel / cmp - 1) × 100` |

### Positions soldées (par cycle)

| Métrique | Calcul |
|---|---|
| Date ouverture | Premier achat du cycle |
| Date clôture | Dernière vente du cycle |
| PV réalisée | `Σ(produit_vente - cmp×qty)` sur les ventes du cycle |
| Dividendes | COUPONS reçus pendant le cycle |
| Résultat net | PV réalisée + Dividendes |

---

## Récupération des cours (Yahoo Finance)

```python
import yfinance as yf

# Mapping ISIN → ticker Yahoo Finance
ISIN_TO_TICKER = {
    'LU1681043599': 'AMUNDI-MSCI-WORLD',   # AM.M.WOR.ETF EUR C
    'IE0002XZSHO1': 'ISHS-MSCI-WORLD',     # ISHS VI-ISMWSPE EO
    'FR0000120271': 'TTE.PA',               # TOTALENERGIES SE
    'FR0000125486': 'DG.PA',                # VINCI
    # À compléter au fur et à mesure
}

def get_current_price(isin: str) -> float | None:
    ticker = ISIN_TO_TICKER.get(isin)
    if not ticker:
        return None
    try:
        t = yf.Ticker(ticker)
        return t.fast_info['last_price']
    except:
        return None
```

**Note :** Le mapping ISIN→ticker doit être maintenu manuellement ou via une recherche automatique. Prévoir un mécanisme de fallback (afficher `N/A` si cours non disponible) sans bloquer l'affichage.

---

## Import CSV

### Import initial

```python
def import_csv(filepath: str, db: Database) -> tuple[int, int]:
    """
    Retourne (nb_importées, nb_doublons_ignorés)
    """
```

- Parser le CSV (UTF-8 BOM, séparateur `;`)
- Pour chaque ligne, nettoyer :
  - Date : `dd/mm/yyyy` → `datetime`
  - Montant : float (déjà avec point décimal)
  - Quantité : float
- Filtrer les opérations sans Valeur/ISIN (virements, frais)
- Insérer avec `INSERT OR IGNORE` (déduplication via contrainte UNIQUE)

### Import incrémental (dossier inbox)

Au démarrage de l'application, scanner `data/inbox/` :
- Pour chaque fichier `.csv` non encore traité
- Importer avec déduplication
- Déplacer vers `data/inbox/processed/` après import réussi
- Afficher un résumé : "X nouvelles opérations importées depuis fichier.csv"

### Clé de déduplication

```
(date_op, isin, montant, quantite)
```

---

## Interface Streamlit — Pages

### Page 1 : Positions actuelles

Tableau avec colonnes :
- Valeur, ISIN
- Quantité
- PRU (CMP)
- Coût position
- Cours actuel (Yahoo Finance, avec indicateur de fraîcheur)
- PV latente (€)
- PV latente (%)
- Dividendes totaux
- Dividendes position actuelle
- PRU après dividendes
- PV ventes partielles

Tri par défaut : PV latente décroissante.  
Afficher en bas : **Total coût portefeuille**, **Total PV latente**.

### Page 2 : Positions soldées

Tableau avec colonnes :
- Valeur
- Date ouverture cycle
- Date clôture cycle
- PV réalisée (€)
- Dividendes (€)
- Résultat net (€)

Une ligne par cycle (ex : STELLANTIS apparaît 3 fois, NEXITY 2 fois).  
Tri par défaut : date clôture décroissante.  
Afficher en bas : **Total PV réalisée**, **Total dividendes**, **Total net**.

### Page 3 : Synthèse

KPIs affichés en cards :
- Solde espèces (= somme de tous les montants incluant virements)
- PV réalisée totale
- PV réalisée par année (tableau : Année / PV)
- PV latente actuelle (temps réel)
- **PV totale si sortie** = PV réalisée + PV latente
- Total dividendes perçus

### Page 4 : Mouvements

Tableau de l'historique brut, lecture seule.  
Filtres : par valeur, par type d'opération, par période.

### Sidebar (toutes pages)

- Bouton **"Vérifier inbox"** : scanner et importer les nouveaux CSV
- Indicateur : dernière mise à jour des cours
- Indicateur : nombre d'opérations en base

---

## Valeurs de référence pour les tests

Ces valeurs sont **validées** par comparaison avec Boursorama et l'algorithme Python testé sur les données réelles.

```python
# tests/test_calculator.py

def test_positions_actuelles(portfolio):
    pos = {p.valeur: p for p in portfolio.positions}

    # AM.M.WOR.ETF EUR C
    assert pos['AM.M.WOR.ETF EUR C'].quantity == 16
    assert pos['AM.M.WOR.ETF EUR C'].cmp == pytest.approx(513.95, abs=0.01)
    assert pos['AM.M.WOR.ETF EUR C'].current_dividends == pytest.approx(0.0, abs=0.01)

    # TOTALENERGIES SE
    assert pos['TOTALENERGIES SE'].quantity == 37
    assert pos['TOTALENERGIES SE'].cmp == pytest.approx(55.7715, abs=0.001)
    assert pos['TOTALENERGIES SE'].current_dividends == pytest.approx(165.79, abs=0.01)

    # VINCI
    assert pos['VINCI'].quantity == 7
    assert pos['VINCI'].cmp == pytest.approx(122.37, abs=0.01)
    assert pos['VINCI'].current_dividends == pytest.approx(6.30, abs=0.01)

    # ISHS VI-ISMWSPE EO
    assert pos['ISHS VI-ISMWSPE EO'].quantity == 823
    assert pos['ISHS VI-ISMWSPE EO'].cmp == pytest.approx(5.6497, abs=0.001)


def test_cycles_soldes(portfolio):
    cycles = portfolio.cycles

    # AIR LIQUIDE — 1 cycle
    al = [c for c in cycles if c.valeur == 'AIR LIQUIDE']
    assert len(al) == 1
    assert al[0].realized_pv == pytest.approx(3.24, abs=0.01)

    # STELLANTIS — 3 cycles
    st = [c for c in cycles if c.valeur == 'STELLANTIS']
    assert len(st) == 3
    assert sum(c.realized_pv for c in st) == pytest.approx(37.94, abs=0.01)

    # NEXITY — 2 cycles
    nx = [c for c in cycles if c.valeur == 'NEXITY']
    assert len(nx) == 2
    assert sum(c.realized_pv for c in nx) == pytest.approx(60.28, abs=0.01)

    # BOUYGUES — 1 cycle
    bo = [c for c in cycles if c.valeur == 'BOUYGUES']
    assert len(bo) == 1
    assert bo[0].realized_pv == pytest.approx(211.62, abs=0.01)
    assert bo[0].dividends == pytest.approx(44.00, abs=0.01)

    # BNP PARIBAS — 1 cycle
    bnp = [c for c in cycles if c.valeur == 'BNP PARIBAS']
    assert len(bnp) == 1
    assert bnp[0].realized_pv == pytest.approx(7.59, abs=0.01)
    assert bnp[0].dividends == pytest.approx(9.20, abs=0.01)
```

---

## README — Installation

```markdown
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
3. Lancer l'application et cliquer sur "Vérifier inbox"

## Mises à jour

1. Télécharger l'export CSV depuis Boursorama
2. Placer le fichier dans `data/inbox/`
3. Cliquer sur "Vérifier inbox" — les doublons sont automatiquement ignorés
```

---

## requirements.txt

```
streamlit>=1.32.0
pandas>=2.0.0
openpyxl>=3.1.0
yfinance>=0.2.36
pytest>=8.0.0
```

---

## Points d'attention pour l'implémentation

1. **Tri chronologique strict** : l'algorithme CMP dépend de l'ordre des opérations. Toujours trier par `date_op` ASC avant le calcul.

2. **Même jour, ordre indéterminé** : si un achat et une vente ont la même date, traiter les achats en premier (convention prudente).

3. **Seuil de comparaison à zéro** : utiliser `abs(qty) < 0.001` et non `qty == 0` pour éviter les erreurs de floating point.

4. **Cours Yahoo Finance** : certains ETF irlandais/luxembourgeois ont des tickers non standards. Prévoir un fallback propre (afficher `—` sans crasher).

5. **ACHAT COMPTANT ETR** : traiter exactement comme `ACHAT COMPTANT` (même logique CMP).

6. **Virements négatifs** (ex : VIR TUDI HOLDING 84 = -1000€) : inclure dans le calcul du solde espèces mais **exclure** du calcul portefeuille actions.
