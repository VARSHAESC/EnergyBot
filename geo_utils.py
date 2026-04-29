# -*- coding: utf-8 -*-
"""
geo_utils.py — Data loader and geospatial utilities.
"""
import os
import re
import json
import pandas as pd
import numpy as np
from datetime import datetime
from schema_map import normalise_columns, validate_required_columns

# ── Paths ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
_env_data_file = os.environ.get("DATA_FILE", "")
EXCEL_FILE = (
    os.path.join(BASE_DIR, _env_data_file)
    if _env_data_file
    else os.path.join(BASE_DIR, "data", "stadtwerke_synthetic_2300rows.xlsx")
)
# Legacy fallback: if the resolved path doesn't exist, try the old location or scan the mount
if not os.path.exists(EXCEL_FILE):
    # Try the standard mount path
    _mount_dir = os.path.join(BASE_DIR, "excel_data")
    if os.path.exists(_mount_dir):
        # Scan for any .xlsx file in the mount directory
        xlsx_files = [f for f in os.listdir(_mount_dir) if f.endswith(".xlsx")]
        if xlsx_files:
            EXCEL_FILE = os.path.join(_mount_dir, xlsx_files[0])
            print(f"DEBUG: Found data file in mount: {EXCEL_FILE}")
    
    # Final legacy check
    if not os.path.exists(EXCEL_FILE):
        _legacy = os.path.join(BASE_DIR, "excel_data", "Hausanschluss_data.xlsx")
        if os.path.exists(_legacy):
            EXCEL_FILE = _legacy
DEFAULT_EXCEL_PATH = EXCEL_FILE  # Alias for compatibility
GEO_CACHE_FILE = os.path.join(BASE_DIR, "cache", "geo_cache.json")
ALL_UTILITIES = ["Gas", "Wasser", "General"]
CSV_FILES = {u: EXCEL_FILE for u in ALL_UTILITIES}

import time

# ── Performance Cache ──────────────────────────────────────────────────
_DATA_CACHE = {
    "raw": None,
    "mtime": 0,
    "last_check": 0,
    "utilities": {},
    "unified": None,
    "kpis": {}
}
CACHE_TTL = 300  # 5 minutes

def _invalidate_cache():
    global _DATA_CACHE
    _DATA_CACHE["raw"] = None
    _DATA_CACHE["utilities"].clear()
    _DATA_CACHE["unified"] = None
    _DATA_CACHE["kpis"].clear()

def _get_raw_data():
    global _DATA_CACHE
    if not os.path.exists(EXCEL_FILE):
        return pd.DataFrame()
    
    current_time = time.time()
    
    # Check TTL to avoid hammering the disk with os.path.getmtime
    if _DATA_CACHE["raw"] is not None and (current_time - _DATA_CACHE["last_check"] < CACHE_TTL):
        return _DATA_CACHE["raw"]
        
    mtime = os.path.getmtime(EXCEL_FILE)
    if _DATA_CACHE["raw"] is not None and _DATA_CACHE["mtime"] == mtime:
        _DATA_CACHE["last_check"] = current_time
        return _DATA_CACHE["raw"]
    
    # Cache miss or file changed
    try:
        df = pd.read_excel(EXCEL_FILE, header=0, engine="openpyxl")
        df = normalise_columns(df)
        _invalidate_cache() # Clear downstream caches
        _DATA_CACHE["raw"] = df
        _DATA_CACHE["mtime"] = mtime
        _DATA_CACHE["last_check"] = current_time
        return df
    except Exception:
        return pd.DataFrame()

MATERIAL_LIFESPAN = {
    "PE-HD": 50, "PE": 50, "PE100": 50, "PVC": 40,
    "Kupfer": 60, "Stahl": 65, "Grauguss": 80, "Duktilguss": 80,
    "Gusseisen": 80, "Kunststoff": 40, "HDPE": 50,
    "AL": 45, "Kabel": 45, "NYY": 45
}

