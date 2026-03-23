import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.calculator import calculate_portfolio
from src.db import Database
from src.importer import process_inbox
from src.quotes import get_prices_batch, get_history

DB_PATH = Path(__file__).parent.parent / "data" / "portfolio.db"
INBOX_DIR = Path(__file__).parent.parent / "data" / "inbox"

st.set_page_config(page_title="Portfolio PEA", layout="wide")

# --- Protection par mot de passe ---
def check_password():
    if st.session_state.get("authenticated"):
        return True
    st.title("Portfolio PEA")
    pwd = st.text_input("Mot de passe", type="password")
    if st.button("Connexion"):
        if pwd == st.secrets.get("password", ""):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Mot de passe incorrect")
    return False

if not check_password():
    st.stop()

@st.cache_data(ttl=300)
def fetch_prices(isins: tuple) -> dict:
    return get_prices_batch(list(isins))


@st.cache_data(ttl=3600)
def fetch_history_cached(isin: str, start: str) -> list | None:
    return get_history(isin, start)


# --- Initialisation ---
INBOX_DIR.mkdir(parents=True, exist_ok=True)
db = Database(str(DB_PATH))

# --- Sidebar ---
with st.sidebar:
    st.title("Portfolio PEA")
    page = st.radio(
        "Navigation",
        ["Dashboard", "Synthèse", "Positions actuelles", "Positions soldées", "Mouvements"],
    )
    st.divider()

    if st.button("Vérifier inbox", use_container_width=True):
        with st.spinner("Importation en cours..."):
            results = process_inbox(str(INBOX_DIR), db)
        if results:
            for r in results:
                st.success(
                    f"{r['imported']} nouvelle(s) operation(s) "
                    f"({r['duplicates']} doublon(s)) depuis {r['file']}"
                )
            fetch_prices.clear()
        else:
            st.info("Aucun nouveau fichier dans inbox/")

    count = db.get_operation_count()
    st.metric("Opérations en base", count)

    last_import = db.get_last_import()
    if last_import:
        st.caption(f"Dernier import : {last_import[:19]}")

# --- Chargement des données ---
operations = db.get_all_operations()
positions, cycles = calculate_portfolio(operations)

if positions:
    prices = fetch_prices(tuple(p.isin for p in positions))
else:
    prices = {}



