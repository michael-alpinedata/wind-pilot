"""
Dashboard Streamlit — historique du vent, balise Pioupiou 2176 (Baie de Mémard).

Lit directement les tables marts sur Neon (pas de recalcul côté app,
tout est déjà agrégé par dbt).

Usage :
    pip install streamlit plotly sqlalchemy psycopg2-binary pandas python-dotenv
    streamlit run streamlit_app.py
"""

import os
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine

# Charge le fichier .env en local s'il existe
load_dotenv()

st.set_page_config(page_title="Vent — Lac du Bourget", layout="wide", page_icon="🪁")


@st.cache_resource
def get_engine():
    host = st.secrets.get("NEON_HOST", os.environ.get("NEON_HOST"))
    db = st.secrets.get("NEON_DB", os.environ.get("NEON_DB"))
    user = st.secrets.get("NEON_USER", os.environ.get("NEON_USER"))
    password = st.secrets.get("NEON_PASSWORD", os.environ.get("NEON_PASSWORD"))

    if not all([host, db, user, password]):
        st.error("Credentials Neon manquants. Vérifiez secrets.toml ou votre .env.")
        st.stop()

    url = f"postgresql+psycopg2://{user}:{password}@{host}/{db}?sslmode=require"
    return create_engine(url)


@st.cache_data(ttl=3600)
def load_mart(table_name: str, schema: str = "dbt_prod_marts") -> pd.DataFrame:
    engine = get_engine()
    return pd.read_sql(f"select * from {schema}.{table_name}", engine)


# ---------------------------------------------------------------------------
# Barre latérale : Choix des unités
# ---------------------------------------------------------------------------
st.sidebar.title("⚙️ Configuration")
unit_choice = st.sidebar.radio(
    "Unité de vitesse du vent",
    options=["Nœuds (kn)", "km/h", "m/s"],
    index=0,  # Nœuds par défaut
)

# Facteurs de conversion depuis le km/h (unité stockée en BDD)
if unit_choice == "Nœuds (kn)":
    factor = 1 / 1.852
    unit_symbol = "kn"
elif unit_choice == "m/s":
    factor = 1 / 3.6
    unit_symbol = "m/s"
else:
    factor = 1.0
    unit_symbol = "km/h"


def convert_bucket_label(bucket_str: str, f: float, symbol: str) -> str:
    """Convertit les libellés de tranches de vitesse (ex: '8-15 km/h' -> '4.3-8.1 kn')."""
    if f == 1.0:
        return bucket_str
    try:
        clean = bucket_str.replace(" km/h", "").strip()
        if "-" in clean:
            low, high = map(float, clean.split("-"))
            return f"{low * f:.1f}-{high * f:.1f} {symbol}"
        elif "+" in clean:
            val = float(clean.replace("+", ""))
            return f"{val * f:.1f}+ {symbol}"
    except Exception:
        return bucket_str
    return bucket_str


st.title("Historique du vent — Baie de Mémard (balise Pioupiou 2176)")

daily = load_mart("mart_wind_by_day")
hourly = load_mart("mart_wind_by_hour")
monthly = load_mart("mart_wind_by_month")
rose = load_mart("mart_wind_rose")

# Application du facteur de conversion d'unité
daily["mean_converted"] = daily["mean_kmh"] * factor
daily["max_gust_converted"] = daily["max_gust_kmh"] * factor

hourly["mean_converted"] = hourly["mean_kmh"] * factor
hourly["median_converted"] = hourly["median_kmh"] * factor
hourly["p90_converted"] = hourly["p90_kmh"] * factor

monthly["mean_converted"] = monthly["mean_kmh"] * factor

# ---------------------------------------------------------------------------
# 1. Série temporelle journalière
# ---------------------------------------------------------------------------

st.header("Série temporelle")

daily["measured_date_local"] = pd.to_datetime(daily["measured_date_local"])
date_min, date_max = daily["measured_date_local"].min(), daily["measured_date_local"].max()

