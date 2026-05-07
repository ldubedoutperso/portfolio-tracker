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
│   ├── db.py                # Accès SQLite + settings + ticker_cache
│   ├── quotes.py            # Cours yfinance + auto-détection des tickers
│   └── app.py               # Application Streamlit (6 pages)
├── data/
│   ├── portfolio.db              # Base SQLite (commitée sur GitHub)
│   ├── manual_operations.json    # Ops manuelles (titres non cotés, ex. TUDI FAIR 2)
│   └── inbox/                    # Dépôt local CSV (non utilisé en prod)
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

### Table `ticker_cache`

```sql
CREATE TABLE ticker_cache (
    isin TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    resolved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Cache des correspondances ISIN → ticker yfinance résolues automatiquement.
Évite de re-requêter Yahoo Finance à chaque démarrage. Le mapping manuel
`ISIN_TO_TICKER` dans `quotes.py` garde priorité sur le cache (utile pour
corriger les cas où l'auto-détection se trompe).

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
| Solde espèces | `Σ montant` des opérations **hors `source_file = 'manual'`** |
| Valeur des titres | `coût + pv_latente` (titres non cotés valorisés au coût via fallback) |
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

Trois niveaux de résolution ISIN → ticker dans `src/quotes.py` :

1. **`ISIN_TO_TICKER` (overrides manuels, priorité 1)** — pour corriger les cas où l'auto-détection se trompe et pour les non-cotés (ticker vide pour skip yfinance) :

```python
ISIN_TO_TICKER = {
    "LU1681043599": "CW8.PA",        # Amundi MSCI World
    "IE0002XZSHO1": "IE0002XZSHO1",  # iShares MSCI World PEA (ISIN direct)
    "FR0000120271": "TTE.PA",        # TotalEnergies
    "FR0000125486": "DG.PA",         # Vinci
    "FR0000120503": "EN.PA",         # Bouygues
    "FR0000120073": "AI.PA",         # Air Liquide
    "FR0013258662": "AYV.PA",        # ALD/Ayvens
    "FR0000131104": "BNP.PA",        # BNP Paribas
    "FR0011950732": "ELIOR.PA",      # Elior
    "FR0010112524": "NXI.PA",        # Nexity
    "FR0000130809": "GLE.PA",        # Société Générale
    "NL00150001Q9": "STLAM.MI",      # Stellantis (Milan EUR)
    "NL0000226223": "STM.DE",        # STMicroelectronics (Xetra EUR)
    "FR0000124141": "VIE.PA",        # Veolia
    "FR0000121667": "EL.PA",         # EssilorLuxottica
    "TUDI_FAIR_2": "",               # Non coté — skip yfinance, valorisé au coût
}
```

2. **Cache DB `ticker_cache` (priorité 2)** — chargé en mémoire au démarrage via `load_cache(db)`.

3. **Auto-détection `discover_and_cache(isin, valeur, db)` (priorité 3)** :
   - Tentative 1 : `yf.Ticker(isin)` direct (marche pour certains ETF)
   - Tentative 2 : `yf.Search(valeur)` avec priorité `.PA` puis autres places EUR (`.AS`, `.BR`, `.LS`, `.MC`, `.MI`, `.DE`, `.F`, `.VI`)
   - Résultat persisté en DB (`ticker_cache`) pour ne pas re-requêter

L'auto-détection s'exécute au chargement de l'app pour tout ISIN traité (ACHAT/VENTE)
absent de `ISIN_TO_TICKER`. Cache Streamlit `@st.cache_data(ttl=86400)` pour éviter
les re-tentatives à chaque rerun.

**Règles de choix de ticker :**
- Préférer les tickers EUR (`.PA`, `.DE`, `.MI`) pour éviter les décalages de change
- `auto_adjust=False` pour l'historique (prix non ajustés aux dividendes)
- Cache Streamlit : 5 min pour les cours, 1h pour l'historique
- Pour un titre non coté : ajouter l'ISIN à `ISIN_TO_TICKER` avec ticker vide (`""`) → `get_current_price` retourne `None`, fallback à coût

---

## Opérations manuelles (titres non cotés)

Certains titres présents dans le PEA Boursorama (FCPI, FCPR, fonds non cotés
type **TUDI FAIR 2**) n'apparaissent **pas** dans le CSV Mouvements exporté.
Pour les matérialiser dans l'app :

### Fichier `data/manual_operations.json`

```json
[
  {
    "date_op": "2024-01-01",
    "op_type": "ACHAT",
    "valeur": "TUDI FAIR 2",
    "isin": "TUDI_FAIR_2",
    "montant": -1000.0,
    "quantite": 1000.0
  }
]
```

Chargé au démarrage de l'app via `load_manual_operations()`, ces opérations
sont injectées dans la liste `operations` avec `source_file = "manual"`,
puis traitées par `calculate_portfolio` comme des achats normaux.

### Filtrage du cash

**Important** : ces ops sont **exclues du calcul du solde espèces** car le
flux de souscription correspondant n'est pas dans les CSV Boursorama (qui
restent la source de vérité du cash). Sinon : double-déduction → cash négatif.

```python
solde_especes = sum(op.montant for op in operations if op.source_file != "manual")
```

Idem pour `cash_perf` et `apports_perf` dans la courbe de performance journalière.

### Valorisation

Comme leur ticker est vide (`""`) dans `ISIN_TO_TICKER`, `get_current_price`
renvoie `None`. La page Synthèse et la courbe utilisent alors le **coût payé**
comme valeur (ni gain ni perte fictive).

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
3. **Tickers Yahoo Finance** : vérifier régulièrement — certains tickers `.PA` tombent hors service (ex : STLAM.PA, ALD.PA, STM.PA, WPEA.PA). L'auto-détection résout les nouveaux ISIN mais peut se tromper sur les ETF aux noms tronqués → override manuel dans `ISIN_TO_TICKER` au besoin
4. **Performance journalière** : premier chargement lent (~10s) — mis en cache 1h via `@st.cache_data(ttl=3600)`
5. **Heure d'import** : SQLite stocke `CURRENT_TIMESTAMP` en UTC → afficher avec `datetime(imported_at, 'localtime')`
6. **Fallback courbe perf** : si un ISIN n'a aucun cours yfinance, le code utilise le **coût cumulé** (`holdings_cost_perf[isin]`) comme valeur — **pas** `coût × qty` (ex-bug). Attention si modification du calcul `titres_perf` dans `app.py`
7. **Ops manuelles** : toujours filtrer par `source_file != "manual"` dans tout calcul de cash/apports — sinon double-déduction
