# Portfolio PEA Tracker

Application de suivi d'un PEA Boursorama, déployée sur Streamlit Cloud et protégée par mot de passe.

**URL de production** : https://portfolio-tracker-perso.streamlit.app

---

## Pages

| Page | Contenu |
|------|---------|
| **Dashboard** | Versements cumulés, répartition, PV réalisée/dividendes par année, PV latente par position, évolution du PRU (DCA) |
| **Synthèse** | Date d'ouverture PEA, apports totaux, argent disponible, performance (latente/réalisée/dividendes), gain total si sortie |
| **Positions actuelles** | Tableau détaillé des positions en cours (PRU, cours, PV latente, dividendes) |
| **Positions soldées** | Historique des cycles clos (PV réalisée, dividendes, résultat net) |
| **Mouvements** | Toutes les opérations avec filtres par valeur, type, année |

---

## Lancement en local

Double-cliquer sur `run.bat` à la racine du projet.

Ou depuis le terminal VS Code :
```
python -m streamlit run src/app.py
```

L'application s'ouvre sur http://localhost:8501 — le mot de passe est celui défini dans `.streamlit/secrets.toml`.

---

## Mettre à jour les données

### Depuis le cloud (recommandé)

1. Onglet **Importer** dans l'app déployée
2. Upload du CSV Boursorama
3. La base est sauvegardée automatiquement sur GitHub (token requis dans secrets)

### En local

1. Exporter le CSV depuis Boursorama (onglet Mouvements, séparateur `;`, encodage UTF-8)
2. Placer le fichier dans `data/inbox/`
3. Cliquer sur **"Vérifier inbox"** dans la sidebar — les doublons sont ignorés automatiquement

Puis pousser sur GitHub pour mettre à jour le cloud :
```
git add .
git commit -m "Mise à jour données"
git push
```

## Titres non cotés (TUDI FAIR 2, FCPI, etc.)

Les titres non cotés n'apparaissent pas dans le CSV Mouvements de Boursorama.
Pour les matérialiser dans l'app, éditer [data/manual_operations.json](data/manual_operations.json) :

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

Puis ajouter l'ISIN dans `ISIN_TO_TICKER` de [src/quotes.py](src/quotes.py) avec un ticker vide (`""`) pour skip yfinance — la position sera valorisée à son coût.

Ces opérations sont **exclues du calcul du solde espèces** (le flux de souscription est déjà reflété dans le cash Boursorama).

## Auto-détection des tickers

Au démarrage de l'app, tout ISIN traité (ACHAT/VENTE) absent de `ISIN_TO_TICKER` est résolu automatiquement :
1. `Ticker(ISIN)` direct (marche pour certains ETF)
2. Fallback sur `yf.Search(nom_de_la_valeur)` avec priorité Euronext Paris (`.PA`)

Les résolutions sont cachées en DB (table `ticker_cache`). En cas de mauvaise détection, ajouter un override dans `ISIN_TO_TICKER` (priorité sur le cache).

---

## Déploiement

L'app est déployée sur [Streamlit Community Cloud](https://streamlit.io/cloud) depuis le repo GitHub.
Streamlit redéploie automatiquement à chaque `git push`.

Le mot de passe est configuré dans **Streamlit Cloud → App settings → Secrets** :
```toml
password = "votre_mot_de_passe"
```

---

## Structure du projet

```
portfolio-tracker/
├── src/
│   ├── models.py       # Dataclasses Operation, Position, Cycle
│   ├── db.py           # Accès SQLite (operations, settings, ticker_cache)
│   ├── importer.py     # Import CSV Boursorama (initial + incrémental)
│   ├── calculator.py   # Calcul PRU itératif, cycles, PV partielles
│   ├── quotes.py       # Cours yfinance + auto-détection des tickers
│   └── app.py          # Application Streamlit (6 pages)
├── data/
│   ├── portfolio.db              # Base SQLite
│   ├── manual_operations.json    # Ops manuelles (titres non cotés)
│   └── inbox/                    # Dépôt des nouveaux CSV (ignoré par git)
├── tests/
│   ├── conftest.py
│   └── test_calculator.py
├── .streamlit/
│   └── secrets.toml    # Mot de passe local (ignoré par git)
├── run.bat             # Lancement rapide Windows
└── requirements.txt
```

---

## Installation (nouveau poste)

```
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Créer `.streamlit/secrets.toml` :
```toml
password = "change_me"
```

---

## Format CSV Boursorama

- Séparateur : `;`
- Encodage : UTF-8 BOM
- En-tête : `"Date opération";"Date valeur";Opération;Valeur;"Code ISIN";Montant;Quantité;Cours`

---

## Tests

```
pytest tests/
```