# ---------------------------------------------
# PAGE 0 : Dashboard
# ---------------------------------------------
def page_dashboard():
    import plotly.express as px
    import plotly.graph_objects as go

    st.header("Dashboard")

    if not positions and not cycles:
        st.info("Aucune donnée disponible.")
        return

    pv_by_year: dict[int, float] = {}
    for c in cycles:
        y = c.close_date.year
        pv_by_year[y] = pv_by_year.get(y, 0.0) + c.realized_pv
    for p in positions:
        for entry_date, entry_pv in p.partial_pv_entries:
            y = entry_date.year
            pv_by_year[y] = pv_by_year.get(y, 0.0) + entry_pv

    div_by_year: dict[int, float] = {}
    for op in operations:
        if op.op_type == "COUPONS":
            y = op.date_op.year
            div_by_year[y] = div_by_year.get(y, 0.0) + op.montant

    CHART_LAYOUT = dict(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#e2e8f0",
        margin=dict(t=30, b=20, l=10, r=10),
    )

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Versements cumulés dans le PEA")
        objectif_mensuel = st.number_input(
            "Objectif mensuel (EUR)", min_value=0, max_value=10000,
            value=500, step=50, key="objectif_vir"
        )
        vir_ops = [
            (op.date_op, op.montant)
            for op in operations
            if op.op_type.upper().startswith("VIR") and op.montant > 0
        ]
        if vir_ops:
            from datetime import date as _date
            import math

            df_vir = pd.DataFrame(vir_ops, columns=["Date", "Montant"]).sort_values("Date")
            df_vir["Cumul"] = df_vir["Montant"].cumsum()

            # Courbe theorique : objectif_mensuel/mois depuis le 1er versement jusqu'a aujourd'hui + 5 ans
            first_date = df_vir["Date"].iloc[0]
            today = _date.today()
            end_date = _date(today.year + 3, today.month, 1)
            n_months = (end_date.year - first_date.year) * 12 + (end_date.month - first_date.month) + 1
            theo_dates = [
                _date(first_date.year + (first_date.month - 1 + i) // 12,
                      (first_date.month - 1 + i) % 12 + 1, 1)
                for i in range(n_months)
            ]
            theo_vals = [(i + 1) * objectif_mensuel for i in range(n_months)]

            fig4 = go.Figure()
            fig4.add_trace(go.Scatter(
                x=df_vir["Date"], y=df_vir["Cumul"],
                mode="lines+markers",
                name="Versements réels",
                line=dict(color="#3b82f6", width=2),
                fill="tozeroy",
                fillcolor="rgba(59,130,246,0.10)",
            ))
            fig4.add_trace(go.Scatter(
                x=theo_dates, y=theo_vals,
                mode="lines",
                name=f"Objectif ({objectif_mensuel} EUR/mois)",
                line=dict(color="#f59e0b", width=2, dash="dash"),
            ))
            fig4.update_layout(
                xaxis_title="Date", yaxis_title="EUR",
                legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1),
                height=320,
                **CHART_LAYOUT,
            )
            st.plotly_chart(fig4, use_container_width=True)

            # Écart réel vs objectif à la date du dernier versement
            last_real_date = df_vir["Date"].iloc[-1]
            last_real_cumul = df_vir["Cumul"].iloc[-1]
            n_months_elapsed = (last_real_date.year - first_date.year) * 12 + (last_real_date.month - first_date.month) + 1
            theo_at_last = n_months_elapsed * objectif_mensuel
            ecart = last_real_cumul - theo_at_last
            delta_label = f"{ecart:+,.0f} EUR vs objectif"
            st.metric("Versements au dernier virement", f"{last_real_cumul:,.0f} EUR", delta=delta_label)
        else:
            st.info("Aucun virement trouvé")

    with col2:
        st.subheader("Répartition du portefeuille")
        pos_data = []
        for p in positions:
            cours = prices.get(p.isin)
            vm = cours * p.quantity if cours is not None else p.cost
            pos_data.append({"Valeur": p.valeur, "Montant": vm})
        if pos_data:
            df_pie = pd.DataFrame(pos_data)
            fig = px.pie(
                df_pie, values="Montant", names="Valeur",
                hole=0.45,
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            fig.update_layout(showlegend=False, height=320, **CHART_LAYOUT)
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    col3, col4 = st.columns(2)

    with col3:
        st.subheader("PV réalisée et dividendes par année")
        all_years = sorted(set(pv_by_year) | set(div_by_year))
        if all_years:
            fig3 = go.Figure()
            fig3.add_trace(go.Bar(
                name="PV réalisée",
                x=[str(y) for y in all_years],
                y=[pv_by_year.get(y, 0.0) for y in all_years],
                marker_color="#3b82f6",
            ))
            fig3.add_trace(go.Bar(
                name="Dividendes",
                x=[str(y) for y in all_years],
                y=[div_by_year.get(y, 0.0) for y in all_years],
                marker_color="#f59e0b",
            ))
            fig3.update_layout(
                barmode="group",
                xaxis_title="Année", yaxis_title="EUR",
                legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1),
                height=320,
                **CHART_LAYOUT,
            )
            st.plotly_chart(fig3, use_container_width=True)

    with col4:
        st.subheader("PV latente par position")
        pv_rows = []
        for p in positions:
            cours = prices.get(p.isin)
            if cours is not None:
                pv = (cours - p.cmp) * p.quantity
                pct = (cours / p.cmp - 1) * 100
                pv_rows.append({"Valeur": p.valeur, "PV": pv, "Pct": pct})
        if pv_rows:
            df_pv = pd.DataFrame(pv_rows).sort_values("PV")
            colors = ["#ef4444" if v < 0 else "#22c55e" for v in df_pv["PV"]]
            fig2 = go.Figure(go.Bar(
                x=df_pv["PV"],
                y=df_pv["Valeur"],
                orientation="h",
                marker_color=colors,
                text=[f"{v:+.0f} EUR  ({p:+.1f}%)" for v, p in zip(df_pv["PV"], df_pv["Pct"])],
                textposition="outside",
            ))
            fig2.add_vline(x=0, line_width=1, line_color="#64748b")
            fig2.update_layout(
                xaxis_title="EUR",
                height=320,
                xaxis=dict(showgrid=False),
                **CHART_LAYOUT,
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Cours non disponibles")

    st.divider()

    # -- Graphique DCA : PRU vs prix d'achat --
    st.subheader("Évolution du PRU vs prix d'achat")

    achat_valeurs = sorted(set(
        op.valeur for op in operations if op.op_type.startswith("ACHAT")
    ))
    if achat_valeurs:
        selected_valeur = st.selectbox(
            "Choisir une valeur", achat_valeurs,
            index=next((i for i, v in enumerate(achat_valeurs) if "ISHS" in v.upper() or "ISHARES" in v.upper() or "WPEA" in v.upper() or "WOR" in v.upper()), 0),
            key="dca_valeur"
        )

        achats = sorted(
            [op for op in operations
             if op.op_type.startswith("ACHAT") and op.valeur == selected_valeur],
            key=lambda o: o.date_op,
        )
        ventes = sorted(
            [op for op in operations
             if op.op_type.startswith("VENTE") and op.valeur == selected_valeur],
            key=lambda o: o.date_op,
        )

        # Reconstruire le PRU running en tenant compte des ventes
        all_ops = sorted(
            [op for op in operations
             if op.op_type.startswith(("ACHAT", "VENTE")) and op.valeur == selected_valeur],
            key=lambda o: (o.date_op, 0 if o.op_type.startswith("ACHAT") else 1),
        )

        running_cost = 0.0
        running_qty = 0.0
        dca_rows = []
        vente_rows = []

        for op in all_ops:
            if op.op_type.startswith("ACHAT"):
                prix_unitaire = abs(op.montant) / op.quantite if op.quantite else 0
                running_cost += abs(op.montant)
                running_qty += op.quantite
                pru = running_cost / running_qty if running_qty > 0 else 0
                dca_rows.append({
                    "Date": op.date_op,
                    "Prix": prix_unitaire,
                    "PRU": pru,
                    "Delta": prix_unitaire - pru,
                    "Qte": op.quantite,
                })
            elif op.op_type.startswith("VENTE") and running_qty > 0:
                pru = running_cost / running_qty
                prix_vente = op.montant / op.quantite if op.quantite else 0
                pv_unitaire = prix_vente - pru
                vente_rows.append({
                    "Date": op.date_op,
                    "Prix": prix_vente,
                    "PRU": pru,
                    "PV unitaire": pv_unitaire,
                    "Qte": op.quantite,
                })
                running_cost -= pru * op.quantite
                running_qty -= op.quantite
                if running_qty < 0.001:
                    running_cost = 0.0
                    running_qty = 0.0

        if dca_rows:
            df_dca = pd.DataFrame(dca_rows)
            colors_achats = ["#ef4444" if d > 0 else "#22c55e" for d in df_dca["Delta"]]

            fig_dca = go.Figure()

            # Ligne PRU (step)
            fig_dca.add_trace(go.Scatter(
                x=df_dca["Date"], y=df_dca["PRU"],
                mode="lines",
                name="PRU courant",
                line=dict(color="#3b82f6", width=2, shape="hv"),
            ))

            # Points achats
            fig_dca.add_trace(go.Scatter(
                x=df_dca["Date"], y=df_dca["Prix"],
                mode="markers",
                name="Achat",
                marker=dict(
                    color=colors_achats,
                    size=10,
                    symbol="circle",
                    line=dict(color="white", width=1),
                ),
                text=[
                    f"ACHAT {q:.0f} titre(s)<br>Prix : {p:.4f} EUR<br>PRU après : {pru:.4f} EUR<br>Impact PRU : {d:+.4f} EUR"
                    for p, pru, d, q in zip(df_dca["Prix"], df_dca["PRU"], df_dca["Delta"], df_dca["Qte"])
                ],
                hoverinfo="text+x",
            ))

            # Points ventes
            if vente_rows:
                df_ventes = pd.DataFrame(vente_rows)
                colors_ventes = ["#22c55e" if pv >= 0 else "#ef4444" for pv in df_ventes["PV unitaire"]]
                fig_dca.add_trace(go.Scatter(
                    x=df_ventes["Date"], y=df_ventes["Prix"],
                    mode="markers",
                    name="Vente",
                    marker=dict(
                        color=colors_ventes,
                        size=12,
                        symbol="triangle-down",
                        line=dict(color="white", width=1),
                    ),
                    text=[
                        f"VENTE {q:.0f} titre(s)<br>Prix : {p:.4f} EUR<br>PRU : {pru:.4f} EUR<br>PV/titre : {pv:+.4f} EUR"
                        for p, pru, pv, q in zip(df_ventes["Prix"], df_ventes["PRU"], df_ventes["PV unitaire"], df_ventes["Qte"])
                    ],
                    hoverinfo="text+x",
                ))

            # Courbe historique des cours
            isin_valeur = next(
                (op.isin for op in operations
                 if op.valeur == selected_valeur and op.isin and op.isin != "nan"),
                None
            )
            if isin_valeur and dca_rows:
                first_op_date = str(df_dca["Date"].iloc[0])
                hist = fetch_history_cached(isin_valeur, first_op_date)
                if hist:
                    h_dates, h_prices = zip(*hist)
                    fig_dca.add_trace(go.Scatter(
                        x=list(h_dates), y=list(h_prices),
                        mode="lines",
                        name="Cours reel",
                        line=dict(color="rgba(148,163,184,0.5)", width=1.5),
                        hovertemplate="%{y:.4f} EUR<extra>Cours</extra>",
                    ))
                    # Remettre cours reel en arriere-plan
                    traces = fig_dca.data
                    fig_dca.data = (traces[-1],) + traces[:-1]

            fig_dca.update_layout(
                xaxis_title="Date",
                yaxis_title="EUR / action",
                legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1),
                height=420,
                **CHART_LAYOUT,
            )
            st.plotly_chart(fig_dca, use_container_width=True)