RISK_LADDER = {
    "Gas": [
        {"material": "Stahl mit KKS", "gut": 59, "mittel": 95, "life": 80},
        {"material": "Stahl ohne KKS", "gut": 51, "mittel": 83, "life": 70},
        {"material": "PE", "gut": 55, "mittel": 89, "life": 75},
        # Fallback for generic 'Stahl' in Gas
        {"material": "Stahl", "gut": 51, "mittel": 83, "life": 70}, 
    ],
    "Wasser": [
        {"material": "Asbestzement-(AZ)", "gut": 36, "mittel": 59, "life": 50},
        {"material": "AZ", "gut": 36, "mittel": 59, "life": 50},
        {"material": "Asbest", "gut": 36, "mittel": 59, "life": 50},
        {"material": "PE", "gut": 62, "mittel": 101, "life": 85},
        {"material": "PVC", "gut": 36, "mittel": 59, "life": 50},
        {"material": "Stahl", "gut": 44, "mittel": 71, "life": 60},
    ],
    "Strom": [
        {"material": "Kabel", "gut": 35, "mittel": 50, "life": 45},
        {"material": "AL", "gut": 35, "mittel": 50, "life": 45},
        {"material": "NYY", "gut": 35, "mittel": 50, "life": 45},
    ]
}

def _get_risk_profile(sparte: str, material: str):
    material_lower = str(material).lower()
    if sparte in RISK_LADDER:
        for profile in RISK_LADDER[sparte]:
            if profile["material"].lower() in material_lower:
                return profile
    return None

CURRENT_YEAR = datetime.now().year

def _fix_encoding(s: str) -> str:
    """Clean up strings from Excel artifacts aggressively using unicode escapes."""
    if not isinstance(s, str): return str(s)
    
    # Standardize most common artifacts
    s = s.replace('\ufffd', 'ü') # Default fallback
    
    # Specific German fixes
    replacements = {
        'Stra' + chr(0xfffd) + 'e': 'Straße',
        'Strae': 'Straße',
        'Strasse': 'Straße',
        'Gre': 'Größe',
        'Gr' + chr(0xfffd) + 'e': 'Größe',
        'Lngengrad': 'Längengrad',
        'L' + chr(0xfffd) + 'ndengrad': 'Längengrad',
        'Kundenname': 'Kundenname'
    }
    for old, new in replacements.items():
        s = s.replace(old, new)
        
    # Standardize remaining fallback artifacts
    s = s.replace('\ufffd', 'ü')
    s = s.replace('Strae', 'Straße')
    
    s = s.replace('\x00', '')
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def _parse_date(val) -> pd.Timestamp:
    if pd.isna(val): return pd.NaT
    if isinstance(val, datetime): return pd.Timestamp(val)
    s = str(val).strip()
    if not s or s.lower() == "nan": return pd.NaT
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y"):
        try: return pd.to_datetime(s, format=fmt)
        except: pass
    return pd.NaT

def _infer_risk(row: pd.Series, sparte: str) -> str:
    age = row.get("Alter", 0)
    material = str(row.get("Werkstoff", "")).strip()
    if not age or pd.isna(age): return "Unbekannt"
    age = float(age)

    # Use granular risk ladder if available
    profile = _get_risk_profile(sparte, material)
    if profile:
        if age <= profile["gut"]: return "Niedrig"
        elif age <= profile["mittel"]: return "Mittel"
        else: return "Hoch"

    # Fallback to general logic
    lifespan = MATERIAL_LIFESPAN.get(material, 50)
    pct = age / lifespan
    if pct >= 0.85: return "Hoch"
    if pct >= 0.65: return "Mittel"
    return "Niedrig"

def _erneuerung_jahr(row: pd.Series, sparte: str) -> object:
    einbau = row.get("Einbaudatum", pd.NaT)
    material = str(row.get("Werkstoff", "")).strip()
    if pd.isna(einbau): return None
    
    profile = _get_risk_profile(sparte, material)
    lifespan = profile["life"] if profile else MATERIAL_LIFESPAN.get(material, 50)
    
    try: return int(einbau.year + lifespan)
    except: return None

