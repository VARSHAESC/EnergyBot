# -*- coding: utf-8 -*-
"""
rag_engine.py — Multi-Utility Hybrid Engine (Gas | Strom | Wasser)
Strictly Offline Version using Gemma 3 via Ollama.
"""

from __future__ import annotations

# --- NumPy 2.x compatibility shim ---
import numpy as _np
if not hasattr(_np, "float_"):   _np.float_ = _np.float64
if not hasattr(_np, "int_"):     _np.int_ = int
if not hasattr(_np, "bool_"):    _np.bool_ = bool
if not hasattr(_np, "object_"): _np.object_ = object
# ------------------------------------

import os
import re
import io
from typing import List, Dict, Any, Optional, Sequence, Set

import pandas as pd
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import requests
import json
import docx

from geo_utils import load_excel, CSV_FILES, ALL_UTILITIES, MATERIAL_LIFESPAN, get_utility_df, get_unified_df

load_dotenv()

# ─────────────── Config ───────────────
OFFLINE: bool = os.getenv("OFFLINE_MODE", "false").lower() == "true"
PERSIST_DIR: str = "./chroma_db"
EMBED_MODEL_NAME: str = os.getenv(
    "EMBED_MODEL_NAME",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
RETURN_ALL_MAX: int = 100_000

# ─────────────── Utilities ───────────────
def _safe(v: Any) -> str:
    return "" if pd.isna(v) else str(v)

def row_to_paragraph(row: Dict[str, Any], utility: str = "") -> str:
    general_keys = ["Gemeinde", "Ortsteil", "Straße", "Hausnummer", "Zusatz", "Objekt-ID_Global"]
    util_specific = {k: v for k, v in row.items() if k not in general_keys and k != "Sparte"}
    parts = []
    if utility: parts.append(f"VERSORGUNGSART: {utility}")
    gen = [f"{k}: {_safe(row.get(k))}" for k in general_keys if row.get(k) and pd.notna(row.get(k))]
    if gen: parts.append("ALLGEMEINE OBJEKTDATEN: " + ", ".join(gen))
    spec = [f"{k}: {_safe(v)}" for k, v in util_specific.items() if pd.notna(v) and str(v).strip() not in ("", "nan")]
    if spec: parts.append(f"DATEN ZUM NETZANSCHLUSS {utility}: " + ", ".join(spec))
    return " | ".join(parts) + "."

# ─────────────── Vector Store ───────────────
class VectorStore:
    def __init__(self, persist_dir: str = PERSIST_DIR, name: str = "energy_kb", embed_model: str = EMBED_MODEL_NAME):
        self.client = chromadb.PersistentClient(path=persist_dir, settings=Settings(anonymized_telemetry=False))
        try:
            self.col = self.client.get_collection(name)
        except Exception:
            self.col = self.client.create_collection(name, metadata={"embed_model": embed_model})
        meta = self.col.metadata or {}
        if meta.get("embed_model") != embed_model:
            self.client.delete_collection(name)
            self.col = self.client.create_collection(name, metadata={"embed_model": embed_model})

    def reset(self, metadata: Optional[Dict[str, Any]] = None):
        name = self.col.name
        self.client.delete_collection(name)
        self.col = self.client.create_collection(name, metadata=metadata)

    def count(self) -> int:
        try: return self.col.count()
        except: return 0

    def add(self, ids, embeddings, metadatas, documents):
        self.col.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)

    def query(self, query_embeddings, top_k: int = 5):
        cnt = self.count()
        if cnt == 0: return {"metadatas": [[]], "documents": [[]], "distances": [[]]}
        return self.col.query(query_embeddings=query_embeddings, n_results=min(top_k, cnt))

class Embedder:
    def __init__(self, model_name: str = EMBED_MODEL_NAME):
        self.model = SentenceTransformer(model_name)
    def embed(self, texts: List[str], batch_size: int = 64) -> List[List[float]]:
        return self.model.encode(texts, batch_size=batch_size, show_progress_bar=False).tolist()