# ─────────────────────────────────────────────
# PAGE 1 : Positions actuelles
# ─────────────────────────────────────────────
def page_positions():
    st.header("Positions actuelles")

    if not positions:
        st.info("Aucune position en cours. Importez des données via le bouton 'Vérifier inbox'.")
        return

    rows = []
    for p in positions:
        cours = prices.get(p.isin)
        pv_latente = (cours - p.cmp) * p.quantity if cours is not None else None
        pv_pct = ((cours / p.cmp) - 1) * 100 if cours is not None else None

        rows.append(
            {
                "Valeur": p.valeur,
                "ISIN": p.isin,
                "Qte": p.quantity,
                "PRU (EUR)": p.cmp,
                "Coût (EUR)": p.cost,
                "Cours (EUR)": cours,
                "PV latente (EUR)": pv_latente,
                "PV latente (%)": pv_pct,
                "Div. totaux (EUR)": p.total_dividends,
                "Div. position (EUR)": p.current_dividends,
                "PRU après div (EUR)": p.pru_after_div,
                "PV partielles (EUR)": p.partial_pv if p.partial_pv != 0 else None,
            }
        )

    df = pd.DataFrame(rows)
    df = df.sort_values("PV latente (EUR)", ascending=False, na_position="last")

    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "PRU (EUR)": st.column_config.NumberColumn(format="%.4f"),
            "Coût (EUR)": st.column_config.NumberColumn(format="%.2f"),
            "Cours (EUR)": st.column_config.NumberColumn(format="%.2f"),
            "PV latente (EUR)": st.column_config.NumberColumn(format="%.2f"),
            "PV latente (%)": st.column_config.NumberColumn(format="%.2f"),
            "Div. totaux (EUR)": st.column_config.NumberColumn(format="%.2f"),
            "Div. position (EUR)": st.column_config.NumberColumn(format="%.2f"),
            "PRU après div (EUR)": st.column_config.NumberColumn(format="%.4f"),
            "PV partielles (EUR)": st.column_config.NumberColumn(format="%.2f"),
        },
        hide_index=True,
    )

    total_cost = sum(p.cost for p in positions)
    known_pv = [
        (prices[p.isin] - p.cmp) * p.quantity
        for p in positions
        if prices.get(p.isin) is not None
    ]
    total_pv = sum(known_pv) if known_pv else None

    col1, col2 = st.columns(2)
    col1.metric("Total coût portefeuille", f"{total_cost:,.2f} EUR")
    if total_pv is not None:
        col2.metric("Total PV latente", f"{total_pv:,.2f} EUR")
    else:
        col2.metric("Total PV latente", "N/A (cours manquants)")