date_range = st.slider(
    "Période",
    min_value=date_min.to_pydatetime(),
    max_value=date_max.to_pydatetime(),
    value=(date_min.to_pydatetime(), date_max.to_pydatetime()),
)

slot_filter = st.radio("Créneau", ["jour", "nuit", "les deux"], horizontal=True, index=2)

filtered = daily[
    (daily["measured_date_local"] >= date_range[0])
    & (daily["measured_date_local"] <= date_range[1])
]
if slot_filter != "les deux":
    filtered = filtered[filtered["day_night_slot"] == slot_filter]

plot_df = (
    filtered.groupby("measured_date_local")
    .agg(
        mean_speed=("mean_converted", "mean"),
        max_gust=("max_gust_converted", "max"),
    )
    .reset_index()
)

fig_ts = go.Figure()
fig_ts.add_trace(
    go.Scatter(
        x=plot_df["measured_date_local"],
        y=plot_df["max_gust"],
        name="Rafale max",
        line=dict(width=0),
        showlegend=False,
    )
)
fig_ts.add_trace(
    go.Scatter(
        x=plot_df["measured_date_local"],
        y=plot_df["mean_speed"],
        name="Vitesse moyenne",
        fill="tonexty",
        line=dict(color="royalblue"),
    )
)
fig_ts.update_layout(
    yaxis_title=unit_symbol,
    xaxis_title="Date",
    hovermode="x unified",
)
st.plotly_chart(fig_ts, width='stretch')

# ---------------------------------------------------------------------------
# 2. Profil horaire type (avec explication P90)
# ---------------------------------------------------------------------------

st.header("Profil horaire type (toutes dates confondues)")

with st.expander("ℹ️ Comment lire la courbe P90 (90ème percentile) ?"):
    st.markdown(
        f"""
        * **Moyenne & Médiane :** Représentent les conditions classiques / régulières observées à cette heure.
        * **P90 (90ème percentile) :** Indique que **90% des mesures sont inférieures ou égales** à cette vitesse.
          * *Autrement dit :* Il y a **10% de chances** d'avoir un vent au moins aussi fort.
          * C'est l'indicateur idéal pour repérer l'heure de levée des **thermiques solides** (ex: la *Traverse*) ou les coups de vent exploitables en foil.
        """
    )

fig_hourly = go.Figure()
fig_hourly.add_trace(
    go.Scatter(
        x=hourly["hour_local"],
        y=hourly["p90_converted"],
        name="P90 (10% de chance d'avoir +)",
        line=dict(dash="dot", color="firebrick"),
    )
)
fig_hourly.add_trace(
    go.Scatter(
        x=hourly["hour_local"],
        y=hourly["mean_converted"],
        name="Moyenne",
        line=dict(color="royalblue"),
    )
)
fig_hourly.add_trace(
    go.Scatter(
        x=hourly["hour_local"],
        y=hourly["median_converted"],
        name="Médiane",
        line=dict(dash="dash", color="green"),
    )
)
fig_hourly.update_layout(
    xaxis_title="Heure locale",
    yaxis_title=unit_symbol,
    hovermode="x unified",
)
st.plotly_chart(fig_hourly, width='stretch')

# ---------------------------------------------------------------------------
# 3. Saisonnalité mensuelle
# ---------------------------------------------------------------------------

st.header("Saisonnalité mensuelle")

col1, col2 = st.columns(2)

with col1:
    fig_monthly = go.Figure()
    fig_monthly.add_trace(
        go.Bar(x=monthly["measured_month"], y=monthly["mean_converted"], name="Moyenne")
    )
    fig_monthly.update_layout(
        yaxis_title=unit_symbol, xaxis_title="Mois", title="Vitesse moyenne"
    )
    st.plotly_chart(fig_monthly, width='stretch')

