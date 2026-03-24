# Spec — Portfolio PEA Tracker

## Contexte

Application de suivi d'un PEA Boursorama, déployée sur Streamlit Cloud.
Langage : **Python 3.11+**
Interface : **Streamlit** (web, navigateur)
Stockage : **SQLite** (`data/portfolio.db`)
Déploiement : **Streamlit Community Cloud** — https://portfolio-tracker-perso.streamlit.app
Protection : mot de passe via `st.secrets`

---

## Structure des fichiers

```
portfolio-tracker/
├── src/
│   ├── importer.py          # Import CSV (initial + incrémental + upload)
│   ├── calculator.py        # Algorithme PRU/CMP itératif
│   ├── models.py            # Dataclasses Operation, Position, Cycle
│   ├── db.py                # Accès SQLite + settings clé/valeur
│   ├── quotes.py            # Cours temps réel + historique via yfinance
│   └── app.py               # Application Streamlit (6 pages)
├── data/
│   ├── portfolio.db         # Base SQLite (commitée sur GitHub)
│   └── inbox/               # Dépôt local CSV (non utilisé en prod)
├── tests/
│   ├── conftest.py
│   └── test_calculator.py
├── .streamlit/
│   └── secrets.toml         # Secrets locaux (jamais commité)
├── run.bat                  # Lancement rapide Windows
├── requirements.txt
└── README.md
```

---

## Pages de l'application

| Page | Contenu |
|------|---------|
| **Dashboard** | Performance journalière, versements cumulés vs objectif, répartition, PV réalisée/dividendes par année, PV latente par position, évolution PRU (DCA) avec cours historique |
| **Synthèse** | Date ouverture PEA + countdown 5 ans (exonération), apports, argent disponible, performance annualisée, gain total si sortie |
| **Positions actuelles** | Tableau PRU, cours, PV latente, dividendes |
| **Positions soldées** | Cycles clos : PV réalisée, dividendes, résultat net |
| **Mouvements** | Historique brut, filtres valeur/type/année |
| **Importer** | Upload CSV Boursorama → import + push GitHub automatique |

---

## Source de données

### Format CSV Boursorama (source de vérité)

- Séparateur : point-virgule (`;`)
- Encodage : UTF-8 BOM (`utf-8-sig`)
- Dates : `dd/mm/yyyy`
- Montant : décimal avec point (`-126.37`) ou virgule française (`-126,37`)

**En-tête :**
```
"Date opération";"Date valeur";Opération;Valeur;"Code ISIN";Montant;Quantité;Cours
```

### Types d'opérations

| Type (préfixe) | Traitement |
|---|---|
| `ACHAT COMPTANT` | Achat — montant négatif |
| `ACHAT COMPTANT ETR` | Achat ETF étranger — même logique |
| `VENTE COMPTANT` | Vente — montant positif |
| `COUPONS` | Dividende — ne modifie pas le PRU |
| `VIR...` | Virement — inclus dans solde espèces, exclu du calcul portefeuille |
| `FRAIS...`, `*RETROC...` | Frais divers — ignorés dans les calculs |

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

### Table `settings`

