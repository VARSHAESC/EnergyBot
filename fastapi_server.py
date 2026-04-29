# -*- coding: utf-8 -*-
import os
import logging
import time
import pandas as pd

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

# -------------------------------------------------------------
# SAFE IMPORTS
# -------------------------------------------------------------
try:
    from geo_utils import (
        get_utility_df,
        get_unified_df,
        kpi_advanced,
        ALL_UTILITIES,
        load_excel,
        EXCEL_FILE,
        _invalidate_cache
    )
except Exception as e:
    logger.error("geo_utils import failed: %s", e)
    get_utility_df = None
    get_unified_df = None
    kpi_advanced = None
    load_excel = None
    EXCEL_FILE = None
    ALL_UTILITIES = []
    _invalidate_cache = None

try:
    from rag_engine import EnergyRAG
except Exception as e:
    logger.error("EnergyRAG import failed: %s", e)
    EnergyRAG = None

# -------------------------------------------------------------
# FASTAPI APP
# -------------------------------------------------------------
app = FastAPI(
    title="STADTWERKE X API",
    description="Production API for the EnergyBot Intelligence Platform"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = None

# -------------------------------------------------------------
# MODELS
# -------------------------------------------------------------
class UpdateRequest(BaseModel):
    customer_id: str
    field_name: str
    new_value: str
    utility: str

class ChatRequest(BaseModel):
    query: str
    utility: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = []

# -------------------------------------------------------------
# KPI CACHE
# -------------------------------------------------------------
_KPI_CACHE = {
    "kpis": {},
    "detailed_kpis": {},
    "mtime": 0,
    "last_check": 0
}

CACHE_TTL = 300

def _check_kpi_cache():
    global _KPI_CACHE
    current_time = time.time()

    if current_time - _KPI_CACHE["last_check"] < CACHE_TTL:
        return

    if EXCEL_FILE and os.path.exists(EXCEL_FILE):
        mtime = os.path.getmtime(EXCEL_FILE)
        if mtime != _KPI_CACHE["mtime"]:
            _KPI_CACHE["kpis"].clear()
            _KPI_CACHE["detailed_kpis"].clear()
            _KPI_CACHE["mtime"] = mtime

    _KPI_CACHE["last_check"] = current_time

# -------------------------------------------------------------
# STARTUP
# -------------------------------------------------------------
@app.on_event("startup")
def startup_event():
    global engine

    logger.info("Starting EnergyBot Platform...")

    try:
        if get_unified_df:
            get_unified_df()
            if load_excel:
                load_excel()
    except Exception as e:
        logger.warning(f"Cache warmup failed: {e}")

    if EnergyRAG:
        try:
            engine = EnergyRAG()
            logger.info("RAG Engine initialized")
        except Exception as e:
            logger.error("Engine init failed: %s", e)

# -------------------------------------------------------------
# KPI ENDPOINTS (VECTORIZED & CACHED)
# -------------------------------------------------------------
@app.get("/api/kpis")
def get_kpis(utility: str = "Alle Sparten"):
    """Fetch global KPIs for the dashboard"""
    if not get_unified_df:
        raise HTTPException(status_code=500, detail="Data utilities not loaded.")
        
    _check_kpi_cache()
    if utility in _KPI_CACHE["kpis"]:
        return _KPI_CACHE["kpis"][utility]
        
    df = get_unified_df() if utility == "Alle Sparten" else get_utility_df(utility)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No data found for {utility}")
    
    kpis = kpi_advanced(df)
    sanitized_kpis = {k: float(v) if isinstance(v, (int, float)) else v for k, v in kpis.items()}
    
    _KPI_CACHE["kpis"][utility] = sanitized_kpis
    return sanitized_kpis

@app.get("/api/kpis/detailed")
def get_detailed_kpis(utility: str = "Alle Sparten"):
    if not get_unified_df:
        raise HTTPException(status_code=500, detail="Data utilities not loaded.")

    _check_kpi_cache()
    if utility in _KPI_CACHE["detailed_kpis"]:
        return _KPI_CACHE["detailed_kpis"][utility]

    df = get_unified_df() if utility == "Alle Sparten" else get_utility_df(utility)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No data found for {utility}")

    def safe_int(val):
        try: return int(val)
        except: return 0

    def safe_float(val):
        try: return float(val)
        except: return 0.0

    def get_col_df(frame, candidates):
        for col in frame.columns:
            lower = str(col).lower()
            if any(c.lower() in lower for c in candidates):
                return frame[col]
        return pd.Series(dtype=object)

    def vectorized_yr(series):
        # Extract 4-digit years and convert to numeric efficiently
        years = series.astype(str).str.extract(r'(\d{4})')[0]
        years = pd.to_numeric(years, errors='coerce')
        return years.where((years > 1900) & (years < 2030))

    try:
        raw = load_excel() # Hits the fast _DATA_CACHE now
    except Exception:
        raw = pd.DataFrame()

    # -- 1. Anschlüsse -------------------------------------------------
    total  = len(df)
    wasser = safe_int((df["Sparte"] == "Wasser").sum())
    gas    = safe_int((df["Sparte"] == "Gas").sum())
    avg_age = safe_float(df["Alter"].mean()) if "Alter" in df.columns else 0.0

    druck_col = get_col_df(df, ["druck"])
    gas_md = safe_int(((df["Sparte"] == "Gas") & (druck_col.astype(str).str.contains("MD", case=False, na=False))).sum()) if not druck_col.empty else 0
    gas_nd = safe_int(((df["Sparte"] == "Gas") & (druck_col.astype(str).str.contains("ND", case=False, na=False))).sum()) if not druck_col.empty else 0

    haushalt = buero = industrie = gemeinschaft = schule = hotel = msh = msh_nein = unclassified = 0
    if not raw.empty:
        haushalt     = safe_int(get_col_df(raw, ["haushalt"]).eq("Ja").sum())
        buero        = safe_int(get_col_df(raw, ["büro", "buero"]).eq("Ja").sum())
        industrie    = safe_int(get_col_df(raw, ["industrie"]).eq("Ja").sum())
        gemeinschaft = safe_int(get_col_df(raw, ["gemeinschaft"]).eq("Ja").sum())
        schule       = safe_int(get_col_df(raw, ["schule", "bildung"]).eq("Ja").sum())
        hotel        = safe_int(get_col_df(raw, ["hotel"]).eq("Ja").sum())
        msh_col_raw  = raw.get("Mehrspartenhauseinführung", pd.Series(dtype=object))
        msh          = safe_int((msh_col_raw == "Ja").sum())
        msh_nein     = safe_int((msh_col_raw == "Nein").sum())
        _bt_flags = [
            get_col_df(raw, ["haushalt"]),
            get_col_df(raw, ["büro", "buero"]),
            get_col_df(raw, ["industrie"]),
            get_col_df(raw, ["gemeinschaft"]),
            get_col_df(raw, ["schule", "bildung"]),
            get_col_df(raw, ["hotel"]),
        ]
        _has_type = pd.Series(False, index=raw.index)
        for _c in _bt_flags:
            if not _c.empty:
                _has_type = _has_type | (_c == "Ja")
        unclassified = safe_int((~_has_type).sum())

    # -- 2. Kritisch ---------------------------------------------------
    hoch        = safe_int((df["Risiko"] == "Hoch").sum())
    wasser_hoch = safe_int(((df["Sparte"] == "Wasser") & (df["Risiko"] == "Hoch")).sum())
    gas_hoch    = safe_int(((df["Sparte"] == "Gas")    & (df["Risiko"] == "Hoch")).sum())
    high_risk_pct = safe_float(100 * hoch / max(total, 1))

    overdue_wasser = overdue_gas = insp_overdue = 0
    if not raw.empty:
        wi_col = "Wasser (Letztes) Inspektionsdatum"
        gi_col = "Gas (Letztes) Inspektionsdatum"
        if wi_col in raw.columns:
            wi = vectorized_yr(raw[wi_col])
            overdue_wasser = safe_int(((2026 - wi).dropna() > 5).sum())
        if gi_col in raw.columns:
            gi = vectorized_yr(raw[gi_col])
            overdue_gas = safe_int(((2026 - gi).dropna() > 5).sum())
        insp_overdue = overdue_wasser + overdue_gas

    # -- 3. Über Nutzungsdauer -----------------------------------------
    over_lifespan = renewal_next_10yr = renewal_next_20yr = 0
    age_gt_80 = age_gt_80_wasser = wasser_over = gas_over = oldest_asset_years = 0
    if not raw.empty:
        w_col = "Wasser Einbaudatum/ Fertigmeldung"
        g_col = "Gas Einbaudatum/ Fertigmeldung"
        
        wa = (2026 - vectorized_yr(raw[w_col])) if w_col in raw.columns else pd.Series(dtype=float)
        ga = (2026 - vectorized_yr(raw[g_col])) if g_col in raw.columns else pd.Series(dtype=float)
        
        wa_v = wa.dropna()
        ga_v = ga.dropna()

        wasser_over   = safe_int((wa_v > 64).sum())
        gas_over      = safe_int((ga_v > 64).sum())
        over_lifespan = wasser_over + gas_over

        age_gt_80        = safe_int((wa_v > 80).sum()) + safe_int((ga_v > 80).sum())
        age_gt_80_wasser = safe_int((wa_v > 80).sum())

        renewal_next_10yr = safe_int(((wa_v > 54) & (wa_v <= 64)).sum()) + safe_int(((ga_v > 54) & (ga_v <= 64)).sum())
        renewal_next_20yr = safe_int(((wa_v > 44) & (wa_v <= 64)).sum()) + safe_int(((ga_v > 44) & (ga_v <= 64)).sum())

        all_ages = pd.concat([wa_v, ga_v])
        oldest_asset_years = safe_int(all_ages.max()) if not all_ages.empty else 0

    # -- 4. Materialrisiko ---------------------------------------------
    werkstoff_col   = get_col_df(df, ["werkstoff"])
    az_count        = safe_int((werkstoff_col == "Asbestzement-(AZ)").sum()) if not werkstoff_col.empty else 0
    stahl_no_kks    = safe_int((werkstoff_col == "Stahl ohne KKS").sum()) if not werkstoff_col.empty else 0
    critical_material = az_count + stahl_no_kks
    schutzrohr_col  = get_col_df(df, ["schutzrohr"])
    schutzrohr_nein = safe_int(((df["Sparte"] == "Wasser") & (schutzrohr_col == "Nein")).sum()) if not schutzrohr_col.empty else 0

    result = {
        "anschluesse": {
            "total": total, "wasser": wasser, "gas": gas, "avg_age": avg_age,
            "haushalt": haushalt, "buero": buero, "industrie": industrie,
            "gemeinschaft": gemeinschaft, "schule": schule, "hotel": hotel,
            "unclassified": unclassified,
            "msh": msh, "msh_nein": msh_nein, "gas_md": gas_md, "gas_nd": gas_nd,
        },
        "kritisch": {
            "hoch_risiko": hoch, "wasser_kritisch": wasser_hoch,
            "gas_kritisch": gas_hoch, "high_risk_pct": high_risk_pct,
            "inspection_overdue": insp_overdue,
            "overdue_wasser": overdue_wasser, "overdue_gas": overdue_gas,
        },
        "ueber_nutzungsdauer": {
            "over_lifespan": over_lifespan, "renewal_next_10yr": renewal_next_10yr,
            "renewal_next_20yr": renewal_next_20yr, "age_gt_80": age_gt_80,
            "age_gt_80_wasser": age_gt_80_wasser, "wasser_over": wasser_over,
            "gas_over": gas_over, "oldest_asset_years": oldest_asset_years,
        },
        "modernisierung": {
            "critical_material": critical_material, "az_leitungen": az_count,
            "stahl_ohne_kks": stahl_no_kks, "schutzrohr_nein": schutzrohr_nein,
            "msh_nein": msh_nein,
        },
    }
    
    _KPI_CACHE["detailed_kpis"][utility] = result
    return result

# -------------------------------------------------------------
# UPDATE ENDPOINT (FIXED)
# -------------------------------------------------------------
@app.post("/update-asset")
def update_asset(req: UpdateRequest):
    global engine

    if not engine:
        raise HTTPException(status_code=500, detail="Engine not ready")

    # Clear caches
    if _invalidate_cache:
        _invalidate_cache()
    _KPI_CACHE["kpis"].clear()
    _KPI_CACHE["detailed_kpis"].clear()
    
    result = engine.apply_update(
        customer_id=req.customer_id,
        field_name=req.field_name,
        new_value=req.new_value,
        utility=req.utility,
    )

    return result

# -------------------------------------------------------------
# CHAT (NORMAL)
# -------------------------------------------------------------
@app.post("/api/chat")
def chat(request: ChatRequest):
    if not engine:
        raise HTTPException(status_code=500, detail="RAG Engine not initialized.")

    req_util = request.utility if request.utility != "Alle Sparten" else None

    response = engine.answer_question(
        request.query,
        utility=req_util,
        history=request.history
    )

    return {
        "answer": response.get("answer", ""),
        "pending_action": response.get("pending_action", None),
    }

# -------------------------------------------------------------
# CHAT STREAM (FIXED)
# -------------------------------------------------------------
@app.post("/api/chat/stream")
def chat_stream(request: ChatRequest):
    if not engine:
        raise HTTPException(status_code=500, detail="RAG Engine not initialized.")

    req_util = request.utility if request.utility != "Alle Sparten" else None

    def generate():
        yield from engine.stream_answer(
            request.query,
            utility=req_util,
            history=request.history
        )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )

# -------------------------------------------------------------
# ASSETS AND MAP ENDPOINTS (RESTORED)
# -------------------------------------------------------------
@app.get("/api/assets")
def get_assets(utility: str = "Alle Sparten"):
    """Fetch detailed asset list and summaries for charts"""
    if not get_unified_df:
        raise HTTPException(status_code=500, detail="Data utilities not loaded.")
        
    df = get_unified_df() if utility == "Alle Sparten" else get_utility_df(utility)
    if df.empty:
        return {"records": [], "summaries": {}}

    def get_summary_for_df(frame):
        # 1. Summary: Age Groups
        age_bins = [0, 10, 20, 30, 100]
        age_labels = ["0-10 J", "10-20 J", "20-30 J", "30+ J"]
        # Use a copy to avoid SettingWithCopyWarning
        temp_df = frame.copy()
        temp_df['AgeGroup'] = pd.cut(temp_df['Alter'], bins=age_bins, labels=age_labels, right=False)
        age_summary = temp_df.groupby('AgeGroup', observed=True).size().reset_index(name='count')
        age_data = []
        for label in age_labels:
            count = int(age_summary[age_summary['AgeGroup'] == label]['count'].sum())
            age_data.append({"name": label, "value": count})

        # 2. Summary: Risk distribution
        risk_summary = temp_df['Risiko'].value_counts().to_dict()
        risk_data = [
            {"name": "Hoch", "value": int(risk_summary.get("Hoch", 0)), "color": "#ef4444"},
            {"name": "Mittel", "value": int(risk_summary.get("Mittel", 0)), "color": "#f59e0b"},
            {"name": "Niedrig", "value": int(risk_summary.get("Niedrig", 0)), "color": "#22c55e"},
        ]
        return {"age": age_data, "risk": risk_data}

    summaries = {}
    if utility == "Alle Sparten":
        # Get separate summaries for Gas and Water
        gas_df = df[df["Sparte"] == "Gas"]
        water_df = df[df["Sparte"] == "Wasser"]
        if not gas_df.empty:
            summaries["Gas"] = get_summary_for_df(gas_df)
        if not water_df.empty:
            summaries["Wasser"] = get_summary_for_df(water_df)
    else:
        summaries[utility] = get_summary_for_df(df)

    # 3. Records for table (last 100 rows)
    records = df.tail(100).to_dict('records')
    clean_records = []
    for r in records:
        row = {}
        for k, v in r.items():
            key = str(k)
            if pd.isna(v):
                row[key] = None
            elif hasattr(v, 'item'):
                row[key] = v.item()
            elif isinstance(v, (pd.Timestamp, pd.Period)):
                row[key] = str(v)
            else:
                row[key] = v
        clean_records.append(row)

    return {
        "records": clean_records,
        "summaries": summaries
    }

