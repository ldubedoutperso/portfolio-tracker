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

1. Exporter le CSV depuis Boursorama (onglet Mouvements, séparateur `;`, encodage UTF-8)
2. Placer le fichier dans `data/inbox/`
3. Cliquer sur **"Vérifier inbox"** dans la sidebar — les doublons sont ignorés automatiquement

Puis pousser sur GitHub pour mettre à jour le cloud :
```
git add .
git commit -m "Mise à jour données"
git push
```

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
│   ├── db.py           # Accès SQLite + settings clé/valeur
│   ├── importer.py     # Import CSV Boursorama (initial + incrémental)
│   ├── calculator.py   # Calcul PRU itératif, cycles, PV partielles
│   ├── quotes.py       # Cours temps réel et historique via yfinance
│   └── app.py          # Application Streamlit (5 pages)
├── data/
│   ├── portfolio.db    # Base SQLite
│   └── inbox/          # Dépôt des nouveaux CSV (ignoré par git)
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