def _docs_complete(row: pd.Series) -> str:
    doc_cols = [c for c in row.index if any(k in str(c).lower() for k in ["gestattung", "auftrag", "anfrage"])]
    if not doc_cols: return "Vollständig"
    missing = [c for c in doc_cols if pd.isna(row[c])]
    return "Lückenhaft" if missing else "Vollständig"

def _is_unsuitable_infrastructure(row: pd.Series, sparte: str) -> bool:
    """Checks if infrastructure needs modernization based purely on technical life table."""
    age = row.get("Alter", 0)
    if not age or pd.isna(age): return False
    
    material = str(row.get("Werkstoff", "")).strip()
    profile = _get_risk_profile(sparte, material)
    
    lifespan = profile["life"] if profile else MATERIAL_LIFESPAN.get(material, 50)
    return float(age) > lifespan

# ── Geodata logic ──────────────────────────────────────────────────────
def get_coordinates(row: pd.Series) -> tuple:
    """Gets coordinates from new explicit columns or UTM fallback."""
    # Find columns by keyword to be robust against encoding issues (e.g. Längengrad vs Lngengrad)
    lat_col = next((c for c in row.index if "Latitude" in str(c)), None)
    lon_col = next((c for c in row.index if "Longitude" in str(c)), None)
    
    lat = row.get(lat_col) if lat_col else None
    lon = row.get(lon_col) if lon_col else None
    
    # Check if they are valid numbers
    try:
        if pd.notna(lat) and pd.notna(lon):
            return float(lat), float(lon)
    except: pass

    # Fallback to UTM (Hochwert/Rechtswert) if they look like UTM
    hw = row.get("Hochwert Objekt")
    rw = row.get("Rechtswert Objekt")
    if pd.notna(hw) and pd.notna(rw) and rw < 2000000:
        # Transformation for UTM Zone 32N / Germany
        lat_calc = 48.0 + (hw - 5300000) / 111111
        lon_calc = 9.0 + (rw - 500000) / (111111 * 0.65)
        return lat_calc, lon_calc
    
    return None, None

def load_excel(path=EXCEL_FILE, header=0):
    if path == EXCEL_FILE:
        return _get_raw_data()
    if not os.path.exists(path): return pd.DataFrame()
    df = pd.read_excel(path, header=header, engine="openpyxl")
    df = normalise_columns(df)
    return df

def _has_actual_connection(row: dict, sparte: str) -> bool:
    """True only if this property has an actual installation for the given utility."""
    col = f"{sparte} Einbaudatum/ Fertigmeldung"
    val = row.get(col)
    return val is not None and str(val).strip() not in ("", "nan", "NaT", "None", "NaN")