# ─────────────── Main Engine ───────────────
class EnergyRAG:
    def __init__(self, persist_dir: str = PERSIST_DIR, embed_model: str = EMBED_MODEL_NAME):
        self.vs = VectorStore(persist_dir, "energy_kb_multi", embed_model)
        self.embedder = Embedder(embed_model)
        
        # --- Provider-Agnostic LLM Configuration ---
        self.llm_api_key = os.getenv("LLM_API_KEY", os.getenv("GROQ_API_KEY"))
        self.llm_model = os.getenv("LLM_MODEL_NAME", os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
        # Base URL for OpenAI-compatible APIs (default to Groq if not specified)
        self.llm_base_url = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
        
        self.unified_df = get_unified_df()
        self.reference_manual = self._load_reference_manual()

    def _load_reference_manual(self) -> str:
        """Loads the Word reference manual for system prompt context."""
        doc_path = os.path.join("excel_data", "Hausanschluss_KI_Referenzhandbuch.docx")
        if not os.path.exists(doc_path):
            return "Reference Manual not found."
        try:
            doc = docx.Document(doc_path)
            return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        except:
            return "Error loading Reference Manual."

    def check_llm_status(self) -> Dict[str, Any]:
        if not self.llm_api_key:
            return {"ok": False, "msg": "API Key fehlt."}
        try:
            # Simple check call to models list (OpenAI-compatible)
            headers = {"Authorization": f"Bearer {self.llm_api_key}"}
            resp = requests.get(f"{self.llm_base_url}/models", headers=headers, timeout=5)
            if resp.status_code == 200:
                provider_name = "Online" if "groq" in self.llm_base_url else "Custom Provider"
                return {"ok": True, "msg": f"{provider_name}: {self.llm_model}"}
            return {"ok": False, "msg": f"LLM Error: {resp.status_code}"}
        except Exception as e:
            return {"ok": False, "msg": f"Verbindungsfehler: {str(e)[:50]}"}

    def init_or_refresh_kb(self, utility: Optional[str] = None, reset: bool = False) -> int:
        utils = [utility] if utility else ALL_UTILITIES
        if reset: 
            # Preserve metadata during reset to avoid startup deletion loop
            old_meta = self.vs.col.metadata
            self.vs.reset(metadata=old_meta)
        total = 0
        for util in utils:
            df = get_utility_df(util)
            if df.empty: continue
            docs, ids, metas = [], [], []
            for i, row in df.iterrows():
                row_id = f"{util}_{row.get('Datensatz', i)}"
                para = row_to_paragraph(row.to_dict(), utility=util)
                if not para: continue
                docs.append(para)
                ids.append(row_id)
                metas.append({"utility": util, "id": str(row.get("Kundennummer", ""))})
            if docs:
                embeddings = self.embedder.embed(docs)
                self.vs.add(ids=ids, embeddings=embeddings, metadatas=metas, documents=docs)
                total += len(docs)
        self.unified_df = get_unified_df()
        return total

    def transcribe_audio(self, audio_bytes: bytes) -> Dict[str, Any]:
        if not self.llm_api_key: return {"ok": False, "text": "API Key fehlt."}
        if not audio_bytes or len(audio_bytes) < 100:
            return {"ok": False, "text": "Audio-Daten zu kurz oder leer."}
            
        try:
            headers = {"Authorization": f"Bearer {self.llm_api_key}"}
            files = {
                "file": ("audio.webm", io.BytesIO(audio_bytes), "audio/webm"),
                "model": (None, os.getenv("WHISPER_MODEL", "whisper-large-v3")),
            }
            # Whisper endpoint is usually /audio/transcriptions
            resp = requests.post(f"{self.llm_base_url}/audio/transcriptions", headers=headers, files=files, timeout=30)
            if resp.status_code == 200:
                t = resp.json().get("text", "")
                return {"ok": True, "text": t}
            return {"ok": False, "text": f"LLM Error: {resp.status_code} - {resp.text}"}
        except Exception as e:
            return {"ok": False, "text": f"Verbindungsfehler: {str(e)}"}

    def _try_dataframe_answer(self, question: str) -> Optional[Dict[str, Any]]:
        ql = (question or "").lower()
        
        # 0. STRICT BYPASS: If this is an update command, we MUST use the Agentic Engine
        update_keywords = ["update", "ändern", "setze", "change", "aktualisier", "korrigier", "fix", "put", "schreib"]
        if any(x in ql for x in update_keywords):
            return None

        if self.unified_df.empty: self.unified_df = get_unified_df()
        
        # 1. Direct ID Lookup (Prioritized for Queries only)
        id_match = re.search(r'(\d+)', ql)
        if id_match and not any(x in ql for x in ["älter", "jahre", "vor", "nach", "count", "anzahl"]):
            sid = id_match.group(1)
            search_df = self.unified_df.copy()
            
            # Smart Sparten Filter (Optional)
            target_sparte = None
            if "gas" in ql: target_sparte = "Gas"
            elif "strom" in ql: target_sparte = "Strom"
            elif "wasser" in ql: target_sparte = "Wasser"
            
            if target_sparte:
                search_df = search_df[search_df["Sparte"] == target_sparte]
            
            # Find the ID
            matches = pd.DataFrame()
            for col in ["Kundennummer", "Objekt-ID", "Objekt-ID_Global"]:
                if col in search_df.columns:
                    mask = search_df[col].astype(str).str.contains(rf'\b{sid}\b', regex=True, na=False)
                    if mask.any():
                        matches = search_df[mask]
                        break
            
            if not matches.empty:
                res = matches.iloc[0]
                lines = [f"✅ **Datensatz gefunden: {res.get('Sparte', '')} - {res.get('Kundennummer', sid)}**", ""]
                
                # Check specifics
                if any(x in ql for x in ["material", "werkstoff", "type", "art"]):
                    lines.append(f"🏗️ **Material:** {res.get('Werkstoff', 'n/a')} ({res.get('Dimension', '')})")
                
                if any(x in ql for x in ["strasse", "straße", "hausnummer", "address", "location"]):
                    lines.append(f"📍 **Adresse:** {res.get('Straße', 'n/a')} {res.get('Hausnummer', '')}")
                    lines.append(f"🏙️ **Ort:** {res.get('Ortsteil', '')} {res.get('Gemeinde', '')}")

                if any(x in ql for x in ["alter", "age", "year", "einbau"]):
                    lines.append(f"⏳ **Alter:** {int(res.get('Alter', 0))} Jahre (Einbau: {res.get('Einbaujahr', 'unbekannt')})")

                if len(lines) <= 2: # Show all if vague
                    lines.append(f"📍 **Adresse:** {res.get('Straße', 'n/a')} {res.get('Hausnummer', '')}")
                    lines.append(f"🏗️ **Material:** {res.get('Werkstoff', 'n/a')}")
                    lines.append(f"⚠️ **Risiko:** {res.get('Risiko', 'n/a')}")
                
                return {"answer": "\n".join(lines), "hits": [], "model_used": "Direct-ID-Engine-v2", "switched": True}

        # 2. Greetings (Fixed for False Positives like "whicH I...")
        if ql.strip() in ["hi", "hallo", "hello", "guten tag", "hey"]:
            return {"answer": "Guten Tag! Ich bin das ESC Infrastructure Intelligence System. Wie kann ich Ihnen heute bei der Analyse Ihrer Gas-, Strom- oder Wasser-Anschlussdaten helfen?", "hits": [], "model_used": "System", "switched": False}

        # 3. Analytical Trends (Materials over time)
        if any(x in ql for x in ["material", "werkstoff", "anschlussart"]) and any(x in ql for x in ["wann", "verbaut", "historisch", "zeitraum"]):
            try:
                df = self.unified_df.copy()
                df["Dekade"] = (df["Einbaujahr"] // 10) * 10
                summary = df.groupby(["Dekade", "Werkstoff"]).size().unstack(fill_value=0)
                lines = ["📜 **Historische Analyse: Materialverwendung**", ""]
                for decade in sorted(summary.index.dropna()):
                    if decade < 1920: continue
                    mats = summary.loc[decade]
                    top = mats[mats > 0].sort_values(ascending=False)
                    mat_str = ", ".join([f"{m} ({q})" for m, q in top.items()])
                    lines.append(f"- **{int(decade)}er Jahre**: {mat_str}")
                return {"answer": "\n".join(lines), "hits": [], "model_used": "History-Engine", "switched": True}
            except: pass

        # 4. Numeric Filters
        age_match = re.search(r'(älter|older|>)\s*(\d+)', ql)
        if age_match:
            try:
                threshold = int(age_match.group(2))
                matches = self.unified_df[self.unified_df["Alter"] > threshold].sort_values("Alter", ascending=False)
                if not matches.empty:
                    lines = [f"📊 **Analyse: {len(matches)} Objekte > {threshold} Jahre**", "Top Treffer:", ""]
                    for _, r in matches.head(5).iterrows():
                        lines.append(f"- {r['Sparte']} ({r['Kundennummer']}): {r['Straße']} | **{int(r['Alter'])} J.**")
                    return {"answer": "\n".join(lines), "hits": [], "model_used": "Filter-Engine", "switched": True}
            except: pass

        return None

    def answer_question(self, question: str, utility: Optional[str] = None) -> Dict[str, Any]:
        ql = (question or "").lower()
        print(f"DEBUG: Processing question: '{ql[:50]}...'")
        
        # 0. SKIP FAST ENGINE FOR UPDATES (Force Agentic Tool Mode)
        update_keywords = ["update", "ändern", "setze", "change", "aktualisier", "korrigier", "fix", "put", "schreib"]
        is_update = any(x in ql for x in update_keywords)
        print(f"DEBUG: is_update detected: {is_update}")
        
        if not is_update:
            df_res = self._try_dataframe_answer(question)
            if df_res: 
                print("DEBUG: Handled by fast-lookup engine.")
                return df_res
        else:
            print("DEBUG: Update detected. Skipping fast-lookup, forcing Agentic Tool Mode.")

        status = self.check_llm_status()
        if not status["ok"]:
            return {"answer": f"⚠️ **Service-Status**: {status['msg']}", "hits": [], "model_used": "Status-Check", "switched": False}

        hits = []
        try:
            results = self.vs.query(query_embeddings=self.embedder.embed([question]), top_k=4)
            hits = [{"meta": m, "doc": d, "score": 1-dist} for m, d, dist in zip(results["metadatas"][0], results["documents"][0], results["distances"][0])]
            
            ctx = "\n---\n".join([h["doc"] for h in hits])
            
            headers = {
                "Authorization": f"Bearer {self.llm_api_key}",
                "Content-Type": "application/json"
            }

            if is_update:
                # --- AGENTIC MODE: send tools for write operations ---
                tools = [
                    {
                        "type": "function",
                        "function": {
                            "name": "update_asset",
                            "description": "Updates any field of a utility asset in the database. Call this when the user asks to change, set, or update any value.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "customer_id": {"type": "string", "description": "Customer ID, e.g. '3' or 'Kunde 3'."},
                                    "field_name": {"type": "string", "description": "Column to update, e.g. Hausnummer, Schutzrohr, Werkstoff, Installateur Name, Gemeinde, Gestattungsvertrag, etc."},
                                    "new_value": {"type": "string", "description": "New value to write."},
                                    "utility": {"type": "string", "enum": ["Gas", "Wasser", "Strom", "Gemeinsam"], "description": "Utility sector. Use Gemeinsam for shared fields."}
                                },
                                "required": ["customer_id", "field_name", "new_value", "utility"]
                            }
                        }
                    }
                ]
                payload = {
                    "model": self.llm_model,
                    "messages": [
                        {"role": "system", "content": (
                            "You are the ESC Agentic Assistant. You have FULL AUTHORITY to update the database. "
                            "When the user asks to change any value, IMMEDIATELY call the update_asset tool. "
                            "If utility is unclear, use 'Gemeinsam' for address fields (Hausnummer, Stra\u00dfe, Gemeinde)."
                        )},
                        {"role": "user", "content": f"Question: {question}"}
                    ],
                    "tools": tools,
                    "tool_choice": "required",
                    "temperature": 0.0,
                    "max_tokens": 300
                }
            else:
                # --- FAST READ MODE: no tools, minimal tokens ---
                payload = {
                    "model": self.llm_model,
                    "messages": [
                        {"role": "system", "content": f"You are an infrastructure data expert. Answer concisely in the same language as the question. Context: {self.reference_manual[:500]}"},
                        {"role": "user", "content": f"Data:\n{ctx}\n\nQuestion: {question}"}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 600
                }

            resp = requests.post(f"{self.llm_base_url}/chat/completions", headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                choice = resp.json()["choices"][0]
                msg = choice["message"]
                
                # Check for tool calls (only in agentic mode)
                if "tool_calls" in msg and msg["tool_calls"]:
                    tc = msg["tool_calls"][0]["function"]
                    args = json.loads(tc["arguments"])
                    return {
                        "answer": f"🤖 Update erkannt:\n- **Kunde:** `{args.get('customer_id')}`\n- **Feld:** `{args.get('field_name')}`\n- **Neuer Wert:** `{args.get('new_value')}`\n- **Sparte:** `{args.get('utility')}`",
                        "hits": hits,
                        "model_used": self.llm_model,
                        "pending_action": {"type": "update_asset", "args": args}
                    }

                answer = msg.get("content", "")
                return {"answer": answer, "hits": hits, "model_used": self.llm_model, "switched": False}
        except: pass

        if hits:
            fallback = "⏱️ **Zeitüberschreitung**: Relevantes aus der Datenbank:\n\n" + "\n".join([f"- {h['doc']}" for h in hits[:2]])
            return {"answer": fallback, "hits": hits, "model_used": "Timeout-Fallback", "switched": False}
        
        return {"answer": "Keine Antwort gefunden.", "hits": [], "model_used": "Error", "switched": False}

    def chat_general(self, user_message: str, history: List[Dict]) -> Dict[str, Any]:
        return self.answer_question(user_message)