# ─────────────────────────────────────────────
# PAGE 2 : Positions soldées
# ─────────────────────────────────────────────
def page_cycles():
    st.header("Positions soldées")

    if not cycles:
        st.info("Aucune position soldée.")
        return

    rows = [
        {
            "Valeur": c.valeur,
            "Date ouverture": c.open_date,
            "Date clôture": c.close_date,
            "PV réalisée (EUR)": c.realized_pv,
            "Dividendes (EUR)": c.dividends,
            "Résultat net (EUR)": c.net_result,
        }
        for c in cycles
    ]

    df = pd.DataFrame(rows)
    df = df.sort_values("Date clôture", ascending=False)

    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "Date ouverture": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Date clôture": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "PV réalisée (EUR)": st.column_config.NumberColumn(format="%.2f"),
            "Dividendes (EUR)": st.column_config.NumberColumn(format="%.2f"),
            "Résultat net (EUR)": st.column_config.NumberColumn(format="%.2f"),
        },
        hide_index=True,
    )

    total_pv = sum(c.realized_pv for c in cycles)
    total_div = sum(c.dividends for c in cycles)
    total_net = sum(c.net_result for c in cycles)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total PV réalisée", f"{total_pv:,.2f} EUR")
    col2.metric("Total dividendes", f"{total_div:,.2f} EUR")
    col3.metric("Total net", f"{total_net:,.2f} EUR")