def get_utility_df(utility: str) -> pd.DataFrame:
    global _DATA_CACHE
    raw = _get_raw_data()
    if raw.empty: return pd.DataFrame()

    if utility in _DATA_CACHE["utilities"]:
        return _DATA_CACHE["utilities"][utility]

    # Fix 2.4: drop permanently null columns
    cols_to_drop = ["Zusatz"]
    raw_clean = raw.drop(columns=[c for c in cols_to_drop if c in raw.columns])

    # Identify utility-specific columns
    common_cols = []
    util_cols = []
    for c in raw_clean.columns:
        c_l = str(c).lower()
        if c_l.startswith(utility.lower()):
            util_cols.append(c)
        elif not any(c_l.startswith(u.lower()) for u in ALL_UTILITIES):
            common_cols.append(c)

    # Check for a "Sparte" column first
    sparte_col = next((c for c in raw_clean.columns if str(c).lower() in ["sparte", "medium", "typ"]), None)
    
    if sparte_col:
        # Filter rows by the value in the "Sparte" column
        df = raw_clean[raw_clean[sparte_col].astype(str).str.lower().str.contains(utility.lower())].copy()
    elif not util_cols:
        # Fallback: If no specific utility columns and no Sparte column, treat as General
        df = raw_clean.copy()
    else:
        df = raw_clean[common_cols + util_cols].copy()

    # Optimized connection detection (Vectorized)
    conn_col = f"{utility} Einbaudatum/ Fertigmeldung"
    if conn_col in raw.columns:
        # Treat various null-like strings as actual NaTs
        has_connection = raw[conn_col].astype(str).str.strip().replace(
            ["", "nan", "NaT", "None", "NaN", "0"], pd.NA
        ).notna()
    else:
        has_connection = pd.Series(False, index=raw.index)

    # Connection check: only filter if it's a specific utility with a known connection column
    if utility != "General" and conn_col in raw.columns:
        df = df[has_connection].copy()
    
    if df.empty: return pd.DataFrame()
    
    # Cleaning column names
    new_cols = []
    for c in df.columns:
        c_clean = str(c).strip()
        if c_clean.lower().startswith(utility.lower()):
            c_clean = c_clean[len(utility):].strip()
        c_clean = _fix_encoding(c_clean)
        new_cols.append(c_clean)
    df.columns = new_cols
    
    # Rename for consistency (all column names already stripped of whitespace)
    renames = {
        "Kundenname": "Kundenname",
        "Kunden Name": "Kundenname",
        "Kunden": "Kundenname",
        "Objekt-ID (Nummer bspw.)": "Kundennummer",
        "Objekt-ID": "Kundennummer",
        "Einbaudatum/ Fertigmeldung": "Einbaudatum",
        "Werkstoff Anschlussleitung": "Werkstoff",
        "Kabeltyp AL": "Werkstoff",
        "Dimension Anschlussleitung": "Dimension",
        "Querschnitt AL": "Dimension",
        "Querschnitt AL (mm²)": "Dimension",
        "Strae": "Straße", "Strasse": "Straße", "Straße": "Straße",
        "Anschlusslänge Hausanschluss": "Länge",
        "Länge Anschlussleitung": "Länge",
    }
    
    final_cols = []
    for c in df.columns:
        found = False
        # Prioritize exact or more specific matches
        for k, v in renames.items():
            if k == c: # Exact match
                final_cols.append(v); found = True; break
        
        if not found:
            for k, v in renames.items():
                if k in c and v not in final_cols: # Substring match (fallback)
                    final_cols.append(v); found = True; break
        
        if not found: final_cols.append(c)
    df.columns = final_cols
    
    df["Sparte"] = utility
    
    # Extract coordinates.
    # normalise_columns() may have already renamed Breitengrad (Latitude) → lat.
    # If so, use those values directly; get_coordinates() would return None because
    # it searches for "Latitude" in the column name which no longer exists.
    if "lat" in df.columns and "lon" in df.columns and df["lat"].notna().any():
        df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
        df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    else:
        coords = df.apply(get_coordinates, axis=1)
        df["lat"] = coords.apply(lambda x: x[0])
        df["lon"] = coords.apply(lambda x: x[1])

    # ── Final Cleaning ──
    # Clean all string values in the dataframe to handle encoding artifacts
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].apply(lambda x: _fix_encoding(x) if isinstance(x, str) else x)

    if "Einbaudatum" in df.columns:
        df["Einbaudatum"] = df["Einbaudatum"].apply(_parse_date)
        df["Einbaujahr"] = df["Einbaudatum"].dt.year
        df["Alter"] = df["Einbaujahr"].apply(lambda y: CURRENT_YEAR - y if pd.notna(y) else 0)
    
    df["Risiko"] = df.apply(lambda r: _infer_risk(r, utility), axis=1)
    df["Erneuerung_empfohlen_bis"] = df.apply(lambda r: _erneuerung_jahr(r, utility), axis=1)
    df["Dokumente"] = df.apply(_docs_complete, axis=1)
    df["Infrastruktur_ungeeignet"] = df.apply(lambda r: _is_unsuitable_infrastructure(r, utility), axis=1)

    # Fix 2.5: flag records missing their inspection date (critical compliance field)
    def _missing_inspection(row: pd.Series) -> bool:
        val = row.get("(Letztes) Inspektionsdatum")  # prefix stripped by rename loop above
        return val is None or str(val).strip() in ("", "nan", "NaT", "None", "NaN")

    df["missing_inspection"] = df.apply(_missing_inspection, axis=1)
    
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    
    # Store in cache
    _DATA_CACHE["utilities"][utility] = df
    return df