```sql
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

Utilisée pour stocker des valeurs persistantes (ex : PV annuelle manuelle).

---

## Algorithme PRU/CMP itératif (CRITIQUE)

**Base de calcul : `ABS(montant)` — frais de courtage inclus.** Méthode officielle Boursorama validée sur données réelles.

Principe :
- Grouper les opérations par valeur, trier par `date_op` ASC
- Maintenir un état courant : `qty`, `stock` (valeur au PRU), `cmp`
- ACHAT : `stock += abs(montant)`, `qty += quantite`, `cmp = stock / qty`
- VENTE : `pv = montant - cmp * quantite`, `stock -= cmp * quantite`, `qty -= quantite`
- Si `abs(qty) < 0.001` après vente → cycle soldé, reset état
- COUPONS : ne modifie pas le CMP, s'accumule dans `total_divs` et `cycle_divs`
- Ventes partielles : enregistrement de `(date, pv)` dans `partial_pv_entries`

**Points d'attention :**
- Tri chronologique strict (l'ordre impacte le PRU)
- Même jour : traiter les ACHAT avant les VENTE
- Seuil zéro : `abs(qty) < 0.001` (floating point)
- `ACHAT COMPTANT ETR` traité comme `ACHAT COMPTANT`
- Virements négatifs inclus dans solde espèces, exclus du calcul actions

---

## Métriques calculées

### Positions actuelles

| Métrique | Calcul |
|---|---|
| Quantité | `qty` |
| PRU (CMP) | `cmp = stock / qty` |
| Coût position | `cmp × qty` |
| Cours actuel | Yahoo Finance (yfinance) |
| PV latente | `(cours - cmp) × qty` |
| PV latente % | `(cours / cmp - 1) × 100` |
| Dividendes totaux | Tous les COUPONS sur cette valeur |
| Dividendes position | COUPONS depuis le dernier passage à qty=0 |
| PRU après dividendes | `(coût - div_position) / qty` |
| PV ventes partielles | PV cumulée des ventes partielles du cycle actuel |

### Synthèse

| Métrique | Calcul |
|---|---|
| Apports totaux | `Σ montant` des opérations VIR positifs |
| Solde espèces | `Σ montant` de toutes les opérations |
| Valeur des titres | `coût + pv_latente` |
| Total PEA | `espèces + valeur_titres` |
| PV réalisée | Cycles clos + ventes partielles en cours, par année |
| Gain total | `pv_réalisée + pv_latente + dividendes` |
| Performance % | `gain_total / apports × 100` |
| Performance annualisée | `gain / apports / n_années × 100` |
| Date exonération | Ouverture PEA + 5 ans = 22/08/2028 |

### Performance journalière (Dashboard)

Reconstruction de la valeur du portefeuille jour par jour depuis l'ouverture :
- Rejouer toutes les opérations chronologiquement
- Valeur = `espèces + Σ(qty_i × prix_i)` où `prix_i` = dernier cours connu
- Fallback si cours absent : coût d'achat (ni gain ni perte fictive)
- Comparaison avec apports cumulés

---

## Récupération des cours (Yahoo Finance)

Mapping ISIN → ticker dans `src/quotes.py` :

```python
ISIN_TO_TICKER = {
    "LU1681043599": "CW8.PA",    # Amundi MSCI World
    "IE0002XZSHO1": "EUNL.DE",   # iShares MSCI World (WPEA.PA hors service)
    "FR0000120271": "TTE.PA",    # TotalEnergies
    "FR0000125486": "DG.PA",     # Vinci
    "FR0000120503": "EN.PA",     # Bouygues
    "FR0000120073": "AI.PA",     # Air Liquide
    "FR0013258662": "AYV.PA",    # ALD/Ayvens (ALD.PA hors service)
    "FR0000131104": "BNP.PA",    # BNP Paribas
    "FR0011950732": "ELIOR.PA",  # Elior
    "FR0010112524": "NXI.PA",    # Nexity
    "FR0000130809": "GLE.PA",    # Société Générale
    "NL00150001Q9": "STLAM.MI",  # Stellantis (STLAM.PA hors service)
    "NL0000226223": "STM.DE",    # STMicroelectronics (STM.PA hors service — Xetra EUR)
    "FR0000124141": "VIE.PA",    # Veolia
}
```

**Règles de choix de ticker :**
- Préférer les tickers EUR (`.PA`, `.DE`, `.MI`) pour éviter les décalages de change
- `auto_adjust=False` pour l'historique (prix non ajustés aux dividendes)
- Fallback automatique via `_find_ticker_auto()` pour les ISIN non mappés
- Cache Streamlit : 5 min pour les cours, 1h pour l'historique

---

## Import depuis la production

1. Upload CSV via onglet **Importer** dans l'app
2. Traitement via `import_csv()` (fichier temporaire)
3. Push automatique de `data/portfolio.db` sur GitHub via PyGithub
4. Streamlit redéploie automatiquement

**Secrets requis dans Streamlit Cloud :**
```toml
password = "..."
github_token = "ghp_..."
github_repo = "ldubedoutperso/portfolio-tracker"
```

---

## Points d'attention

1. **OneDrive verrouille `portfolio.db`** lors des `git rebase` → utiliser `git merge --no-rebase` ou `--force-with-lease`
2. **Encodage Windows** : utiliser `PYTHONUTF8=1` pour les scripts Python en CLI
3. **Tickers Yahoo Finance** : vérifier régulièrement — certains tickers `.PA` tombent hors service (ex : STLAM.PA, ALD.PA, STM.PA, WPEA.PA)
4. **Performance journalière** : premier chargement lent (~10s) — mis en cache 1h via `@st.cache_data(ttl=3600)`
5. **Heure d'import** : SQLite stocke `CURRENT_TIMESTAMP` en UTC → afficher avec `datetime(imported_at, 'localtime')`