# ─────────────────────────────────────────────
# PAGE 3 : Synthèse
# ─────────────────────────────────────────────
def page_synthese():
    st.header("Synthèse")

    from datetime import date as _date
    current_year = _date.today().year

    # -- Calculs de base --
    pv_by_year: dict[int, float] = {}
    for c in cycles:
        y = c.close_date.year
        pv_by_year[y] = pv_by_year.get(y, 0.0) + c.realized_pv
    # Ventes partielles sur positions encore ouvertes
    for p in positions:
        for entry_date, entry_pv in p.partial_pv_entries:
            y = entry_date.year
            pv_by_year[y] = pv_by_year.get(y, 0.0) + entry_pv

    def _manual_key(y: int) -> str:
        return f"manual_pv_{y}"

    def _get_manual(year: int) -> float | None:
        v = db.get_setting(_manual_key(year))
        return float(v) if v is not None else None

    calc_current = pv_by_year.get(current_year, 0.0)
    manual_current = _get_manual(current_year)
    pv_current = manual_current if manual_current is not None else calc_current

    pv_realisee = sum(v for y, v in pv_by_year.items() if y != current_year) + pv_current
    total_div = sum(op.montant for op in operations if op.op_type == "COUPONS")
    solde_especes = sum(op.montant for op in operations)

    total_cost = sum(p.cost for p in positions)
    known_pv_items = [
        (prices[p.isin] - p.cmp) * p.quantity
        for p in positions
        if prices.get(p.isin) is not None
    ]
    pv_latente = sum(known_pv_items) if known_pv_items else None
    valeur_marche = (total_cost + pv_latente) if pv_latente is not None else None
    total_pea = (solde_especes + valeur_marche) if valeur_marche is not None else None
    pv_latente_pct = (pv_latente / total_cost * 100) if (pv_latente is not None and total_cost > 0) else None
    gain_total = (pv_realisee + pv_latente + total_div) if pv_latente is not None else None
    total_deposits = sum(op.montant for op in operations if op.op_type.upper().startswith("VIR") and op.montant > 0)
    gain_total_pct = (gain_total / total_deposits * 100) if (gain_total is not None and total_deposits > 0) else None

    # Ancienneté du portefeuille en années
    from datetime import date as _date2
    first_op_date = min(op.date_op for op in operations) if operations else None
    n_years = (((_date2.today() - first_op_date).days / 365.25) if first_op_date else None)
    pv_latente_an = (pv_latente / n_years) if (pv_latente is not None and n_years and n_years > 0) else None
    pv_latente_pct_an = (pv_latente_an / total_deposits * 100) if (pv_latente_an is not None and total_deposits > 0) else None
    pv_realisee_an = (pv_realisee / n_years) if (n_years and n_years > 0) else None
    pv_realisee_pct_an = (pv_realisee_an / total_deposits * 100) if (pv_realisee_an is not None and total_deposits > 0) else None
    div_an = (total_div / n_years) if (n_years and n_years > 0) else None
    div_pct_an = (div_an / total_deposits * 100) if (div_an is not None and total_deposits > 0) else None
    gain_total_an = (gain_total / n_years) if (gain_total is not None and n_years and n_years > 0) else None
    gain_total_pct_an = (gain_total_an / total_deposits * 100) if (gain_total_an is not None and total_deposits > 0) else None

    # -- Bloc 0 : Apports --
    st.subheader("Apports")
    st.metric("Total apporté sur le PEA", f"{total_deposits:,.2f} EUR")

    st.divider()

    # -- Bloc 1 : Argent disponible --
    st.subheader("Argent disponible")
    c1, c2, c3 = st.columns(3)
    c1.metric("Liquidites (especes)", f"{solde_especes:,.2f} EUR")
    c2.metric(
        "Valeur des titres",
        f"{valeur_marche:,.2f} EUR" if valeur_marche is not None else "N/A",
    )
    c3.metric(
        "Total PEA",
        f"{total_pea:,.2f} EUR" if total_pea is not None else "N/A",
    )

    st.divider()

    # -- Bloc 2 : Performance --
    st.subheader("Performance")
    c1, c2, c3 = st.columns(3)
    if pv_latente is not None:
        delta_str = f"{pv_latente_pct:+.1f}%" if pv_latente_pct is not None else None
        c1.metric("PV latente (positions en cours)", f"{pv_latente:,.2f} EUR", delta=delta_str)
        if pv_latente_an is not None:
            c1.caption(f"~ {pv_latente_an:+,.0f} EUR/an  ({pv_latente_pct_an:+.1f}%/an)")
    else:
        c1.metric("PV latente (positions en cours)", "N/A")
    c2.metric("PV réalisée (cycles clos)", f"{pv_realisee:,.2f} EUR")
    if pv_realisee_an is not None:
        c2.caption(f"~ {pv_realisee_an:+,.0f} EUR/an  ({pv_realisee_pct_an:+.1f}%/an)")
    c3.metric("Dividendes perçus", f"{total_div:,.2f} EUR")
    if div_an is not None:
        c3.caption(f"~ {div_an:+,.0f} EUR/an  ({div_pct_an:+.1f}%/an)")

    st.divider()

    # -- Bloc 3 : Si je sors aujourd'hui --
    st.subheader("Si je sors aujourd'hui")
    if gain_total is not None:
        delta_gain_str = f"{gain_total_pct:+.1f}%" if gain_total_pct is not None else None
        st.metric("Gain total (latent + réalisé + dividendes)", f"{gain_total:,.2f} EUR", delta=delta_gain_str)
        if gain_total_an is not None:
            st.caption(f"~ {gain_total_an:+,.0f} EUR/an  ({gain_total_pct_an:+.1f}%/an) — depuis {n_years:.1f} ans")
    else:
        st.metric("Gain total (latent + réalisé + dividendes)", "N/A (cours manquants)")

    # [TABLEAU PV PAR ANNEE EDITABLE - desactive, remettre si besoin]
    # st.caption(
    #     f"Ligne {current_year} editable -- effacez pour revenir au calcul auto ({calc_current:.2f} EUR)"
    # )
    # all_years = sorted(set(pv_by_year.keys()) | {current_year})
    # df_table = pd.DataFrame([
    #     {"Annee": y, "PV réalisée (EUR)": (pv_current if y == current_year else pv_by_year.get(y, 0.0))}
    #     for y in all_years
    # ])
    # editor_key = f"pv_editor_{pv_current:.2f}"
    # edited = st.data_editor(
    #     df_table,
    #     use_container_width=False,
    #     column_config={
    #         "Annee": st.column_config.NumberColumn(format="%d", disabled=True),
    #         "PV réalisée (EUR)": st.column_config.NumberColumn(format="%.2f"),
    #     },
    #     hide_index=True,
    #     key=editor_key,
    # )
    # mask = edited["Annee"] == current_year
    # if mask.any():
    #     cell = edited.loc[mask, "PV réalisée (EUR)"].iloc[0]
    #     if pd.isna(cell):
    #         if manual_current is not None:
    #             db.delete_setting(_manual_key(current_year))
    #             st.rerun()
    #     else:
    #         new_float = float(cell)
    #         if abs(new_float - pv_current) > 0.001:
    #             db.set_setting(_manual_key(current_year), str(new_float))
    #             st.rerun()