def get_unified_df() -> pd.DataFrame:
    global _DATA_CACHE
    if _DATA_CACHE["unified"] is not None:
        return _DATA_CACHE["unified"]
        
    dfs = [get_utility_df(u) for u in ALL_UTILITIES]
    valid_dfs = [d for d in dfs if not d.empty]
    if not valid_dfs: return pd.DataFrame()
    
    unified = pd.concat(valid_dfs, ignore_index=True)
    _DATA_CACHE["unified"] = unified
    return unified

def kpi_advanced(df: pd.DataFrame) -> dict:
    if df.empty: return {k: 0 for k in ["total", "critical", "aging_30", "aging_40", "renewal_soon", "unsuitable", "over_lifespan"]}
    total = len(df)
    critical = int(df["Risiko"].eq("Hoch").sum())
    aging_30 = int(df["Alter"].ge(30).sum()) if "Alter" in df.columns else 0
    aging_40 = int(df["Alter"].ge(40).sum()) if "Alter" in df.columns else 0
    missing_docs = int(df["Dokumente"].eq("Lückenhaft").sum())
    unsuitable = int(df.get("Infrastruktur_ungeeignet", pd.Series([0]*total)).sum())
    over_lifespan = int((df["Erneuerung_empfohlen_bis"] < CURRENT_YEAR).sum()) if "Erneuerung_empfohlen_bis" in df.columns else 0
    return {
        "total": total, "critical": critical, "aging_30": aging_30, "aging_40": aging_40,
        "missing_docs": missing_docs, "doc_complete_pct": round(100*(total-missing_docs)/max(total,1), 1),
        "unsuitable": unsuitable,
        "avg_age": df["Alter"].mean() if "Alter" in df.columns else 0,
        "high_risk_pct": round(100 * critical / max(total, 1), 1),
        "renewal_soon": int(df["Erneuerung_empfohlen_bis"].dropna().apply(lambda x: x <= CURRENT_YEAR + 10).sum()) if "Erneuerung_empfohlen_bis" in df.columns else 0,
        "over_lifespan": over_lifespan
    }

def get_material_distribution(df: pd.DataFrame):
    if "Werkstoff" not in df.columns or "Einbaujahr" not in df.columns: return pd.DataFrame()
    return df.groupby(["Einbaujahr", "Werkstoff"]).size().reset_index(name="count")

def get_bundling_potential(df: pd.DataFrame):
    if "Straße" not in df.columns: return pd.DataFrame()
    critical_streets = df[df["Alter"] > 35].groupby("Straße").agg({"Alter": "mean", "Sparte": "count"}).rename(columns={"Sparte": "Anzahl"})
    return critical_streets.sort_values("Anzahl", ascending=False).head(10)

def invalidate_cache():
    import streamlit as st
    st.cache_data.clear()
    st.cache_resource.clear()

# ── Dynamic GeoJSON Regeneration ─────────────────────────────────────────
GEOJSON_FILE = os.path.join(BASE_DIR, "excel_data", "utility_networks.geojson")

# Entry stations (supply points) for the network topology
_STATIONS = {
    "Stadtnetz": [
        {"name": "Hammerstein",  "lat": 51.2880, "lon": 7.0550},
        {"name": "Kocherscheidt","lat": 51.2810, "lon": 7.0450},
    ],
    "Ortsteilnetz": [
        {"name": "Rohdenhaus", "lat": 51.2950, "lon": 7.0600},
    ]
}

def is_geojson_stale() -> bool:
    """Return True if the GeoJSON is missing or older than the Excel file."""
    if not os.path.exists(GEOJSON_FILE):
        return True
    if not os.path.exists(EXCEL_FILE):
        return False
    return os.path.getmtime(EXCEL_FILE) > os.path.getmtime(GEOJSON_FILE)

