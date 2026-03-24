# Portfolio PEA Tracker

Application de suivi d'un PEA Boursorama, déployée sur Streamlit Cloud et protégée par mot de passe.

**URL de production** : https://portfolio-tracker-perso.streamlit.app

---

## Pages

| Page | Contenu |
|------|---------|
| **Dashboard** | Performance journalière du portefeuille, versements cumulés vs objectif, répartition, PV réalisée/dividendes par année, PV latente par position, évolution du PRU (DCA) avec courbe de cours |
| **Synthèse** | Date d'ouverture PEA + countdown 5 ans, apports totaux, argent disponible, performance annualisée (latente/réalisée/dividendes), gain total si sortie |
| **Positions actuelles** | Tableau détaillé des positions en cours (PRU, cours, PV latente, dividendes) |
| **Positions soldées** | Historique des cycles clos (PV réalisée, dividendes, résultat net) |
| **Mouvements** | Toutes les opérations avec filtres par valeur, type, année |
| **Importer** | Upload CSV Boursorama → import automatique + sauvegarde GitHub |

---

## Lancement en local

Double-cliquer sur `run.bat` à la racine du projet.

Ou depuis le terminal VS Code :
```
python -m streamlit run src/app.py
```

L'application s'ouvre sur http://localhost:8501 — le mot de passe est celui défini dans `.streamlit/secrets.toml`.

---

## Mettre à jour les données (depuis la prod)

1. Exporter le CSV depuis Boursorama (onglet Mouvements, séparateur `;`, encodage UTF-8)
2. Ouvrir l'app → onglet **Importer**
3. Déposer le fichier CSV → cliquer **Importer**
4. L'app importe les données et met à jour GitHub automatiquement

---

## Déploiement

L'app est déployée sur [Streamlit Community Cloud](https://streamlit.io/cloud) depuis le repo GitHub public `ldubedoutperso/portfolio-tracker`.
Streamlit redéploie automatiquement à chaque `git push`.

Les secrets sont configurés dans **Streamlit Cloud → App settings → Secrets** :
```toml
password = "votre_mot_de_passe"
github_token = "ghp_..."
github_repo = "ldubedoutperso/portfolio-tracker"
```

---

## Structure du projet

```
portfolio-tracker/
├── src/
│   ├── models.py       # Dataclasses Operation, Position, Cycle
│   ├── db.py           # Accès SQLite + settings clé/valeur
│   ├── importer.py     # Import CSV Boursorama (initial + incrémental)
│   ├── calculator.py   # Calcul PRU itératif, cycles, PV partielles
│   ├── quotes.py       # Cours temps réel et historique via yfinance (ISIN→ticker)
│   └── app.py          # Application Streamlit (6 pages)
├── data/
│   ├── portfolio.db    # Base SQLite
│   └── inbox/          # Dépôt local des CSV (non utilisé en prod)
├── tests/
│   ├── conftest.py
│   └── test_calculator.py
├── .streamlit/
│   └── secrets.toml    # Secrets locaux (jamais commité)
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
github_token = "ghp_..."
github_repo = "ldubedoutperso/portfolio-tracker"
```

---

## Ajouter un nouveau ticker

Si une valeur achetée n'a pas de courbe dans le graphique DCA, ajouter son ISIN et ticker Yahoo Finance dans `src/quotes.py` :

```python
ISIN_TO_TICKER: dict[str, str] = {
    ...
    "FR0000123456": "TICKER.PA",  # NOM DE LA VALEUR
}
```

Trouver le bon ticker : chercher la valeur sur [finance.yahoo.com](https://finance.yahoo.com) et copier le symbole.
Préférer les tickers en EUR (`.PA` Paris, `.DE` Xetra, `.MI` Milan) pour éviter les décalages de change.

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