@app.get("/api/map-explorer")
def get_map_explorer(utility: str = "Alle Sparten"):
    """Fetch all asset records for the Map Explorer page"""
    if not get_unified_df:
        raise HTTPException(status_code=500, detail="Data utilities not loaded.")

    df = get_unified_df() if utility == "Alle Sparten" else get_utility_df(utility)
    if df.empty:
        return {"records": []}

    CURRENT_YEAR = 2026
    clean_records = []
    for r in df.to_dict('records'):
        row = {}
        for k, v in r.items():
            key = str(k)
            try:
                is_na = pd.isna(v)
            except Exception:
                is_na = False
            if is_na:
                row[key] = None
            elif hasattr(v, 'item'):
                row[key] = v.item()
            elif isinstance(v, (pd.Timestamp, pd.Period)):
                row[key] = str(v)
            else:
                row[key] = v
        renewal = row.get("Erneuerung_empfohlen_bis")
        row["over_lifespan"] = bool(renewal is not None and renewal < CURRENT_YEAR)
        clean_records.append(row)

    return {"records": clean_records}

# -------------------------------------------------------------
# HEALTH
# -------------------------------------------------------------
@app.get("/api/health")
def health_check():
    if not engine:
        return {"status": "backend_degraded", "llm_available": False}

    status = engine.check_llm_status()["msg"]
    kb_count = engine.vs.count() if hasattr(engine, 'vs') else 0

    return {
        "status": "ok",
        "llm": status,
        "kb_count": kb_count
    }


# -------------------------------------------------------------
# RUN
# -------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fastapi_server:app", host="127.0.0.1", port=8000, reload=True)