def _osrm_route(p1, p2):
    import requests, time as _time
    coords = f"{p1[0]},{p1[1]};{p2[0]},{p2[1]}"
    url = (f"http://router.project-osrm.org/route/v1/driving/{coords}"
           f"?overview=full&geometries=geojson")
    try:
        for _ in range(2):
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                d = r.json()
                if d.get("code") == "Ok":
                    return d["routes"][0]["geometry"]["coordinates"]
            _time.sleep(0.5)
    except Exception:
        pass
    return [p1, p2]   # straight-line fallback

def _build_mst_edges(points):
    """Return edges of the Minimum Spanning Tree for the given list of [lon,lat] points."""
    from scipy.spatial.distance import pdist, squareform
    from scipy.sparse.csgraph import minimum_spanning_tree
    if len(points) < 2:
        return []
    arr = np.array(points)
    mst = minimum_spanning_tree(squareform(pdist(arr)))
    cx = mst.tocoo()
    return [(points[i], points[j]) for i, j in zip(cx.row, cx.col)]

def _offset_polyline(coords, offset_dist):
    """Shift a polyline perpendicularly by offset_dist degrees (approx)."""
    if offset_dist == 0 or len(coords) < 2:
        return coords
    out = []
    for i in range(len(coords)):
        if i == 0:
            v1, v2 = np.array(coords[i]), np.array(coords[i + 1])
        elif i == len(coords) - 1:
            v1, v2 = np.array(coords[i - 1]), np.array(coords[i])
        else:
            v1, v2 = np.array(coords[i - 1]), np.array(coords[i + 1])
        direction = v2 - v1
        dist = np.linalg.norm(direction)
        if dist == 0:
            out.append(coords[i])
            continue
        perp = np.array([-direction[1], direction[0]]) / dist
        out.append((np.array(coords[i]) + perp * offset_dist).tolist())
    return out

def _osrm_nearest_best(house_pt):
    """
    Find the best junction point on the road for a house by checking
    multiple nearby road segments and picking the one that is truly 'in front'.
    """
    import requests
    # Get top 5 nearest road waypoints to increase chance of finding the parallel street
    url = f"http://router.project-osrm.org/nearest/v1/driving/{house_pt[0]},{house_pt[1]}?number=10"
    try:
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            d = r.json()
            if d.get("code") == "Ok":
                # Find the one that is geographically closest to being perpendicular
                # We pick the point that is simply the closest to the house
                # OSRM's 'nearest' already sorts by distance, but we want to make sure
                # we don't pick a point that is 'closer' but on a different road or behind houses.
                # Actually, the first result is usually the closest.
                # The issue before was that OSRM snapped to a junction.
                # Let's try to pick a point that isn't a junction if possible, or just the best one.
                return d["waypoints"][0]["location"]
    except: pass
    return house_pt