with col2:
    threshold_converted = 12 * factor
    fig_pct = go.Figure()
    fig_pct.add_trace(
        go.Bar(
            x=monthly["measured_month"],
            y=monthly["pct_above_12kmh"],
            name=f"% > {threshold_converted:.1f} {unit_symbol}",
        )
    )
    fig_pct.update_layout(
        yaxis_title="% du temps",
        xaxis_title="Mois",
        title=f"% du temps navigable (> {threshold_converted:.1f} {unit_symbol})",
    )
    st.plotly_chart(fig_pct, width='stretch')

# ---------------------------------------------------------------------------
# 4. Rose des vents (Orientée Nord en haut, Est à droite)
# ---------------------------------------------------------------------------

st.header("Rose des vents")

direction_order = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]
speed_order = ["0-8 km/h", "8-15 km/h", "15-22 km/h", "22-30 km/h", "30+ km/h"]

fig_rose = go.Figure()
for bucket in speed_order:
    subset = rose[rose["speed_bucket"] == bucket].set_index("wind_direction_16pt")
    subset = subset.reindex(direction_order).fillna(0)
    
    # Libellé adapté à l'unité choisie
    legend_label = convert_bucket_label(bucket, factor, unit_symbol)

    fig_rose.add_trace(
        go.Barpolar(
            r=subset["nb_measurements"],
            theta=direction_order,
            name=legend_label,
        )
    )

fig_rose.update_layout(
    polar=dict(
        angularaxis=dict(
            direction="clockwise",  # Rotation horaire (N -> E -> S -> W)
            rotation=90,            # Place le Nord (N) tout en haut (90 deg)
            showticklabels=True,
        ),
        radialaxis=dict(showticklabels=True, ticks=""),
    ),
    legend=dict(orientation="h"),
)
st.plotly_chart(fig_rose, width='stretch')

# ---------------------------------------------------------------------------
# 5. Assistant Recommandation Matos Wing Foil (Projet Capstone LLM Zoomcamp)
# ---------------------------------------------------------------------------

st.markdown("---")
st.header("🤖 Assistant Wing Foil — Choix de Matos")
st.caption("Projet RAG / LLM Zoomcamp — Calcule la taille de wing et de foil optimale selon tes conditions.")

col_rider1, col_rider2, col_rider3 = st.columns(3)

with col_rider1:
    weight = st.number_input("Poids du pratiquant (kg)", min_value=40, max_value=120, value=75)
with col_rider2:
    level = st.selectbox("Niveau", ["Débutant", "Intermédiaire", "Confirmé / Expert"])
with col_rider3:
    target_wind = st.number_input(f"Vent prévu ({unit_symbol})", min_value=5.0, max_value=45.0, value=15.0)

if st.button("💡 Recommander le matos idéal"):
    # Convertit systématiquement en nœuds pour le prompt / règles métier
    wind_knots = target_wind if unit_symbol == "kn" else target_wind * (1.852 if unit_symbol == "km/h" else 1.94384)
    
    st.info(f"Analyse pour un rider de **{weight} kg** ({level}) dans **{wind_knots:.1f} nœuds** à la Baie de Mémard...")
    
    # TODO Capstone: Ici viendra l'appel à votre chaîne RAG (LangChain / LlamaIndex / Custom)
    # Exemple d'output structuré pour le test
    st.markdown(
        f"""
        ### Recommandation suggérée :
        * **Taille de Wing :** `{5.0 if wind_knots < 18 else (4.0 if wind_knots < 25 else 3.0)} m²`
        * **Surface de Foil (Front Wing) :** `{"1500-1800" if level == "Débutant" else "1000-1200"} cm²`
        * **Volume de Planche :** `{weight + (30 if level == 'Débutant' else 10)} Litres`
        
        > *Note : Cette section sera connectée à la base RAG contenant les guides constructeurs (Gong, F-One, Reed, Duotone) pour le projet LLM Zoomcamp.*
        """
    )

st.caption(
    "Données vent : (c) contributors of the OpenWindMap wind network "
    "(https://www.openwindmap.org) — balise 2176 / Baie de Mémard."
)