def page_mouvements():
    st.header("Mouvements")

    if not operations:
        st.info("Aucune opération en base.")
        return

    df = pd.DataFrame(
        [
            {
                "Date": op.date_op,
                "Type": op.op_type,
                "Valeur": op.valeur,
                "ISIN": op.isin,
                "Montant (EUR)": op.montant,
                "Quantité": op.quantite,
                "Source": op.source_file or "",
            }
            for op in operations
        ]
    )

    # Filtres
    col1, col2, col3 = st.columns(3)

    valeurs = sorted(df["Valeur"].unique().tolist())
    selected_valeur = col1.selectbox("Valeur", ["Toutes"] + valeurs)

    types = sorted(df["Type"].unique().tolist())
    selected_type = col2.selectbox("Type", ["Tous"] + types)

    years = sorted(df["Date"].apply(lambda d: d.year).unique().tolist(), reverse=True)
    selected_year = col3.selectbox("Année", ["Toutes"] + [str(y) for y in years])

    if selected_valeur != "Toutes":
        df = df[df["Valeur"] == selected_valeur]
    if selected_type != "Tous":
        df = df[df["Type"] == selected_type]
    if selected_year != "Toutes":
        df = df[df["Date"].apply(lambda d: d.year) == int(selected_year)]

    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "Date": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Montant (EUR)": st.column_config.NumberColumn(format="%.2f"),
        },
        hide_index=True,
    )
    st.caption(f"{len(df)} opération(s) affichée(s)")


# ─────────────────────────────────────────────
# Routage
# ─────────────────────────────────────────────
if page == "Dashboard":
    page_dashboard()
elif page == "Positions actuelles":
    page_positions()
elif page == "Positions soldées":
    page_cycles()
elif page == "Synthèse":
    page_synthese()
elif page == "Mouvements":
    page_mouvements()