def _features_for_utility(utility: str) -> list:
    """
    Build GeoJSON features using a refined Star Topology.
    Strategy: 
    1. Route from each house to its nearest supply station via OSRM.
    2. Project the house onto ALL segments of the road route to find the 
       geographically closest junction point on the street.
    3. Ensure all features have 6 keys for Folium compatibility.
    """
    df = get_utility_df(utility)
    if df.empty: return []
    df = df.dropna(subset=["lat", "lon"]).copy()
    if df.empty: return []

    all_stations = []
    for zone, s_list in _STATIONS.items():
        for s in s_list:
            all_stations.append({**s, "zone": zone})

    OFFSET = {"Gas": -0.000035, "Wasser": 0.0, "Strom": 0.000035}
    offset = OFFSET.get(utility, 0)
    DIM_MAIN, DIM_LAT = ({"Gas":"DN 150","Wasser":"DN 150","Strom":"110kV"}, {"Gas":"DN 40","Wasser":"DN 32","Strom":"400V"})
    MAT_MAIN, MAT_LAT = ({"Gas":"PE-HD","Wasser":"GG","Strom":"Kabel"}, {"Gas":"PE-HD","Wasser":"PE","Strom":"NYY-J"})

    features = []

    def project_point_to_line(pt, v, w):
        v, w, pt = np.array(v), np.array(w), np.array(pt)
        l2 = np.sum((w-v)**2)
        if l2 == 0: return v.tolist()
        t = max(0, min(1, np.dot(pt-v, w-v)/l2))
        return (v + t*(w-v)).tolist()

    for _, row in df.iterrows():
        h_lat, h_lon = float(row["lat"]), float(row["lon"])
        risk = str(row.get("Risiko", "Unbekannt"))
        house_pt = [h_lon, h_lat]

        # ── 1. Nearest Station ────────────────────────────────────────
        nearest = min(all_stations, key=lambda s: (h_lat-s["lat"])**2 + (h_lon-s["lon"])**2)
        station_pt = [nearest["lon"], nearest["lat"]]
        zone = nearest["zone"]

        # ── 2. Route via OSRM ─────────────────────────────────────────
        road_route = _osrm_route(station_pt, house_pt)
        if offset != 0: road_route = _offset_polyline(road_route, offset)

        # ── 3. Find Absolute Best Junction (90 deg) ───────────────────
        # We project the house onto EVERY segment of the road route
        best_dist = float('inf')
        best_snap = road_route[-1]
        best_idx  = len(road_route) - 2

        if len(road_route) >= 2:
            for i in range(len(road_route)-1):
                proj = project_point_to_line(house_pt, road_route[i], road_route[i+1])
                d = (house_pt[0]-proj[0])**2 + (house_pt[1]-proj[1])**2
                if d < best_dist:
                    best_dist = d
                    best_snap = proj
                    best_idx = i
        
        main_coords = road_route[:best_idx+1] + [best_snap]
        
        # Offset the house point as well so the entire lateral is separated
        # We use a MUCH smaller shift at the house (10%) to keep it on the same building
        # while keeping the full offset at the street side.
        house_offset = offset * 0.1
        final_house_pt = [house_pt[0] + house_offset, house_pt[1] + house_offset]
        lateral_coords = [best_snap, final_house_pt]

        # Extract pipe length if available
        p_length = row.get("Länge", 0)
        try:
            # Handle potential non-numeric values
            p_length = float(str(p_length).replace(",", ".")) if pd.notna(p_length) else 0
        except:
            p_length = 0

        # ── 4. Build Features ─────────────────────────────────────────
        # All features MUST have these 6 keys to avoid Folium Tooltip crashes
        base = {
            "utility": utility, 
            "network": zone, 
            "risiko": risk,
            "material": "N/A",
            "dimension": "N/A"
        }
        
        # Main pipe
        mp = base.copy()
        mp.update({
            "type": "Main Pipe", 
            "material": MAT_MAIN.get(utility, "N/A"), 
            "dimension": DIM_MAIN.get(utility, "N/A"),
            "risiko": "N/A"
        })
        features.append({"type":"Feature", "properties":mp, "geometry":{"type":"LineString", "coordinates":main_coords}})
        base = {
            "utility": utility, 
            "network": zone, 
            "risiko": risk,
            "type": "Lateral",
            "material": MAT_LAT.get(utility, "n/a"),
            "dimension": DIM_LAT.get(utility, "n/a"),
            "length": f"{p_length:.1f} m" if p_length > 0 else "n/a"
        }
        features.append({"type":"Feature", "properties":base, "geometry":{"type":"LineString", "coordinates":lateral_coords}})
        
        # Connection Node
        cn = base.copy()
        cn.update({"type": "Connection Node", "material":"N/A", "dimension":"N/A"})
        features.append({"type":"Feature", "properties":cn, "geometry":{"type":"Point", "coordinates":best_snap}})
        
        # House Node
        hn = base.copy()
        hn.update({"type": "Node", "material":"N/A", "dimension":"N/A"})
        features.append({"type":"Feature", "properties":hn, "geometry":{"type":"Point", "coordinates":final_house_pt}})

    return features

