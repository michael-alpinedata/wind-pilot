"""
Dashboard Streamlit — historique du vent, balise Pioupiou 2176.

Lit directement les tables marts sur Neon (pas de recalcul côté app,
tout est déjà agrégé par dbt).

Usage :
    pip install streamlit plotly sqlalchemy psycopg2-binary pandas
    streamlit run streamlit_app.py

Config :
    Variables d'environnement NEON_HOST, NEON_DB, NEON_USER, NEON_PASSWORD
    (ou adapter get_engine() pour lire un secrets.toml Streamlit).
"""

import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import create_engine

st.set_page_config(page_title="Vent — Lac du Bourget", layout="wide")


@st.cache_resource
def get_engine():
    # st.secrets ira lire le fichier .streamlit/secrets.toml en local,
    # et piochera dans l'interface sécurisée côté Streamlit Cloud.
    host = st.secrets["NEON_HOST"]
    db = st.secrets["NEON_DB"]
    user = st.secrets["NEON_USER"]
    password = st.secrets["NEON_PASSWORD"]
    
    url = f"postgresql+psycopg2://{user}:{password}@{host}/{db}?sslmode=require"
    return create_engine(url)


@st.cache_data(ttl=3600)
def load_mart(table_name: str, schema: str = "dbt_dev_marts") -> pd.DataFrame:
    engine = get_engine()
    return pd.read_sql(f"select * from {schema}.{table_name}", engine)


st.title("Historique du vent — Baie de Mémard (balise Pioupiou 2176)")

daily = load_mart("mart_wind_by_day")
hourly = load_mart("mart_wind_by_hour")
monthly = load_mart("mart_wind_by_month")
rose = load_mart("mart_wind_rose")

# ---------------------------------------------------------------------------
# 1. Série temporelle journalière — style courbe moyenne + bande rafale,
#    comme sur les pages de station OpenWindMap, mais sur tout l'historique
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

# Agrégation par date si les deux créneaux sont affichés ensemble
plot_df = (
    filtered.groupby("measured_date_local")
    .agg(mean_kmh=("mean_kmh", "mean"), max_gust_kmh=("max_gust_kmh", "max"))
    .reset_index()
)

fig_ts = go.Figure()
fig_ts.add_trace(
    go.Scatter(
        x=plot_df["measured_date_local"],
        y=plot_df["max_gust_kmh"],
        name="Rafale max",
        line=dict(width=0),
        showlegend=False,
    )
)
fig_ts.add_trace(
    go.Scatter(
        x=plot_df["measured_date_local"],
        y=plot_df["mean_kmh"],
        name="Vitesse moyenne",
        fill="tonexty",
        line=dict(color="royalblue"),
    )
)
fig_ts.update_layout(
    yaxis_title="km/h",
    xaxis_title="Date",
    hovermode="x unified",
)
st.plotly_chart(fig_ts, width='stretch')

# ---------------------------------------------------------------------------
# 2. Profil horaire type — pour repérer l'heure de levée de la Traverse
# ---------------------------------------------------------------------------

st.header("Profil horaire type (toutes dates confondues)")

fig_hourly = go.Figure()
fig_hourly.add_trace(
    go.Scatter(x=hourly["hour_local"], y=hourly["p90_kmh"], name="P90", line=dict(dash="dot"))
)
fig_hourly.add_trace(
    go.Scatter(x=hourly["hour_local"], y=hourly["mean_kmh"], name="Moyenne")
)
fig_hourly.add_trace(
    go.Scatter(x=hourly["hour_local"], y=hourly["median_kmh"], name="Médiane", line=dict(dash="dash"))
)
fig_hourly.update_layout(xaxis_title="Heure locale", yaxis_title="km/h")
st.plotly_chart(fig_hourly, width='stretch')

# ---------------------------------------------------------------------------
# 3. Saisonnalité mensuelle
# ---------------------------------------------------------------------------

st.header("Saisonnalité mensuelle")

col1, col2 = st.columns(2)

with col1:
    fig_monthly = go.Figure()
    fig_monthly.add_trace(
        go.Bar(x=monthly["measured_month"], y=monthly["mean_kmh"], name="Moyenne")
    )
    fig_monthly.update_layout(yaxis_title="km/h", xaxis_title="Mois")
    st.plotly_chart(fig_monthly, width='stretch')

with col2:
    fig_pct = go.Figure()
    fig_pct.add_trace(
        go.Bar(x=monthly["measured_month"], y=monthly["pct_above_12kmh"], name="% > seuil praticable")
    )
    fig_pct.update_layout(yaxis_title="% du temps", xaxis_title="Mois")
    st.plotly_chart(fig_pct, width='stretch')

# ---------------------------------------------------------------------------
# 4. Rose des vents
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
    fig_rose.add_trace(
        go.Barpolar(
            r=subset["nb_measurements"],
            theta=direction_order,
            name=bucket,
        )
    )
fig_rose.update_layout(
    polar=dict(radialaxis=dict(showticklabels=True, ticks="")),
    legend=dict(orientation="h"),
)
st.plotly_chart(fig_rose, width='stretch')

st.caption(
    "Données : (c) contributors of the OpenWindMap wind network "
    "(https://www.openwindmap.org) — balise 2176 / Baie de Mémard."
)
