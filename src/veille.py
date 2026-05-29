"""Page Veille — affiche les articles markdown du dossier data/veille/.

À placer dans src/veille.py du repo portfolio-tracker.
Le dossier source d'articles est data/veille/AAAA-MM-JJ.md (un fichier par jour).
Format attendu : frontmatter YAML + corps markdown.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import streamlit as st

VEILLE_DIR = Path(__file__).parent.parent / "data" / "veille"

# Mappe niveau de risque → couleur de bandeau
RISQUE_STYLES = {
    "FAIBLE": ("#e8f5e9", "#2e7d32"),
    "MODÉRÉ": ("#fff9c4", "#9a7d00"),
    "MODÉRÉ-ÉLEVÉ": ("#ffe0b2", "#7a3e00"),
    "CRITIQUE": ("#ffcdd2", "#b71c1c"),
}

ACTION_BADGES = {
    "RECHARGE": ("🟢", "#2e7d32", "#e8f5e9"),
    "CONSERVE": ("🔵", "#1565c0", "#e3f2fd"),
    "ALLÈGE": ("🟠", "#e65100", "#ffe0b2"),
    "VENDS": ("🔴", "#b71c1c", "#ffcdd2"),
}


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Extrait le frontmatter YAML simple (key: value) et retourne (meta, corps_md).
    On évite une dépendance PyYAML pour rester léger. Format attendu :
    ---
    key: value
    bloc:
      sous_clé: valeur
    ---
    """
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw = text[3:end].strip("\n")
    body = text[end + 4 :].lstrip("\n")

    meta: dict = {}
    current_block_key: str | None = None
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        # Bloc imbriqué (2 espaces de retrait)
        if line.startswith("  ") and current_block_key:
            sub = line.strip()
            if ":" in sub:
                k, v = sub.split(":", 1)
                meta[current_block_key][k.strip()] = _strip_quotes(v.strip())
            continue
        # Clé racine
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()
            if v == "":
                meta[k] = {}
                current_block_key = k
            else:
                meta[k] = _strip_quotes(v)
                current_block_key = None
    return meta, body


def _strip_quotes(v: str) -> str:
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
        return v[1:-1]
    return v


def list_articles() -> list[Path]:
    """Retourne les articles triés par date décroissante (plus récent en premier)."""
    if not VEILLE_DIR.exists():
        return []
    files = [p for p in VEILLE_DIR.glob("*.md") if re.match(r"^\d{4}-\d{2}-\d{2}\.md$", p.name)]
    files.sort(reverse=True)
    return files


def render_verdict_banner(meta: dict) -> None:
    """Bandeau coloré 'Verdict du jour' selon le niveau de risque."""
    niveau = str(meta.get("niveau_risque", "MODÉRÉ"))
    bg, fg = RISQUE_STYLES.get(niveau, ("#f5f5f5", "#444"))
    confiance = meta.get("confiance", "—")
    libelle = meta.get("confiance_libelle", "")
    date_str = meta.get("date", "")
    st.markdown(
        f"""
        <div style="background:{bg}; border-left:6px solid {fg}; padding:14px 18px; border-radius:6px; margin-bottom:14px;">
          <div style="font-size:11px; letter-spacing:1px; color:{fg}; font-weight:700; opacity:0.85;">VEILLE DU {date_str}</div>
          <div style="font-size:20px; font-weight:700; color:{fg}; margin-top:4px;">Risque {niveau}</div>
          <div style="font-size:13px; color:#3a3a3a; margin-top:6px;">Confiance : <b>{confiance} / 10</b> — {libelle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_actions_chips(meta: dict) -> None:
    """Badges colorés par action (RECHARGE / CONSERVE / ALLÈGE / VENDS)."""
    actions = meta.get("actions") or {}
    if not actions:
        return
    chips_html = ""
    for nom, verdict in actions.items():
        emoji, fg, bg = ACTION_BADGES.get(verdict, ("⚪", "#444", "#f0f0f0"))
        chips_html += (
            f'<span style="display:inline-block; background:{bg}; color:{fg}; '
            f'padding:6px 12px; margin:4px 6px 4px 0; border-radius:14px; '
            f'font-size:13px; font-weight:600;">{emoji} {nom} — {verdict}</span>'
        )
    st.markdown(
        f"""
        <div style="margin-bottom:14px;">
          <div style="font-size:12px; color:#666; font-weight:600; margin-bottom:6px;">VERDICT PAR ACTION</div>
          {chips_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_veille() -> None:
    st.header("Veille")

    articles = list_articles()
    if not articles:
        st.info(
            "Aucun article de veille pour l'instant. "
            "Les articles sont déposés automatiquement dans `data/veille/` "
            "par la tâche planifiée Claude (un fichier par jour, nommé `AAAA-MM-JJ.md`)."
        )
        return

    # Sélecteur de date (dernier article par défaut)
    options = {p.stem: p for p in articles}
    selected_key = st.selectbox(
        "Article",
        options=list(options.keys()),
        index=0,
        format_func=lambda d: _format_date_label(d),
    )
    article_path = options[selected_key]

    text = article_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)

    # Bandeau verdict + badges actions en haut
    render_verdict_banner(meta)
    render_actions_chips(meta)

    # Corps de l'article (markdown brut)
    st.markdown(body, unsafe_allow_html=False)


def _format_date_label(d: str) -> str:
    """Affiche '2026-05-29' en 'vendredi 29 mai 2026 (aujourd'hui)'."""
    try:
        dt = datetime.strptime(d, "%Y-%m-%d").date()
    except ValueError:
        return d
    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    mois = [
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    ]
    label = f"{jours[dt.weekday()]} {dt.day} {mois[dt.month - 1]} {dt.year}"
    today = date.today()
    if dt == today:
        label += " (aujourd'hui)"
    elif (today - dt).days == 1:
        label += " (hier)"
    return label