def regenerate_network_geojson(utilities=None) -> int:
    """
    Re-generate utility_networks.geojson from the current Excel data.
    Returns the number of GeoJSON features written.
    Only utilities with at least one valid customer row are included.
    """
    if utilities is None:
        utilities = ALL_UTILITIES
    all_features = []
    for u in utilities:
        all_features.extend(_features_for_utility(u))

    geojson = {"type": "FeatureCollection", "features": all_features}
    os.makedirs(os.path.dirname(GEOJSON_FILE), exist_ok=True)
    with open(GEOJSON_FILE, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
    return len(all_features)

# ── Helper for 2_Map.py compatibility ───────────────────────────────────
def attach_geo_from_columns(df: pd.DataFrame) -> tuple:
    coords = df.apply(get_coordinates, axis=1)
    df["__lat"] = coords.apply(lambda x: x[0])
    df["__lon"] = coords.apply(lambda x: x[1])
    has_geo = df["__lat"].notna().any()
    return df, has_geo

def geocode_missing_coords(df: pd.DataFrame) -> tuple:
    # Minimal mock for compatibility
    return df, df["__lat"].notna().any()

def pick_col(df, options):
    for o in options:
        if o in df.columns: return o
    return None

def classify_priority(df):
    if "Risiko" in df.columns:
        return df["Risiko"].map({"Hoch": "critical", "Mittel": "warning", "Niedrig": "normal"}).fillna("normal")
    return pd.Series(["normal"] * len(df))

def apply_filters_case_insensitive(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    dff = df.copy()
    for col, val in filters.items():
        if col in dff.columns and val:
            dff = dff[dff[col].astype(str).str.lower() == str(val).lower()]
    return dff

def update_excel_record(customer_id: str, utility: str, field: str, new_value: str) -> bool:
    """
    Updates a specific record in the source Excel file.
    Returns True on success, False otherwise.
    """
    if not os.path.exists(EXCEL_FILE): return False
    
    try:
        df_raw = pd.read_excel(EXCEL_FILE)
        
        # 1. Find the best matching column using smart fuzzy search
        # This handles ALL columns automatically:
        #   - Shared fields (Hausnummer, Straße, Gemeinde, etc.)
        #   - Utility-specific fields (Gas Schutzrohr, Wasser Werkstoff Anschlussleitung, etc.)
        target_col = None
        field_lower = field.lower().strip()
        utility_lower = utility.lower().strip()
        
        # Pass 1: Exact match (after normalizing whitespace)
        for c in df_raw.columns:
            if c.strip().lower() == field_lower:
                target_col = c
                break
        
        # Pass 2: Utility-prefixed exact match (e.g. 'Gas Schutzrohr')
        if not target_col and utility_lower not in ['gemeinsam', '']:
            for c in df_raw.columns:
                c_norm = c.strip().lower()
                expected = f"{utility_lower} {field_lower}"
                if c_norm == expected or c_norm.endswith(field_lower) and c_norm.startswith(utility_lower):
                    target_col = c
                    break
        
        # Pass 3: Field substring match in utility-prefixed columns
        if not target_col and utility_lower not in ['gemeinsam', '']:
            for c in df_raw.columns:
                c_norm = c.strip().lower()
                if field_lower in c_norm and c_norm.startswith(utility_lower):
                    target_col = c
                    break
        
        # Pass 4: Field substring match in any column (shared fields like Hausnummer)
        if not target_col:
            for c in df_raw.columns:
                if field_lower in c.strip().lower():
                    target_col = c
                    break
        
        if not target_col:
            return False
            
        # 2. Fuzzy ID Matching
        target_sid = str(customer_id).lower().replace("kunde", "").strip()
        
        found_idx = None
        for i, val in enumerate(df_raw['Kunden']):
            v_str = str(val).lower().replace("kunde", "").strip()
            if v_str == target_sid:
                found_idx = i
                break
        
        if found_idx is None: 
            return False
        idx = found_idx
        
        # 3. Apply update
        df_raw.at[idx, target_col] = str(new_value)
        
        # 4. Save back
        try:
            # Use a context manager to ensure the file is closed
            with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl') as writer:
                df_raw.to_excel(writer, index=False)
        except Exception as e:
            df_raw.to_excel(EXCEL_FILE, index=False)
            
        invalidate_cache()
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False
