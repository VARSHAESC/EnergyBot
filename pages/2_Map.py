# -*- coding: utf-8 -*-
"""
pages/2_Map.py — Offline-friendly Map (Plotly scattergeo)
- No online tiles required
- Shows land/coastlines with a light theme
- Auto-centers/zooms to your data
"""

import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from geo_utils import (
    DEFAULT_EXCEL_PATH, load_excel, attach_geo_from_columns,
    geocode_missing_coords, pick_col, classify_priority, apply_filters_case_insensitive
)

OFFLINE = os.getenv("OFFLINE_MODE", "false").lower() == "true"

COLORS = {
    "bg": "#ffffff", "text": "#111111",
    "kritisch": "#ef4444", "gas": "#f59e0b", "strom": "#10b981", "fallback": "#3b82f6"
}

st.set_page_config(page_title="STADTWERKE WÜLFRATH — Netz-Karte", page_icon="🗺️", layout="wide")
st.title("🗺️ Netz-Karte — STADTWERKE WÜLFRATH")

# 1) Load & ensure geo
df = load_excel(DEFAULT_EXCEL_PATH)
if df.empty:
    st.warning("Keine Excel-Daten gefunden. Bitte laden Sie zunächst eine Datei im Dashboard.")
    st.stop()

df, has_geo = attach_geo_from_columns(df)
if not has_geo:
    if OFFLINE:
        st.warning("Koordinaten fehlen und Geokodierung ist offline deaktiviert. Bitte Koordinatenspalten in Excel bereitstellen.")
    else:
        with st.spinner("Geokodiere Adressen …"):
            df, has_geo = geocode_missing_coords(df)

# 2) Filters from session
filters = st.session_state.get("filters", {})
effective = {k: v for k, v in filters.items() if v is not None and not k.startswith("__")}
filtered = apply_filters_case_insensitive(df, effective)

# 3) KPI focus
focus = st.session_state.get("kpi_focus")
if not focus:
    try:
        focus = st.query_params.get("focus", [None])[0]
    except Exception:
        qp = st.experimental_get_query_params()
        focus = qp.get("focus", [None])[0] if isinstance(qp, dict) else None

cat = classify_priority(filtered)
filtered = filtered.copy()
filtered["__kpi_cat"] = cat

if focus in {"critical", "warning", "normal"}:
    st.subheader(f"Drill‑down: **{focus}**")
    mdf = filtered[filtered["__kpi_cat"] == focus]
else:
    st.subheader("Alle gefilterten Ergebnisse")
    mdf = filtered

# 4) Sanity: ensure coords
if {"__lat", "__lon"}.issubset(mdf.columns):
    mdf = mdf.dropna(subset=["__lat", "__lon"]).copy()
else:
    mdf = pd.DataFrame()

if mdf.empty:
    st.info("Keine gültigen Geo-Punkte für die aktuelle Auswahl.")
    st.stop()

# 5) Color per point
def color_for_row(row) -> str:
    if focus == "critical":
        return COLORS["kritisch"]
    tcol = pick_col(mdf, ["Anschlussart", "Spartentyp", "Type"])
    if tcol:
        t = str(row[tcol]).lower()
        if t == "gas":
            return COLORS["gas"]
        if t in ["strom", "electricity", "power"]:
            return COLORS["strom"]
    return COLORS["fallback"]

mdf["__color"] = mdf.apply(color_for_row, axis=1)

# Tooltips
kunden_id_col = pick_col(mdf, ["Kunden-ID", "KundenID", "CustomerID"])
anschluss_id_col = pick_col(mdf, ["Anschluss-ID", "AnschlussID", "ConnectionID"])

hover_text = []
for _, r in mdf.iterrows():
    kid = str(r[kunden_id_col]) if kunden_id_col else "-"
    aid = str(r[anschluss_id_col]) if anschluss_id_col else "-"
    hover_text.append(f"<b>Kunde:</b> {kid}<br><b>Anschluss:</b> {aid}")

# 5) Build scatter_mapbox (Street-level views)
fig = go.Figure(
    go.Scattermapbox(
        lon=mdf["__lon"], lat=mdf["__lat"],
        text=hover_text, hoverinfo="text",
        mode="markers",
        marker=dict(size=12, color=mdf["__color"], opacity=0.8)
    )
)

# Center point
lat_center = float(mdf["__lat"].mean())
lon_center = float(mdf["__lon"].mean())

fig.update_layout(
    mapbox=dict(
        style="open-street-map",
        center=dict(lat=lat_center, lon=lon_center),
        zoom=12
    ),
    margin=dict(l=0, r=0, t=30, b=0),
    height=700,
    title="Netzansicht (Street-level Map)"
)

st.plotly_chart(fig, use_container_width=True)

# 6) Drill-through Data
st.markdown("### 📋 Detailierte Auswahl")
st.dataframe(mdf.drop(columns=[c for c in mdf.columns if c.startswith("__")]), use_container_width=True)
