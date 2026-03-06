# -*- coding: utf-8 -*-
"""
app.py — ESC Utility Services Pvt Ltd Intelligence Platform
DEUTSCHE VERSION | Navigierbare KPIs | Split-Schnittstelle (Karte & Liste)
"""

import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import numpy as np
from datetime import datetime
from dotenv import load_dotenv

from rag_engine import EnergyRAG
from geo_utils import (
    ALL_UTILITIES, get_utility_df, get_unified_df,
    kpi_advanced, invalidate_cache, get_material_distribution,
    get_bundling_potential, CURRENT_YEAR
)
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
from streamlit_mic_recorder import mic_recorder
from gtts import gTTS
import time
import io
import base64

load_dotenv()

# ─────────────── Konfiguration ──────────────────────────────────────
st.set_page_config(
    page_title="STADTWERKE X — Infrastruktur-Intelligenz",
    page_icon="🏢",
    layout="wide",
)

# ─────────────── Styling ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');

html, body, [data-testid="stAppViewContainer"] {
    background-color: #ffffff !important;
    color: #000000 !important;
    font-family: 'Outfit', sans-serif !important;
}

[data-testid="stSidebar"] {
    background-color: #f8fafc !important;
    border-right: 1px solid #e2e8f0;
}

.main-header { font-size: 34px; font-weight: 700; color: #0f172a; margin-bottom: 5px; }
.sub-header { font-size: 15px; color: #475569; margin-bottom: 25px; }

/* KPI Karten */
.metric-card {
    background-color: #ffffff; 
    border-radius: 12px;
    padding: 20px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    transition: all 0.2s ease;
    text-align: center;
    color: #0f172a !important;
    cursor: pointer;
}
.metric-card:hover { transform: translateY(-3px); box-shadow: 0 8px 20px rgba(0,0,0,0.08); }
.metric-value { font-size: 36px; font-weight: 800; color: #0f172a; }
.metric-label { font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.8px; margin-top: 5px; }
.metric-detail { font-size: 10px; color: #94a3b8; margin-top: 3px; }

/* Seitenleiste für Map/List Split */
.split-list-container {
    height: 650px;
    overflow-y: auto;
    padding: 10px;
    background: #ffffff;
    border-radius: 12px;
    border: 1px solid #e2e8f0;
}
.asset-item {
    background: white;
    padding: 12px;
    margin-bottom: 8px;
    border-radius: 8px;
    border-left: 4px solid #e2e8f0;
    box-shadow: 0 2px 4px rgba(0,0,0,0.03);
}

.stTabs [data-baseweb="tab-list"] { gap: 20px; }
.stTabs [data-baseweb="tab"] { color: #64748b; font-weight: 600; font-size: 14px; }
.stTabs [aria-selected="true"] { color: #0f172a !important; border-bottom-color: #0f172a !important; }

.bot-msg { background: #f1f5f9; border: 1px solid #e2e8f0; color: #0f172a; padding: 12px; border-radius: 12px; margin-bottom: 10px; font-size: 14px; }
.user-msg { background: #ffffff; border: 1px solid #e2e8f0; color: #0f172a; padding: 12px; border-radius: 12px; margin-bottom: 10px; text-align: right; font-size: 14px; }

/* Floating Mic Styling */
.stMicRecorder {
    position: fixed;
    bottom: 25px;
    right: 70px;
    z-index: 1000;
}
.stMicRecorder button {
    border-radius: 50% !important;
    width: 45px !important;
    height: 45px !important;
    background-color: #ffffff !important;
    color: #0f172a !important;
    border: 1px solid #e2e8f0 !important;
    transition: all 0.3s ease;
    box-shadow: 0 4px 6px rgba(0,0,0,0.05);
}
.stMicRecorder button:hover {
    background-color: #334155 !important;
    animation: pulse 1.5s infinite;
}
/* Small buttons for Chat/Voice controls */
.stButton button {
    font-size: 13px !important;
    padding: 2px 10px !important;
    min-height: 32px !important;
}
.small-btn-container button {
    font-size: 11px !important;
    padding: 2px 8px !important;
    min-height: 28px !important;
    white-space: nowrap !important;
}
@keyframes pulse {
    0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
    70% { box-shadow: 0 0 0 15px rgba(239, 68, 68, 0); }
    100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
}
</style>
""", unsafe_allow_html=True)

# ─────────────── Session State ──────────────────────────────────────
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "active_tab" not in st.session_state: st.session_state.active_tab = "📈 Strategische Analyse"
if "drilldown_type" not in st.session_state: st.session_state.drilldown_type = "None"
if "speak_text" not in st.session_state: st.session_state.speak_text = None
if "speak_id" not in st.session_state: st.session_state.speak_id = 0
if "history" not in st.session_state: st.session_state.history = []
if "pending_action" not in st.session_state: st.session_state.pending_action = None
if "map_center" not in st.session_state: st.session_state.map_center = None
if "map_zoom" not in st.session_state: st.session_state.map_zoom = 13
if "last_utility" not in st.session_state: st.session_state.last_utility = None
if "target_tab" not in st.session_state: st.session_state.target_tab = None
if "last_map_idx" not in st.session_state: st.session_state.last_map_idx = None
if "selected_customer_id" not in st.session_state: st.session_state.selected_customer_id = None

# CRITICAL: If a target tab is set, override the logical and widget state BEFORE the UI renders
if st.session_state.target_tab and st.session_state.target_tab in ["📉 Strategische Analyse", "🗺️ Netz-Karte", "🛡️ Compliance & Daten", "🤖 AI -Assistent"]:
    st.session_state.active_tab = st.session_state.target_tab
    st.session_state.navigation_tab_widget = st.session_state.target_tab
    st.session_state.target_tab = None

def check_auth(user, pwd):
    if user == os.getenv("APP_USERNAME", "admin") and pwd == os.getenv("APP_PASSWORD", "esc_service_2026"):
        st.session_state.authenticated = True
        st.rerun()
    else:
        st.error("Ungültige Zugangsdaten.")

# ─────────────── Login ───────────────────────────────────────────────
if not st.session_state.authenticated:
    st.markdown('<h1 style="color:#0f172a; text-align:center; margin-top:100px; white-space: nowrap;">🏢 STADTWERKE X</h1><p style="text-align:center; color:#64748b;">Plattform für Infrastruktur-Intelligenz</p>', unsafe_allow_html=True)
    _, c2, _ = st.columns([1.2, 1.6, 1.2])
    with c2:
        u = st.text_input("Benutzername")
        p = st.text_input("Passwort", type="password")
        if st.button("Anmelden", use_container_width=True): check_auth(u, p)
    st.stop()

# ─────────────── Backend ─────────────────────────────────────────────
@st.cache_resource
def get_engine(): return EnergyRAG()

@st.cache_data
def load_data_cached(util):
    df = get_unified_df() if util == "Alle Sparten" else get_utility_df(util)
    if not df.empty:
        # Pre-calculate Netz-Karte to avoid SettingWithCopyWarning and repeated calculations
        if "Material Netzleitung" in df.columns and "Dimension Netzleitung" in df.columns:
            df["Netz-Karte"] = df["Material Netzleitung"].astype(str) + " / " + df["Dimension Netzleitung"].astype(str)
        else:
            df["Netz-Karte"] = "N/A"
    return kpi_advanced(df), df

def play_audio(text):
    if not text: return
    try:
        # Simple bilingual detection
        en_indicators = [' the ', ' is ', ' are ', ' where ', ' how ', ' manual ', ' what ']
        lang = 'en' if any(ind in text.lower() for ind in en_indicators) else 'de'
        
        tts = gTTS(text=text, lang=lang)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        b64 = base64.b64encode(fp.read()).decode()
        
        # Unique ID using session state counter
        uid = st.session_state.get("speak_id", 0)
        
        # Using a component for a clean "fresh" iframe which forces audio refresh
        audio_html = f"""
            <html>
                <body>
                    <audio id="audio_{uid}" autoplay>
                        <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
                    </audio>
                    <script>
                        var audio = document.getElementById('audio_{uid}');
                        audio.play().catch(function(error) {{
                            console.log("Autoplay blocked or failed:", error);
                        }});
                    </script>
                </body>
            </html>
        """
        import streamlit.components.v1 as components
        components.html(audio_html, height=0, width=0)
        
        # Reset state
        st.session_state.speak_text = None
    except Exception as e:
        st.sidebar.error(f"TTS Error: {str(e)}")

# ─────────────── Sidebar ─────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/isometric/100/factory.png", width=50)
    st.markdown("### System-Steuerung")
    selected_utility = st.selectbox("Sparte auswählen", ["Alle Sparten"] + ALL_UTILITIES)
    
    st.divider()
    st.markdown("### KI-Training & Status")
    engine = get_engine()
    llm_status = engine.check_llm_status()
    if llm_status["ok"]: st.success(f"🤖 {llm_status['msg']}")
    else: st.error(f"⚠️ {llm_status['msg']}")
    
    kb_count = engine.vs.count()
    st.info(f"Daten im Speicher: {kb_count}")
    
    if st.button("🔄 KI-Speicher aktualisieren", use_container_width=True, type="primary"):
        with st.spinner("Indiziere Daten..."):
            invalidate_cache()
            st.cache_resource.clear()
            st.cache_data.clear()
            engine = get_engine()
            count = engine.init_or_refresh_kb(reset=True)
            st.success(f"Erfolgreich: {count} Datensätze indiziert.")
            st.rerun()

    st.divider()
    st.button("🚪 Abmelden", on_click=lambda: st.session_state.update({"authenticated": False}), use_container_width=True)

# ─────────────── Utility Switch Logic ─────────────────────────────────
if st.session_state.last_utility != selected_utility:
    st.session_state.map_center = None
    st.session_state.map_zoom = 13
    st.session_state.last_utility = selected_utility

# ─────────────── Dashboard ────────────────────────────────────────────
kpis, df = load_data_cached(selected_utility)
COLORS = {"Gas": "#f59e0b", "Wasser": "#3b82f6", "Strom": "#10b981", "Hoch": "#ef4444", "Mittel": "#f59e0b", "Niedrig": "#22c55e", "Unbekannt": "#94a3b8"}

st.markdown('<h1 class="main-header">STADTWERKE X</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Plattform für Infrastruktur-Analyse, Risikomanagement und Lifecycle-Planung.</p>', unsafe_allow_html=True)

# KPI Navigation Logic
def navigate_to(tab, dd):
    """Programmatic navigation helper that properly handles widget state reconciliation."""
    st.session_state.active_tab = tab
    st.session_state.drilldown_type = dd
    st.session_state.target_tab = tab
    st.rerun()

cols = st.columns(4)
# KPI 1: Gesamtbestand
with cols[0]:
    st.markdown(f'<div class="metric-card"><div class="metric-value">{kpis["total"]}</div><div class="metric-label">Anschlüsse</div><div class="metric-detail">Gesamtbestand</div></div>', unsafe_allow_html=True)
    if st.button("Details anzeigen", key="nav_total", use_container_width=True): navigate_to("📈 Strategische Analyse", "All")

# KPI 2: Kritisches Risiko (NAVIGATES TO MAP)
with cols[1]:
    st.markdown(f'<div class="metric-card" style="border-color:#ef4444;"><div class="metric-value" style="color:#ef4444;">{kpis["critical"]}</div><div class="metric-label">Kritisches Risiko</div><div class="metric-detail">Sofortiger Handlungsbedarf</div></div>', unsafe_allow_html=True)
    if st.button("Auf Karte zeigen", key="nav_crit", use_container_width=True): navigate_to("🗺️ Netz-Karte", "Critical")

# KPI 3: Überalterung
with cols[2]:
    st.markdown(f'<div class="metric-card"><div class="metric-value">{kpis["aging_30"]}</div><div class="metric-label">Überalterung</div><div class="metric-detail">> 30 Jahre Nutzungsdauer</div></div>', unsafe_allow_html=True)
    if st.button("Lebenszyklus-Details", key="nav_aging", use_container_width=True): navigate_to("🗺️ Netz-Karte", "Aging")

# KPI 4: Infrastruktur
with cols[3]:
    st.markdown(f'<div class="metric-card"><div class="metric-value">{kpis["unsuitable"]}</div><div class="metric-label">Infrastruktur</div><div class="metric-detail">Modernisierung nötig</div></div>', unsafe_allow_html=True)
    if st.button("Eignung prüfen", key="nav_infra", use_container_width=True): navigate_to("🗺️ Netz-Karte", "Unsuitable")

# --- Tabs (Programmatic) ---
tab_labels = ["📉 Strategische Analyse", "🗺️ Netz-Karte", "🛡️ Compliance & Daten", "🤖 AI -Assistent"]

# Inject CSS to style radio buttons to look like tabs
st.markdown("""
<style>
/* Make radio options horizontal */
div[data-testid="stRadio"] > div { flex-direction: row; gap: 0px; }
/* Each radio label styled as a tab */
div[data-testid="stRadio"] label {
    padding: 8px 16px;
    border-bottom: 3px solid transparent;
    color: #64748b;
    font-weight: 600;
    font-size: 14px;
    cursor: pointer;
    margin-bottom: 0;
    transition: color 0.15s ease;
}
div[data-testid="stRadio"] label:hover { color: #0f172a; }
/* Hide the actual radio circle (the SVG/span Streamlit injects) */
div[data-testid="stRadio"] label > div:first-child { display: none !important; }
/* Active tab: dark text + red underline (matching screenshot) */
div[data-testid="stRadio"] label:has(input:checked) {
    color: #0f172a !important;
    border-bottom: 3px solid #e53e3e !important;
}
</style>
""", unsafe_allow_html=True)

# Programmatic navigation sync for the radio button
if st.session_state.get("active_tab") not in tab_labels:
    st.session_state.active_tab = tab_labels[0]

active_tab = st.radio(
    "Navigation", 
    tab_labels, 
    key="navigation_tab_widget", 
    horizontal=True, 
    label_visibility="collapsed"
)

# Update canonical state if user manually interacted with the radio
if st.session_state.active_tab != active_tab:
    st.session_state.active_tab = active_tab
    st.rerun()

# Using a container to hold the active tab content
tab_container = st.container()

if active_tab == tab_labels[0]:
    with tab_container:
        # Professional Drilldown Logic for all 4 KPIs
        if st.session_state.drilldown_type != "None":
            st.markdown(f"### 📋 Detailansicht: {st.session_state.drilldown_type}")
            
            # Filter logic
            if st.session_state.drilldown_type == "Critical":
                view_df = df[df["Risiko"] == "Hoch"]
                title = "🚨 Hochrisiko-Assets (Sofortiger Handlungsbedarf)"
            elif st.session_state.drilldown_type == "Aging":
                view_df = df[df["Alter"] >= 30]
                title = "⏳ Überalterte Assets (>30 Jahre Nutzungsdauer)"
            elif st.session_state.drilldown_type == "Unsuitable":
                view_df = df[df["Infrastruktur_ungeeignet"] == True]
                title = "🔌 Ungeeignete Infrastruktur (Modernisierung für WP/Wallbox nötig)"
            else:
                view_df = df
                title = "📄 Gesamtbestand der Anschlüsse"

            st.info(f"**{title}** | Anzahl: {len(view_df)}")
            
            # Action Bar
            c1, c2 = st.columns([1, 5])
            with c1:
                if st.button("⬅️ Zur Übersicht", use_container_width=True):
                    st.session_state.drilldown_type = "None"
                    st.rerun()
            
            if not view_df.empty:
                # Table displayed using the pre-calculated Netz-Karte
                event = st.dataframe(
                    view_df[["Kundennummer", "Sparte", "Straße", "Hausnummer", "Werkstoff", "Alter", "Risiko", "Einbaujahr", "Netz-Karte", "lat", "lon"]],
                    column_config={
                        "Kundennummer": st.column_config.TextColumn("ID", width="small"),
                        "Sparte": st.column_config.TextColumn("Sparte", width="small"),
                        "Straße": st.column_config.TextColumn("Straße"),
                        "Alter": st.column_config.NumberColumn("Alter (J)", format="%d"),
                        "Risiko": st.column_config.SelectboxColumn("Risiko", options=["Hoch", "Mittel", "Niedrig", "Unbekannt"]),
                        "Netz-Karte": st.column_config.TextColumn("Netz-Karte (Mat/Dim)"),
                        "lat": None, "lon": None # Hide coordinates
                    },
                    width="stretch",
                    hide_index=True,
                    height=400,
                    key=f"editor_{st.session_state.drilldown_type}",
                    on_select="rerun",
                    selection_mode="single-row"
                )
                
                if event and event.selection.rows:
                    idx = event.selection.rows[0]
                    row = view_df.iloc[idx]
                    # Only navigate to map if coordinates are valid
                    if pd.notna(row["lat"]) and pd.notna(row["lon"]):
                        st.session_state.map_center = [row["lat"], row["lon"]]
                        st.session_state.map_zoom = 18
                        st.session_state.selected_customer_id = str(row["Kundennummer"])
                        navigate_to(tab_labels[1], st.session_state.drilldown_type)
                    else:
                        st.warning("⚠️ Dieser Anschluss hat keine validen Koordinaten für die Karte.")
            else:
                st.warning("Keine Daten für diese Auswahl gefunden.")

        else:
            # Standard Overview 
            st.markdown(f"### 📊 Strategische Übersicht: {selected_utility}")
            g1, g2 = st.columns(2)
            with g1:
                if not df.empty:
                    fig = px.histogram(df, x="Alter", color="Sparte", title="Altersstruktur der Infrastruktur", 
                                       template="plotly_white", barmode="group", color_discrete_map=COLORS,
                                       labels={"count": "Anzahl", "Sparte": "Versorgungsart"})
                    st.plotly_chart(fig, use_container_width=True)
            with g2:
                if not df.empty:
                    fig = px.pie(df, names="Risiko", title="Risiko-Verteilung (Asset-Zustand)", hole=0.6,
                                 template="plotly_white", color="Risiko", color_discrete_map=COLORS)
                    st.plotly_chart(fig, use_container_width=True)
            
            # Additional Charts
            st.divider()
            a1, a2 = st.columns(2)
            with a1:
                mat_df = get_material_distribution(df)
                if not mat_df.empty:
                    fig = px.line(mat_df, x="Einbaujahr", y="count", color="Werkstoff", 
                                  title="Historische Material-Nutzung", template="plotly_white", markers=True)
                    st.plotly_chart(fig, use_container_width=True)
            with a2:
                st.markdown("#### Strategische Bündelung & Eignung")
                suit_count = df.groupby(["Sparte", "Infrastruktur_ungeeignet"]).size().reset_index(name="Anzahl")
                suit_count["Eignung"] = suit_count["Infrastruktur_ungeeignet"].map({True: "Nachrüsten", False: "Bereit"})
                fig = px.bar(suit_count, x="Sparte", y="Anzahl", color="Eignung",
                             title="Bereitschaft für Energiewende (WP/EV)", template="plotly_white", barmode="group",
                             color_discrete_map={"Bereit": "#22c55e", "Nachrüsten": "#ef4444"})
                st.plotly_chart(fig, use_container_width=True)

elif active_tab == tab_labels[1]:
    with tab_container:
        st.markdown("### 🗺️ Geografische Risikomatrix")
        
        # Ensure coordinates are available
        map_df = df.dropna(subset=["lat", "lon"]).copy()
        
        # Filtering map data based on drilldown
        if st.session_state.drilldown_type == "Critical":
            map_df = map_df[map_df["Risiko"] == "Hoch"]
        elif st.session_state.drilldown_type == "Aging":
            map_df = map_df[map_df["Alter"] >= 30]
        elif st.session_state.drilldown_type == "Unsuitable":
            map_df = map_df[map_df["Infrastruktur_ungeeignet"] == True]
        
        if not map_df.empty:
            # Ensure numeric types
            map_df["lat"] = pd.to_numeric(map_df["lat"])
            map_df["lon"] = pd.to_numeric(map_df["lon"])
            
            c_map, c_list = st.columns([2.5, 1])
            
            with c_map:
                # Calculate Map Center
                center_lat, center_lon = map_df["lat"].mean(), map_df["lon"].mean()
                
                # FOCUS LOGIC: Use targeted coordinates if available
                m_lat = st.session_state.map_center[0] if st.session_state.map_center else center_lat
                m_lon = st.session_state.map_center[1] if st.session_state.map_center else center_lon
                m_zoom = st.session_state.map_zoom

                # Create Folium Map
                m = folium.Map(
                    location=[m_lat, m_lon], 
                    zoom_start=m_zoom,
                    tiles="OpenStreetMap",
                    control_scale=True
                )
                
                # Show Reset Button if focused
                if st.session_state.map_center:
                    if st.button("🗺️ Zoom zurücksetzen"):
                        st.session_state.map_center = None
                        st.session_state.map_zoom = 13
                        st.session_state.selected_customer_id = None
                        st.session_state.last_map_idx = None
                        st.rerun()
            
                # Use Marker Cluster for better performance/look with 300+ markers
                marker_cluster = MarkerCluster().add_to(m)
                
                # Color Mapping
                FO_COLORS = {"Hoch": "red", "Mittel": "orange", "Niedrig": "green", "Unbekannt": "blue"}
                
                # Add Markers to cluster
                for _, row in map_df.iterrows():
                    risk_status = str(row["Risiko"])
                    color = FO_COLORS.get(risk_status, "blue")
                    cust_id = str(row["Kundennummer"])
                    
                    # Professional Tooltip HTML
                    popup_content = f"""
                    <div style="font-family: 'Outfit', sans-serif; min-width: 220px; font-size: 13px;">
                        <h4 style="margin: 0 0 10px 0; color: #0f172a; border-bottom: 2px solid {color}; padding-bottom: 5px;">
                            {row['Sparte']} - {cust_id}
                        </h4>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr><td style="padding: 2px 0;"><b>📍 Ort:</b></td><td>{row['Straße']} {row['Hausnummer']}</td></tr>
                            <tr><td style="padding: 2px 0;"><b>🏗️ Material:</b></td><td>{row.get('Werkstoff', 'n/a')}</td></tr>
                            <tr><td style="padding: 2px 0;"><b>⏳ Alter:</b></td><td>{row['Alter']} Jahre</td></tr>
                            <tr><td style="padding: 2px 0;"><b>⚠️ Risiko:</b></td><td style="color: {color}; font-weight: bold;">{risk_status}</td></tr>
                        </table>
                    </div>
                    """
                    
                    folium.Marker(
                        location=[row["lat"], row["lon"]],
                        popup=folium.Popup(popup_content, max_width=350),
                        tooltip=f"{row['Sparte']} ({row['Straße']})",
                        icon=folium.Icon(color=color, icon="info-sign")
                    ).add_to(marker_cluster)

                    # HIGHLIGHT SELECTED CUSTOMER: Add a special red icon outside Cluster
                    if st.session_state.selected_customer_id == cust_id:
                        highlight_popup = f"""
                        <div style="font-family: 'Outfit', sans-serif; min-width: 250px; font-size: 13px;">
                            <h4 style="margin: 0 0 10px 0; color: #ef4444; border-bottom: 2px solid #ef4444; padding-bottom: 5px;">
                                ⭐ AUSGEWÄHLT: {cust_id}
                            </h4>
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr><td style="padding: 2px 0;"><b>📊 Sparte:</b></td><td>{row['Sparte']}</td></tr>
                                <tr><td style="padding: 2px 0;"><b>📍 Ort:</b></td><td>{row.get('Gemeinde', row.get('Ort', 'Wülfrath'))}</td></tr>
                                <tr><td style="padding: 2px 0;"><b>🏠 Adresse:</b></td><td>{row['Straße']} {row['Hausnummer']}</td></tr>
                                <tr><td style="padding: 2px 0;"><b>🏗️ Material:</b></td><td>{row.get('Werkstoff', 'n/a')}</td></tr>
                                <tr><td style="padding: 2px 0;"><b>⏳ Alter:</b></td><td>{row['Alter']} Jahre</td></tr>
                                <tr><td style="padding: 2px 0;"><b>⚠️ Risiko:</b></td><td style="color: {color}; font-weight: bold;">{risk_status}</td></tr>
                            </table>
                        </div>
                        """
                        folium.Marker(
                            location=[row["lat"], row["lon"]],
                            popup=folium.Popup(highlight_popup, max_width=350),
                            tooltip=f"KLICK FÜR DETAILS: {cust_id}",
                            icon=folium.Icon(color="red", icon="star", prefix="fa" if "fa" in "" else "glyphicon")
                        ).add_to(m)
                
                # Display map inside the c_map column
                st_folium(m, width="100%", height=700, key="main_network_map")
                
            with c_list:
                st.markdown(f"#### 📋 Anschluss-Verzeichnis ({len(map_df)})")
                event_map = st.dataframe(
                    map_df[["Kundennummer", "Sparte", "Straße", "Hausnummer", "Risiko", "Alter", "Netz-Karte", "lat", "lon"]],
                    column_config={
                        "Kundennummer": st.column_config.TextColumn("ID", width="small"),
                        "Risiko": st.column_config.SelectboxColumn("Risiko", options=["Hoch", "Mittel", "Niedrig", "Unbekannt"]),
                        "Alter": st.column_config.NumberColumn("Alt.", format="%d J."),
                        "Netz-Karte": st.column_config.TextColumn("Netz-Karte (Mat/Dim)"),
                        "lat": None, "lon": None # Hide coordinates
                    },
                    width="stretch",
                    hide_index=True,
                    height=650,
                    key="map_asset_list_v5",
                    on_select="rerun",
                    selection_mode="single-row"
                )
                
                if event_map and event_map.selection.rows:
                    idx = event_map.selection.rows[0]
                    # Only rerun if selection actually changed
                    if st.session_state.last_map_idx != idx:
                        row_map = map_df.iloc[idx]
                        if pd.notna(row_map["lat"]) and pd.notna(row_map["lon"]):
                            st.session_state.last_map_idx = idx
                            st.session_state.selected_customer_id = str(row_map["Kundennummer"])
                            st.session_state.map_center = [row_map["lat"], row_map["lon"]]
                            st.session_state.map_zoom = 18
                            st.rerun()
        else:
            st.warning("⚠️ **Keine Daten auf Karte anzeigbar.**")
            st.info("Bitte stellen Sie sicher, dass die Excel-Spalten für Latitude/Longitude ausgefüllt sind und klicken Sie in der Sidebar auf **'🔄 KI-Speicher aktualisieren'**.")

elif active_tab == tab_labels[2]:
    with tab_container:
        st.markdown("### 🛡️ Compliance-Audit")
        comp_df = df[df["Dokumente"] == "Lückenhaft"].copy()
        
        st.dataframe(
            comp_df,
            use_container_width=True,
            hide_index=True,
        )

elif active_tab == tab_labels[3]:
    with tab_container:
        st.markdown("### 🤖 AI -Assistent")
        
        col1, col2 = st.columns([2.5, 1.5])
        
        # Action Buttons Row
        with col1:
            st.markdown('<div class="small-btn-container">', unsafe_allow_html=True)
            btn_c1, _ = st.columns([2, 5])
            if btn_c1.button("🗑️ Chat löschen", use_container_width=True, help="Löscht den gesamten Chatverlauf"):
                st.session_state.history = []
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.markdown("**Strategische Analyse-vorgaben**")
            # Professional suggested queries in a scrollable container
            suggested_queries = [
                "Welche Hausanschlüsse sind älter als 10 Jahre?",
                "Bei welchen Anschlüssen fehlen wesentliche Dokumente?",
                "Welche Anschlussarten/Materialien wurden wann verbaut?",
                "Welche Hausanschlüsse haben erhöhtes Schadensrisiko?",
                "Zusammenhänge Baujahr, Material & Störungswahrscheinlichkeit?",
                "Welche Hausanschlüsse sollten bald erneuert werden?",
                "Welche Erneuerungen lassen sich bündeln?",
                "Welche Anschlüsse sind für Wärmepumpen/EV ungeeignet?",
                "Welche Muster fallen in den Hausanschlussakten auf?",
                "Welches Material hat welche Nutzungsdauer in Jahren?",
                "Welche Störungen sind an welchen Anschlüssen aufgetreten?",
                "Nach wie vielen Jahren Erneuerung für Sparte 10/Material?"
            ]
            
            with st.container(height=500):
                for q in suggested_queries:
                    if st.button(q, key=f"q_{q}", use_container_width=True):
                        st.session_state.history.append({"role": "user", "content": q})
                        with st.spinner("AI analysiert strategische Daten..."):
                            res = engine.answer_question(q, utility=selected_utility if selected_utility != "Alle Sparten" else None)
                            st.session_state.history.append({"role": "bot", "content": res["answer"]})
                            st.session_state.speak_text = res["answer"]
                            st.session_state.speak_id += 1
                            if "pending_action" in res:
                                 st.session_state.pending_action = res["pending_action"]
                        st.rerun()

        with col1:
            # Chat history in a scrollable container
            with st.container(height=500):
                if not st.session_state.history:
                    st.info("Willkommen! Wählen Sie eine Frage rechts aus oder tippen Sie unten eine eigene Anfrage.")
                else:
                    for msg in st.session_state.history:
                        div_class = "user-msg" if msg["role"] == "user" else "bot-msg"
                        st.markdown(f'<div class="{div_class}">{msg["content"]}</div>', unsafe_allow_html=True)
            
            # Render confirmation card OUTSIDE the scrollable container so buttons work
            if st.session_state.pending_action:
                pa = st.session_state.pending_action
                args = pa["args"]
                with st.container():
                    st.markdown(f"""
                    <div style="background:#fff7ed; border:2px solid #fdba74; padding:15px; border-radius:12px; margin-top:10px;">
                        <h5 style="margin:0; color:#9a3412;">🛠️ Daten-Aktualisierung bestätigen</h5>
                        <p style="font-size:13px; margin:8px 0;">Soll folgende Änderung gespeichert werden?</p>
                        <ul style="font-size:13px; margin:0; padding-left:20px;">
                            <li><b>Kunde:</b> {args.get('customer_id')}</li>
                            <li><b>Feld:</b> {args.get('field_name')}</li>
                            <li><b>Neuer Wert:</b> {args.get('new_value')}</li>
                            <li><b>Sparte:</b> {args.get('utility')}</li>
                        </ul>
                    </div>
                    """, unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                if c1.button("✅ Bestätigen & Speichern", use_container_width=True, type="primary"):
                    from geo_utils import update_excel_record
                    success = update_excel_record(
                        args.get("customer_id"), 
                        args.get("utility"), 
                        args.get("field_name"), 
                        args.get("new_value")
                    )
                    if success:
                        st.success("✅ Daten erfolgreich aktualisiert!")
                        st.session_state.history.append({"role": "bot", "content": "✅ Die Daten wurden erfolgreich im Excel-System aktualisiert."})
                        st.session_state.pending_action = None
                        st.cache_resource.clear()
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("Fehler beim Aktualisieren. Prüfen Sie ob die Datei geöffnet ist.")
                        st.warning(f"Debug: ID={args.get('customer_id')}, Feld={args.get('field_name')}, Sparte={args.get('utility')}")
                
                if c2.button("❌ Abbrechen", use_container_width=True):
                    st.session_state.pending_action = None
                    st.session_state.history.append({"role": "bot", "content": "Die Aktualisierung wurde abgebrochen."})
                    st.rerun()
        # Floating Voice Input & Stop Button
        with st.container():
            st.markdown('<div style="position:fixed; bottom:75px; right:70px; font-size:10px; color:#64748b; z-index:1001;">Click to Talk</div>', unsafe_allow_html=True)
            # Create a small floating container for both buttons
            st.markdown("""
                <style>
                .floating-controls {
                    position: fixed;
                    bottom: 20px;
                    right: 20px;
                    z-index: 1000;
                    display: flex;
                    gap: 5px !important;
                    align-items: center;
                    background: white;
                    padding: 8px 12px;
                    border-radius: 50px;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                    border: 1px solid #e2e8f0;
                }
                </style>
            """, unsafe_allow_html=True)
            
            # Using columns inside a div for the floating effect
            f_col1, f_col2 = st.columns([1, 1])
            with st.sidebar: # Temporary anchor
                pass 
                
            # Direct placement in the flow, style will handle float
            st.markdown('<div class="floating-controls small-btn-container">', unsafe_allow_html=True)
            col_v1, col_v2 = st.columns([0.4, 2.6])
            with col_v1:
                audio = mic_recorder(start_prompt="🎙️", stop_prompt="⏹️", just_once=True, key="mic_recorder")
            with col_v2:
                if st.button("🛑 Sprachausgabe stoppen", key="stop_voice_floating"):
                    st.session_state.speak_text = ""
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            if audio:
                with st.spinner("Transkribiere..."):
                    res_voice = engine.transcribe_audio(audio['bytes'])
                    
                    # Resilience: Handle cases where engine is still old cache (returning str or None)
                    if isinstance(res_voice, dict) and res_voice.get("ok"):
                        transcription = res_voice["text"]
                        st.session_state.history.append({"role": "user", "content": transcription})
                        with st.spinner("KI verarbeitet Sprachbefehl..."):
                            res = engine.answer_question(transcription, utility=selected_utility if selected_utility != "Alle Sparten" else None)
                            st.session_state.history.append({"role": "bot", "content": res["answer"]})
                            st.session_state.speak_text = res["answer"]
                            st.session_state.speak_id += 1
                            if "pending_action" in res:
                                 st.session_state.pending_action = res["pending_action"]
                        st.rerun()
                    elif isinstance(res_voice, str): # Legacy compatibility if cache is stuck
                        transcription = res_voice
                        st.session_state.history.append({"role": "user", "content": transcription})
                        res = engine.answer_question(transcription, utility=selected_utility if selected_utility != "Alle Sparten" else None)
                        st.session_state.history.append({"role": "bot", "content": res["answer"]})
                        st.session_state.speak_text = res["answer"]
                        st.session_state.speak_id += 1
                        if "pending_action" in res:
                                 st.session_state.pending_action = res["pending_action"]
                        st.rerun()
                    else:
                        error_msg = res_voice["text"] if isinstance(res_voice, dict) else "Unbekannter Fehler oder Cache-Konflikt."
                        st.warning(f"⚠️ **Spracherkennung fehlgeschlagen:** {error_msg}")
                        st.info("💡 **Tipp:** Bitte nutzen Sie links 'KI-Speicher aktualisieren' falls der Fehler bleibt.")

        if user_p := st.chat_input("Fragen Sie den AI-Assistenten nach Materialien, Risiken oder Objekt-Details..."):
            st.session_state.history.append({"role": "user", "content": user_p})
            with st.spinner("KI verarbeitet Anfrage..."):
                res = engine.answer_question(user_p, utility=selected_utility if selected_utility != "Alle Sparten" else None)
                st.session_state.history.append({"role": "bot", "content": res["answer"]})
                st.session_state.speak_text = res["answer"]
                st.session_state.speak_id += 1
                if "pending_action" in res:
                     st.session_state.pending_action = res["pending_action"]
            st.rerun()

# ─────────────── Auto-Playback Trigger ────────────────────────────────
if st.session_state.speak_text:
    play_audio(st.session_state.speak_text)
    st.session_state.speak_text = "" # Clear after playing to prevent re-playing on subsequent reruns