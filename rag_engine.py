# # -*- coding: utf-8 -*-
# """
# rag_engine.py — Multi-Utility Hybrid Engine (Gas | Strom | Wasser)
# Strictly Offline Version using Gemma 3 via Ollama.
# """

# from __future__ import annotations

# # --- NumPy 2.x compatibility shim ---
# import numpy as _np
# if not hasattr(_np, "float_"):   _np.float_ = _np.float64
# if not hasattr(_np, "int_"):     _np.int_ = int
# if not hasattr(_np, "bool_"):    _np.bool_ = bool
# if not hasattr(_np, "object_"): _np.object_ = object
# # ------------------------------------

# import os
# import re
# import io
# from typing import List, Dict, Any, Optional, Sequence, Set

# import pandas as pd
# import chromadb
# from chromadb.config import Settings
# from sentence_transformers import SentenceTransformer
# from dotenv import load_dotenv
# import requests
# import json
# import docx

# from geo_utils import load_excel, CSV_FILES, ALL_UTILITIES, MATERIAL_LIFESPAN, get_utility_df, get_unified_df

# load_dotenv()

# # ─────────────── Config ───────────────
# OFFLINE: bool = os.getenv("OFFLINE_MODE", "false").lower() == "true"
# PERSIST_DIR: str = "./chroma_db"
# EMBED_MODEL_NAME: str = os.getenv(
#     "EMBED_MODEL_NAME",
#     "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# )
# RETURN_ALL_MAX: int = 100_000

# # ─────────────── Utilities ───────────────
# def _safe(v: Any) -> str:
#     return "" if pd.isna(v) else str(v)

# def row_to_paragraph(row: Dict[str, Any], utility: str = "") -> str:
#     general_keys = ["Gemeinde", "Postleitzahl", "Straße", "Hausnummer", "Zusatz", "Objekt-ID_Global"]
#     util_specific = {k: v for k, v in row.items() if k not in general_keys and k != "Sparte"}
#     parts = []
#     if utility: parts.append(f"VERSORGUNGSART: {utility}")
#     gen = [f"{k}: {_safe(row.get(k))}" for k in general_keys if row.get(k) and pd.notna(row.get(k))]
#     if gen: parts.append("ALLGEMEINE OBJEKTDATEN: " + ", ".join(gen))
#     spec = [f"{k}: {_safe(v)}" for k, v in util_specific.items() if pd.notna(v) and str(v).strip() not in ("", "nan")]
#     if spec: parts.append(f"DATEN ZUM NETZANSCHLUSS {utility}: " + ", ".join(spec))
#     return " | ".join(parts) + "."

# # ─────────────── Engineering Standards (from User Image) ───────────────
# ENGINEERING_STANDARDS = """
# TECHNICAL LIFE TABLES (RISIKOBEWERTUNG):
# GAS (Anschlussleitungen):
# - Stahl mit KKS: gut (0-59J), mittel (60-95J), Risiko (>=96J), TechNutz: 80J
# - Stahl ohne KKS: gut (0-51J), mittel (52-83J), Risiko (>=84J), TechNutz: 70J
# - PE: gut (0-55J), mittel (56-89J), Risiko (>=90J), TechNutz: 75J

# WASSER (Anschlussleitungen):
# - Asbestzement (AZ): gut (0-36J), mittel (37-59J), Risiko (>=60J), TechNutz: 50J
# - PE: gut (0-62J), mittel (63-101J), Risiko (>=102J), TechNutz: 85J
# - PVC: gut (0-36J), mittel (37-59J), Risiko (>=60J), TechNutz: 50J
# - Stahl: gut (0-44J), mittel (45-71J), Risiko (>=72J), TechNutz: 60J

# Note: 'Alter' is calculated as CURRENT_YEAR - Einbaujahr.
# """

# # ─────────────── Vector Store ───────────────
# class VectorStore:
#     def __init__(self, persist_dir: str = PERSIST_DIR, name: str = "energy_kb", embed_model: str = EMBED_MODEL_NAME):
#         self.client = chromadb.PersistentClient(path=persist_dir, settings=Settings(anonymized_telemetry=False))
#         try:
#             self.col = self.client.get_collection(name)
#         except Exception:
#             self.col = self.client.create_collection(name, metadata={"embed_model": embed_model})
#         meta = self.col.metadata or {}
#         if meta.get("embed_model") != embed_model:
#             self.client.delete_collection(name)
#             self.col = self.client.create_collection(name, metadata={"embed_model": embed_model})

#     def reset(self, metadata: Optional[Dict[str, Any]] = None):
#         name = self.col.name
#         self.client.delete_collection(name)
#         self.col = self.client.create_collection(name, metadata=metadata)

#     def count(self) -> int:
#         try: return self.col.count()
#         except: return 0

#     def add(self, ids, embeddings, metadatas, documents):
#         self.col.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)

#     def query(self, query_embeddings, top_k: int = 5):
#         cnt = self.count()
#         if cnt == 0: return {"metadatas": [[]], "documents": [[]], "distances": [[]]}
#         return self.col.query(query_embeddings=query_embeddings, n_results=min(top_k, cnt))

# class Embedder:
#     def __init__(self, model_name: str = EMBED_MODEL_NAME):
#         import os
#         os.environ["TQDM_DISABLE"] = "1"
#         os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
#         self.model = SentenceTransformer(model_name)
#     def embed(self, texts: List[str], batch_size: int = 64) -> List[List[float]]:
#         return self.model.encode(texts, batch_size=batch_size, show_progress_bar=False).tolist()

# # ─────────────── Main Engine ───────────────
# class EnergyRAG:
#     def __init__(self, persist_dir: str = PERSIST_DIR, embed_model: str = EMBED_MODEL_NAME):
#         self.vs = VectorStore(persist_dir, "energy_kb_multi", embed_model)
#         self.embedder = Embedder(embed_model)
        
#         # --- Provider-Agnostic LLM Configuration ---
#         self.llm_api_key = os.getenv("LLM_API_KEY", os.getenv("GROQ_API_KEY"))
#         self.llm_model = os.getenv("LLM_MODEL_NAME", os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
#         self.llm_base_url = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
        
#         self.unified_df = get_unified_df()
#         self.stats_summary = ""
#         self.refresh_stats_manual() # Builds self.reference_manual

#     def _load_reference_manual(self) -> str:
#         """Loads the Word reference manual for system prompt context."""
#         doc_path = os.path.join("excel_data", "Hausanschluss_KI_Referenzhandbuch.docx")
#         if not os.path.exists(doc_path):
#             return "Reference Manual not found."
#         try:
#             doc = docx.Document(doc_path)
#             return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
#         except:
#             return "Error loading Reference Manual."

#     def check_llm_status(self) -> Dict[str, Any]:
#         if not self.llm_api_key:
#             return {"ok": False, "msg": "API Key fehlt."}
#         try:
#             # Simple check call to models list (OpenAI-compatible)
#             headers = {"Authorization": f"Bearer {self.llm_api_key}"}
#             resp = requests.get(f"{self.llm_base_url}/models", headers=headers, timeout=5)
#             if resp.status_code == 200:
#                 provider_name = "Online" if "groq" in self.llm_base_url else "Custom Provider"
#                 return {"ok": True, "msg": f"{provider_name}: {self.llm_model}"}
#             return {"ok": False, "msg": f"LLM Error: {resp.status_code}"}
#         except Exception as e:
#             return {"ok": False, "msg": f"Verbindungsfehler: {str(e)[:50]}"}

#     def refresh_stats_manual(self):
#         """Builds a dynamic stats summary for the LLM to know the 'big picture'."""
#         if self.unified_df.empty: self.unified_df = get_unified_df()
#         df = self.unified_df
#         total = len(df)
#         risks = df["Risiko"].value_counts().to_dict()
#         sparten = df["Sparte"].value_counts().to_dict()
        
#         self.stats_summary = f"""
#         CURRENT INFRASTRUCTURE SUMMARY:
#         - TOTAL CONNECTIONS: {total}
#         - DISTRIBUTION: {', '.join([f'{k}: {v}' for k, v in sparten.items()])}
#         - RISK LEVELS: {', '.join([f'{k}: {v}' for k, v in risks.items()])}
#         """
#         self.reference_manual = f"{self.stats_summary}\n\n{ENGINEERING_STANDARDS}\n"
#         # Load from file if exists
#         ref_path = "excel_data/Hausanschluss_KI_Referenzhandbuch.docx"
#         if os.path.exists(ref_path):
#             try:
#                 import docx
#                 doc = docx.Document(ref_path)
#                 self.reference_manual += "\n".join([p.text for p in doc.paragraphs])
#             except: pass

#     def init_or_refresh_kb(self, utility: Optional[str] = None, reset: bool = False) -> int:
#         self.unified_df = get_unified_df()
#         self.refresh_stats_manual() # Ensure stats are fresh
#         utils = [utility] if utility else ALL_UTILITIES
        
#         if reset:
#             # Preserve metadata during reset to avoid startup deletion loop
#             old_meta = self.vs.col.metadata
#             self.vs.reset(metadata=old_meta)
            
#         total = 0
#         for util in utils:
#             df = get_utility_df(util)
#             if df.empty: continue
            
#             docs, ids, metas = [], [], []
#             for i, row in df.iterrows():
#                 row_id = f"{util}_{row.get('Datensatz', i)}"
#                 para = row_to_paragraph(row.to_dict(), utility=util)
#                 if not para: continue
#                 docs.append(para)
#                 ids.append(row_id)
#                 metas.append({
#                     "utility": util, 
#                     "id": str(row.get("Kundennummer", "")),
#                     "name": str(row.get("Kundenname", ""))
#                 })
            
#             # Batch add to avoid memory/rate limits
#             if docs:
#                 batch_size = 500
#                 for j in range(0, len(docs), batch_size):
#                     b_docs = docs[j:j+batch_size]
#                     b_ids = ids[j:j+batch_size]
#                     b_metas = metas[j:j+batch_size]
#                     b_embeddings = self.embedder.embed(b_docs)
#                     self.vs.add(ids=b_ids, embeddings=b_embeddings, metadatas=b_metas, documents=b_docs)
#                     total += len(b_docs)
                    
#         return total

#     def transcribe_audio(self, audio_bytes: bytes) -> Dict[str, Any]:
#         if not self.llm_api_key: return {"ok": False, "text": "API Key fehlt."}
#         if not audio_bytes or len(audio_bytes) < 100:
#             return {"ok": False, "text": "Audio-Daten zu kurz oder leer."}
            
#         try:
#             headers = {"Authorization": f"Bearer {self.llm_api_key}"}
#             files = {
#                 "file": ("audio.webm", io.BytesIO(audio_bytes), "audio/webm"),
#                 "model": (None, os.getenv("WHISPER_MODEL", "whisper-large-v3")),
#             }
#             # Whisper endpoint is usually /audio/transcriptions
#             resp = requests.post(f"{self.llm_base_url}/audio/transcriptions", headers=headers, files=files, timeout=30)
#             if resp.status_code == 200:
#                 t = resp.json().get("text", "")
#                 return {"ok": True, "text": t}
#             return {"ok": False, "text": f"LLM Error: {resp.status_code} - {resp.text}"}
#         except Exception as e:
#             return {"ok": False, "text": f"Verbindungsfehler: {str(e)}"}

#     def _try_dataframe_answer(self, question: str) -> Optional[Dict[str, Any]]:
#         ql = (question or "").lower()
        
#         # 0. STRICT BYPASS: If this is an update command, we MUST use the Agentic Engine
#         update_keywords = ["update", "ändern", "setze", "change", "aktualisier", "korrigier", "fix", "put", "schreib"]
#         if any(x in ql for x in update_keywords):
#             return None

#         self.unified_df = get_unified_df()
        
#         # 1. Direct ID Lookup (Prioritized for Queries only)
#         id_match = re.search(r'(\d+)', ql)
#         if id_match and not any(x in ql for x in ["älter", "jahre", "vor", "nach", "count", "anzahl", "old", "older", "years", "more", "over", "über", "list", "table", "tabelle", "alle", "all"]):
#             sid = id_match.group(1)
#             search_df = self.unified_df.copy()
            
#             # Smart Sparten Filter (Optional)
#             target_sparte = None
#             if "gas" in ql: target_sparte = "Gas"
#             elif "wasser" in ql: target_sparte = "Wasser"
            
#             if target_sparte:
#                 search_df = search_df[search_df["Sparte"] == target_sparte]
            
#             # Find the ID
#             matches = pd.DataFrame()
#             for col in ["Kundennummer", "Objekt-ID", "Objekt-ID_Global"]:
#                 if col in search_df.columns:
#                     mask = search_df[col].astype(str).str.contains(rf'\b{sid}\b', regex=True, na=False)
#                     if mask.any():
#                         matches = search_df[mask]
#                         break
            
#             if not matches.empty:
#                 res = matches.iloc[0]
#                 lines = [f"✅ **Datensatz gefunden: {res.get('Sparte', '')} - {res.get('Kundennummer', sid)}**", ""]
                
#                 # Check specifics
#                 if any(x in ql for x in ["material", "werkstoff", "type", "art"]):
#                     lines.append(f"🏗️ **Material:** {res.get('Werkstoff', 'n/a')} ({res.get('Dimension', '')})")
                
#                 if any(x in ql for x in ["strasse", "straße", "hausnummer", "address", "location"]):
#                     lines.append(f"📍 **Adresse:** {res.get('Straße', 'n/a')} {res.get('Hausnummer', '')}")
#                     lines.append(f"🏙️ **Ort:** {res.get('Postleitzahl', '')} {res.get('Gemeinde', '')}")

#                 if any(x in ql for x in ["alter", "age", "year", "einbau"]):
#                     lines.append(f"⏳ **Alter:** {int(res.get('Alter', 0))} Jahre (Einbau: {res.get('Einbaujahr', 'unbekannt')})")

#                 if len(lines) <= 2: # Show all if vague
#                     lines.append(f"📍 **Adresse:** {res.get('Straße', 'n/a')} {res.get('Hausnummer', '')}")
#                     lines.append(f"🏗️ **Material:** {res.get('Werkstoff', 'n/a')}")
#                     lines.append(f"⚠️ **Risiko:** {res.get('Risiko', 'n/a')}")
                
#                 if any(x in ql for x in ["karte", "map", "zeige", "view", "show"]):
#                     if pd.notna(res.get("lat")) and pd.notna(res.get("lon")):
#                         return {
#                             "answer": f"📍 **Navigation zur Karte gestartet...**\nIch zeige Ihnen den Anschluss `{res.get('Kundennummer', sid)}` ({res.get('Sparte', '')}) in der `{res.get('Straße', '')} {res.get('Hausnummer', '')}` auf der Karte.",
#                             "hits": [],
#                             "model_used": "Navigation-Engine-v1",
#                             "switched": True,
#                             "pending_action": {
#                                 "type": "navigate_map",
#                                 "args": {
#                                     "customer_id": str(res.get("Kundennummer", sid)),
#                                     "lat": float(res["lat"]),
#                                     "lon": float(res["lon"])
#                                 }
#                             }
#                         }
#                     else:
#                         return {"answer": f"⚠️ Der Kunde `{sid}` wurde gefunden, hat aber leider keine Koordinaten für die Karte.", "hits": [], "model_used": "Navigation-Engine-v1", "switched": True}

#                 # ── Only attach download_data if specifically requested (Strict Keywords) ──
#                 dl_requested = any(x in ql for x in ["excel", "csv", "tabelle", "table", "format", "tabular"])
#                 resp = {"answer": "\n".join(lines), "hits": [], "model_used": "Direct-ID-Engine-v2", "switched": True}
#                 if dl_requested:
#                     resp["download_data"] = matches.to_csv(index=False).encode('utf-8-sig')
#                 return resp

#         # 1.5 Quick Count Analysis
#         if any(x in ql for x in ["wie viele", "how many", "how much", "anzahl", "count", "summe", "total", "wieviel", "kritisch", "critical"]):
#             target_sparte = None
#             if "gas" in ql: target_sparte = "Gas"
#             elif "wasser" in ql: target_sparte = "Wasser"
#             elif "strom" in ql: target_sparte = "Strom"
            
#             # Risk Filter
#             target_risk = None
#             if any(x in ql for x in ["risk", "risiko", "kritisch", "critical", "gefahr", "danger"]):
#                 if any(x in ql for x in ["hoch", "high", "kritisch", "critical", "gefahr", "danger"]): target_risk = "Hoch"
#                 elif any(x in ql for x in ["mittel", "medium"]): target_risk = "Mittel"
#                 elif any(x in ql for x in ["niedrig", "low", "gut", "good"]): target_risk = "Niedrig"
#                 else: target_risk = "Hoch" # Default for "at risk"
            
#             df = self.unified_df.copy()
#             if target_sparte:
#                 df = df[df["Sparte"] == target_sparte]
#             if target_risk:
#                 df = df[df["Risiko"] == target_risk]
            
#             total = len(df)
#             if total > 0:
#                 risk_str = f" mit Risiko-Status **{target_risk}**" if target_risk else ""
#                 msg = f"Wir haben insgesamt **{total} {target_sparte or 'Netz-'}Anschlüsse**{risk_str} im System erfasst."
#                 if not target_sparte and not target_risk:
#                     counts = self.unified_df["Sparte"].value_counts().to_dict()
#                     msg += " Aufgeschlüsselt nach Sparten: " + ", ".join([f"{k}: {v}" for k, v in counts.items()])
#                 return {"answer": msg, "hits": [], "model_used": "Count-Engine-v3", "switched": True}

#         # 2. Greetings (Fixed for False Positives like "whicH I...")
#         if ql.strip() in ["hi", "hallo", "hello", "guten tag", "hey"]:
#             return {"answer": "Guten Tag! Ich bin das ESC Infrastructure Intelligence System. Wie kann ich Ihnen heute bei der Analyse Ihrer Gas- oder Wasser-Anschlussdaten helfen?", "hits": [], "model_used": "System", "switched": False}

#         # 3. Analytical Trends (Materials over time)
#         if any(x in ql for x in ["material", "werkstoff", "anschlussart"]) and any(x in ql for x in ["wann", "verbaut", "historisch", "zeitraum"]):
#             try:
#                 df = self.unified_df.copy()
#                 df["Dekade"] = (df["Einbaujahr"] // 10) * 10
#                 summary = df.groupby(["Dekade", "Werkstoff"]).size().unstack(fill_value=0)
#                 lines = ["📜 **Historische Analyse: Materialverwendung**", ""]
#                 for decade in sorted(summary.index.dropna()):
#                     if decade < 1920: continue
#                     mats = summary.loc[decade]
#                     top = mats[mats > 0].sort_values(ascending=False)
#                     mat_str = ", ".join([f"{m} ({q})" for m, q in top.items()])
#                     lines.append(f"- **{int(decade)}er Jahre**: {mat_str}")
#                 return {"answer": "\n".join(lines), "hits": [], "model_used": "History-Engine", "switched": True, "download_data": summary.to_csv().encode('utf-8-sig')}
#             except: pass

#         # 4. Numeric Filters
#         age_match = re.search(r'(älter|older|>|über|over|more\s*than)\s*(?:als\s*|than\s*)?(\d+)', ql)
#         if age_match:
#             try:
#                 threshold = int(age_match.group(2))
#                 matches = self.unified_df[self.unified_df["Alter"] > threshold].sort_values("Alter", ascending=False)
#                 if not matches.empty:
#                     lines = [f"📊 **Analyse: {len(matches)} Objekte > {threshold} Jahre**", "Top Treffer:", ""]
#                     for _, r in matches.head(5).iterrows():
#                         lines.append(f"- {r['Sparte']} ({r['Kundennummer']}): {r['Straße']} | **{int(r['Alter'])} J.**")
#                     # ── Only attach download_data if specifically requested (Strict Keywords) ──
#                     dl_requested = any(x in ql for x in ["excel", "csv", "tabelle", "table", "format", "tabular"])
#                     resp = {"answer": "\n".join(lines), "hits": [], "model_used": "Filter-Engine", "switched": True}
#                     if dl_requested:
#                         resp["download_data"] = matches.to_csv(index=False).encode('utf-8-sig')
#                     return resp
#             except: pass

#         # 5. Full Table / Listing (Catch queries like "all wasser connections")
#         table_keywords = ["liste", "tabelle", "alle", "list", "table", "all", "übersicht", "total", "excel", "csv", "daten", "format"]
#         if any(x in ql for x in table_keywords):
#             target_sparte = None
#             if "gas" in ql: target_sparte = "Gas"
#             elif "wasser" in ql: target_sparte = "Wasser"
            
#             df = self.unified_df.copy()
#             if target_sparte:
#                 # Use str.contains with case-insensitivity to be resilient
#                 df = df[df["Sparte"].astype(str).str.contains(target_sparte, case=False, na=False)]
            
#             # --- Smart NLP Filters for Tables ---
#             # 1. Risk Filter
#             if any(x in ql for x in ["high risk", "hohes risiko", "risiko hoch", "hoch"]):
#                 df = df[df["Risiko"] == "Hoch"]
#             elif any(x in ql for x in ["medium", "mittel", "mittleres risiko"]):
#                 df = df[df["Risiko"] == "Mittel"]
#             elif any(x in ql for x in ["low", "niedrig", "gering"]):
#                 df = df[df["Risiko"] == "Niedrig"]
                
#             # 2. Address Filter
#             unique_streets = [str(s) for s in df["Straße"].dropna().unique() if len(str(s)) > 3]
#             matched_streets = [s for s in unique_streets if s.lower() in ql]
#             if matched_streets:
#                 best_street = max(matched_streets, key=lambda x: len(x))
#                 df = df[df["Straße"] == best_street]
                
#                 # Check for Hausnummer
#                 hn_match = re.search(r'\b\d{1,4}[a-zA-Z]?\b', ql.replace(best_street.lower(), ''))
#                 if hn_match:
#                     num = hn_match.group()
#                     df = df[df["Hausnummer"].astype(str).str.lower() == num.lower()]

#             if target_sparte:
#                 answer = f"✅ **{target_sparte}-Übersicht**: Ich habe {len(df)} Anschlüsse gefunden."
#             else:
#                 answer = f"✅ **Gesamtübersicht**: Ich habe {len(df)} Anschlüsse gefunden."
            
#             if not df.empty:
#                 # Generate a clean Markdown table for preview (top 15)
#                 # Reorder columns to show Kundenname first
#                 cols = ["Kundenname", "Kundennummer", "Sparte", "Straße", "Hausnummer", "Risiko", "Alter"]
#                 available_cols = [c for c in cols if c in df.columns]
#                 preview_df = df[available_cols].head(15)
#                 table_md = preview_df.to_markdown(index=False)
                
#                 # ── Only attach download_data if specifically requested (Strict Keywords) ──
#                 dl_requested = any(x in ql for x in ["excel", "csv", "tabelle", "table", "format", "tabular"])
                
#                 resp = {
#                     "answer": f"{answer}\n\n{table_md}\n\n*(Oben sehen Sie die ersten 15 Zeilen. Nutzen Sie den Button unten für den vollständigen Export als CSV)*",
#                     "hits": [],
#                     "model_used": "Full-Table-Engine",
#                     "switched": True
#                 }
#                 if dl_requested:
#                     resp["download_data"] = df.to_csv(index=False).encode('utf-8-sig')
#                 return resp
#             else:
#                 return {
#                     "answer": f"📊 **Tabelle**: Ich konnte leider keine Daten für '{target_sparte or 'Gesamt'}' finden, die Ihrer Anfrage entsprechen.",
#                     "hits": [],
#                     "model_used": "Full-Table-Engine",
#                     "switched": True
#                 }

#         # 6. General Map Navigation (Only triggers if NO table keywords are present)
#         map_keywords = ["karte", "map", "landkarte", "netz-karte", "zeige", "view", "show", "öffne", "open"]
#         if any(x in ql for x in map_keywords) and not id_match and not any(x in ql for x in table_keywords):
#              return {
#                 "answer": "🗺️ **Ich erstelle die Netz-Karte direkt hier im Chat...**",
#                 "hits": [],
#                 "model_used": "Navigation-Engine-v1",
#                 "switched": True,
#                 "pending_action": {"type": "navigate_map_general", "args": {"filter": target_sparte or "All"}}
#              }

#         return None

#     def answer_question(self, question: str, utility: Optional[str] = None, history: Optional[List[Dict]] = None) -> Dict[str, Any]:
#         ql = (question or "").lower()
        
#         # 0. SKIP FAST ENGINE FOR UPDATES (Force Agentic Tool Mode)
#         update_keywords = ["update", "ändern", "setze", "change", "aktualisier", "korrigier", "fix", "put", "schreib"]
#         is_update = any(x in ql for x in update_keywords)
        
#         search_query = question
#         if history:
#             history_to_use = history[:-1] if history and history[-1].get("content", "") == question else history
#             last_user_msg = next((h["content"] for h in reversed(history_to_use) if h["role"] == "user"), "")
            
#             # If current question is a follow up (short or lacks numbers), prepend the previous user message for context
#             if last_user_msg and len(question.split()) < 10 and not re.search(r'\d+', question):
#                 search_query = f"{last_user_msg}. {question}"
                
#         # For the fast lookup dataframe engine, we might also want to try the search_query to pull the right ID context
#         if not is_update:
#             df_res = self._try_dataframe_answer(search_query)  # Use the context-aware query here too!
#             if df_res: 
#                 return df_res

#         status = self.check_llm_status()
#         if not status["ok"]:
#             return {"answer": f"⚠️ **Service-Status**: {status['msg']}", "hits": [], "model_used": "Status-Check", "switched": False}

#         hits = []
#         try:
#             results = self.vs.query(query_embeddings=self.embedder.embed([search_query]), top_k=4)
#             hits = [{"meta": m, "doc": d, "score": 1-dist} for m, d, dist in zip(results["metadatas"][0], results["documents"][0], results["distances"][0])]
            
#             ctx = "\n---\n".join([h["doc"] for h in hits])
            
#             headers = {
#                 "Authorization": f"Bearer {self.llm_api_key}",
#                 "Content-Type": "application/json"
#             }

#             if is_update:
#                 # --- AGENTIC MODE: send tools for write operations ---
#                 tools = [
#                     {
#                         "type": "function",
#                         "function": {
#                             "name": "update_asset",
#                             "description": "Updates any field of a utility asset in the database. Call this when the user asks to change, set, or update any value.",
#                             "parameters": {
#                                 "type": "object",
#                                 "properties": {
#                                     "customer_id": {"type": "string", "description": "Customer ID, e.g. '3' or 'Kunde 3'."},
#                                     "field_name": {"type": "string", "description": "Column to update, e.g. Hausnummer, Schutzrohr, Werkstoff, Installateur Name, Gemeinde, Gestattungsvertrag, etc."},
#                                     "new_value": {"type": "string", "description": "New value to write."},
#                                     "utility": {"type": "string", "enum": ["Gas", "Wasser", "Gemeinsam"], "description": "Utility sector. Use Gemeinsam for shared fields."}
#                                 },
#                                 "required": ["customer_id", "field_name", "new_value", "utility"]
#                             }
#                         }
#                     },
#                     {
#                         "type": "function",
#                         "function": {
#                             "name": "navigate_to_map",
#                             "description": "Navigates to the map view for a specific customer or the general map. Call this when the user asks to see a customer, an address, or simply 'the map'.",
#                             "parameters": {
#                                 "type": "object",
#                                 "properties": {
#                                     "customer_id": {"type": "string", "description": "Optional Customer ID to show on map. If omitted, shows general map."}
#                                 }
#                             }
#                         }
#                     }
#                 ]
#                 payload = {
#                     "model": self.llm_model,
#                     "messages": [
#                         {"role": "system", "content": (
#                             "You are the ESC Agentic Assistant. You have tools to update the database and navigate the map. "
#                             "When explaining 'Risiko' (Risk), strictly reference these Technical Life Tables:\n"
#                             f"{ENGINEERING_STANDARDS}\n"
#                             "1. If the user asks to change/update a value, use 'update_asset'. "
#                             "2. If the user asks to see a customer or address on the map OR simply requests the map view, use 'navigate_to_map'. "
#                             "CRITICAL: If the user wants to see the map, ONLY call the tool. Do NOT provide coordinates in text. "
#                             "Be proactive. In the same language as the question."
#                         )}
#                     ],
#                     "tools": tools,
#                     "tool_choice": "auto",
#                     "temperature": 0.0,
#                     "max_tokens": 300
#                 }
#                 # Add history if available (map 'bot' to 'assistant')
#                 if history:
#                     history_to_use = history[:-1] if history[-1].get("content", "") == question else history
#                     for h in history_to_use[-6:]:
#                         role = "assistant" if h["role"] == "bot" else h["role"]
#                         payload["messages"].append({"role": role, "content": h["content"]})
                
#                 payload["messages"].append({"role": "user", "content": f"Question: {question}"})
#             else:
#                 # --- FAST READ MODE WITHOUT TOOLS ---
#                 # We disable tools for read mode completely to prevent hallucination, rely on fast-engine for map nav.
#                 payload = {
#                     "model": self.llm_model,
#                     "messages": [
#                         {"role": "system", "content": (
#                             "You are an infrastructure data expert for energy networks (Gas, Wasser). "
#                             "Answer questions accurately based on Data and Engineering Standards. "
#                             "When explaining 'Risiko' (Risk), strictly reference the Technical Life Tables. "
#                             "NEVER say you don't have enough data for counts; look at the Summary below.\n"
#                             f"{self.reference_manual[:1500]}\n"
#                         )}
#                     ],
#                     "temperature": 0.1,
#                     "max_tokens": 600
#                 }
#                 if history:
#                     history_to_use = history[:-1] if history[-1].get("content", "") == question else history
#                     for h in history_to_use[-6:]:
#                         role = "assistant" if h["role"] == "bot" else h["role"]
#                         payload["messages"].append({"role": role, "content": h["content"]})
                
#                 payload["messages"].append({"role": "user", "content": f"Data:\n{ctx}\n\nQuestion: {question}"})

#             resp = requests.post(f"{self.llm_base_url}/chat/completions", headers=headers, json=payload, timeout=30)
#             if resp.status_code == 200:
#                 choice = resp.json()["choices"][0]
#                 msg = choice["message"]
                
#                 # Check for tool calls
#                 if "tool_calls" in msg and msg["tool_calls"]:
#                     tc = msg["tool_calls"][0]["function"]
#                     args = json.loads(tc["arguments"])
                    
#                     if tc["name"] == "update_asset":
#                         return {
#                             "answer": f"🤖 Update erkannt:\n- **Kunde:** `{args.get('customer_id')}`\n- **Feld:** `{args.get('field_name')}`\n- **Neuer Wert:** `{args.get('new_value')}`\n- **Sparte:** `{args.get('utility')}`",
#                             "hits": hits,
#                             "model_used": self.llm_model,
#                             "pending_action": {"type": "update_asset", "args": args}
#                         }
                    
#                     if tc["name"] == "navigate_to_map":
#                         # Try to find the customer in unified_df to get coordinates
#                         sid = args.get("customer_id")
#                         if not sid:
#                             return {
#                                 "answer": "🗺️ **Ich öffne die Netz-Karte für Sie...**",
#                                 "hits": hits,
#                                 "model_used": self.llm_model,
#                                 "pending_action": {"type": "navigate_map_general", "args": {}}
#                             }

#                         if self.unified_df.empty: self.unified_df = get_unified_df()
#                         # Find the ID (fuzzy)
#                         matches = pd.DataFrame()
#                         for col in ["Kundennummer", "Objekt-ID", "Objekt-ID_Global"]:
#                             if col in self.unified_df.columns:
#                                 mask = self.unified_df[col].astype(str).str.contains(rf'\b{sid}\b', regex=True, na=False)
#                                 if mask.any():
#                                     matches = self.unified_df[mask]
#                                     break
                                    
#                         if not matches.empty:
#                             res = matches.iloc[0]
#                             if pd.notna(res.get("lat")) and pd.notna(res.get("lon")):
#                                 return {
#                                     "answer": f"📍 **Navigation zur Karte...**\nIch zeige Ihnen den Anschluss `{res.get('Kundennummer')}` on the map.",
#                                     "hits": hits,
#                                     "model_used": self.llm_model,
#                                     "pending_action": {
#                                         "type": "navigate_map", 
#                                         "args": {
#                                             "customer_id": str(res.get("Kundennummer")),
#                                             "lat": float(res["lat"]),
#                                             "lon": float(res["lon"])
#                                         }
#                                     }
#                                 }
                        
#                         # General map navigation if no specific match or no coordinates
#                         return {
#                             "answer": "🗺️ **Ich öffne die Netz-Karte für Sie...**",
#                             "hits": hits,
#                             "model_used": self.llm_model,
#                             "pending_action": {"type": "navigate_map_general", "args": {}}
#                         }

#                 answer = msg.get("content", "")
#                 return {"answer": answer, "hits": hits, "model_used": self.llm_model, "switched": False}
#         except: pass

#         if hits:
#             fallback = "⏱️ **Zeitüberschreitung**: Relevantes aus der Datenbank:\n\n" + "\n".join([f"- {h['doc']}" for h in hits[:2]])
#             return {"answer": fallback, "hits": hits, "model_used": "Timeout-Fallback", "switched": False}
        
#         return {"answer": "Keine Antwort gefunden.", "hits": [], "model_used": "Error", "switched": False}

#     def chat_general(self, user_message: str, history: List[Dict]) -> Dict[str, Any]:
#         return self.answer_question(user_message, history=history)



# -*- coding: utf-8 -*-
"""
rag_engine.py — Multi-Utility Hybrid Engine (Gas | Strom | Wasser)
Strictly Offline Version using Gemma 3 via Ollama.

FIXED: Risk assessment accuracy, engineering standards alignment,
       LLM prompt completeness, and dataframe-based risk explanations.
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

from geo_utils import (
    load_excel, CSV_FILES, ALL_UTILITIES, MATERIAL_LIFESPAN,
    get_utility_df, get_unified_df, RISK_LADDER, CURRENT_YEAR
)

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
    general_keys = ["Gemeinde", "Postleitzahl", "Straße", "Hausnummer", "Objekt-ID_Global"]
    util_specific = {k: v for k, v in row.items() if k not in general_keys and k != "Sparte"}
    parts = []
    if utility: parts.append(f"VERSORGUNGSART: {utility}")
    gen = [f"{k}: {_safe(row.get(k))}" for k in general_keys if row.get(k) and pd.notna(row.get(k))]
    if gen: parts.append("ALLGEMEINE OBJEKTDATEN: " + ", ".join(gen))
    spec = [f"{k}: {_safe(v)}" for k, v in util_specific.items() if pd.notna(v) and str(v).strip() not in ("", "nan")]
    if spec: parts.append(f"DATEN ZUM NETZANSCHLUSS {utility}: " + ", ".join(spec))
    return " | ".join(parts) + "."


# ─────────────── Engineering Standards ────────────────────────────────────────
# FIX: Build ENGINEERING_STANDARDS dynamically from RISK_LADDER in geo_utils.py
# so there is ONE single source of truth. No more hand-typed thresholds that
# can drift out of sync with the actual classification logic.
# ─────────────────────────────────────────────────────────────────────────────
def _build_engineering_standards() -> str:
    """
    Dynamically generates the Engineering Standards text from the RISK_LADDER
    defined in geo_utils.py. This guarantees the LLM always sees the same
    thresholds that the classification engine uses — no duplication, no drift.
    """
    lines = [
        "TECHNICAL LIFE TABLES — RISK CLASSIFICATION (Risikobewertung):",
        "=" * 60,
        "Risk levels are assigned per material based on installation age (Alter = CURRENT_YEAR - Einbaujahr).",
        "",
        "Rule:  age <= gut_threshold  →  Niedrig (Low Risk)",
        "       age <= mittel_threshold →  Mittel  (Medium Risk)",
        "       age >  mittel_threshold →  Hoch    (High Risk)",
        "",
    ]
    for sparte, profiles in RISK_LADDER.items():
        lines.append(f"── {sparte.upper()} ──")
        seen = set()
        for p in profiles:
            mat = p["material"]
            if mat in seen:
                continue
            seen.add(mat)
            lines.append(
                f"  {mat:30s}  Niedrig: 0–{p['gut']}J  |  Mittel: {p['gut']+1}–{p['mittel']}J  "
                f"|  Hoch: >{p['mittel']}J  |  TechNutzungsdauer: {p['life']}J"
            )
        lines.append("")

    # Add materials that use the generic MATERIAL_LIFESPAN fallback
    lines.append("── FALLBACK (materials not in sparte-specific ladder) ──")
    for mat, life in MATERIAL_LIFESPAN.items():
        lines.append(
            f"  {mat:30s}  Niedrig: 0–{int(life*0.65)}J  |  Mittel: {int(life*0.65)+1}–{int(life*0.85)}J  "
            f"|  Hoch: >{int(life*0.85)}J  |  TechNutzungsdauer: {life}J"
        )
    lines.append("")
    lines.append(f"Reference year for age calculation: {CURRENT_YEAR}")
    return "\n".join(lines)

ENGINEERING_STANDARDS: str = _build_engineering_standards()


def _risk_explanation(row: pd.Series) -> str:
    """
    Returns a human-readable explanation of WHY a connection has its risk level,
    referencing the exact thresholds from RISK_LADDER.
    Used both in dataframe answers and as LLM context.
    """
    sparte   = str(row.get("Sparte", ""))
    material = str(row.get("Werkstoff", "Unbekannt")).strip()
    alter    = row.get("Alter", 0)
    risiko   = str(row.get("Risiko", "Unbekannt"))

    if not alter or pd.isna(alter):
        return f"Risiko: {risiko} (Einbaudatum unbekannt — kein Alter berechenbar)"

    alter = float(alter)

    # Look up the profile that was used
    profile = None
    if sparte in RISK_LADDER:
        mat_lower = material.lower()
        for p in RISK_LADDER[sparte]:
            if p["material"].lower() in mat_lower:
                profile = p
                break

    if profile:
        gut    = profile["gut"]
        mittel = profile["mittel"]
        life   = profile["life"]
        if alter <= gut:
            return (
                f"Risiko: **Niedrig** — Material '{material}' ({sparte}), Alter {int(alter)}J. "
                f"Schwellenwert Niedrig: ≤{gut}J, Mittel: {gut+1}–{mittel}J, Hoch: >{mittel}J. "
                f"TechNutzungsdauer: {life}J."
            )
        elif alter <= mittel:
            remaining = life - alter
            return (
                f"Risiko: **Mittel** — Material '{material}' ({sparte}), Alter {int(alter)}J. "
                f"Schwellenwert Niedrig: ≤{gut}J, Mittel: {gut+1}–{mittel}J, Hoch: >{mittel}J. "
                f"Noch ca. {int(remaining)}J bis Ende TechNutzungsdauer ({life}J)."
            )
        else:
            overdue = alter - life
            return (
                f"Risiko: **Hoch** ⚠️ — Material '{material}' ({sparte}), Alter {int(alter)}J. "
                f"Schwellenwert Hoch: >{mittel}J (überschritten). "
                f"TechNutzungsdauer ({life}J) um {int(overdue)}J überschritten — Erneuerung dringend!"
            )
    else:
        # Fallback lifespan
        life = MATERIAL_LIFESPAN.get(material, 50)
        pct  = alter / life
        status = "Hoch" if pct >= 0.85 else "Mittel" if pct >= 0.65 else "Niedrig"
        return (
            f"Risiko: **{status}** — Material '{material}' ({sparte}), Alter {int(alter)}J. "
            f"Fallback-TechNutzungsdauer: {life}J ({int(pct*100)}% verbraucht)."
        )


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
        import os
        os.environ["TQDM_DISABLE"] = "1"
        os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
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
        self.llm_base_url = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")

        self.unified_df = get_unified_df()
        self.stats_summary = ""
        self.refresh_stats_manual()  # Builds self.reference_manual

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
            headers = {"Authorization": f"Bearer {self.llm_api_key}"}
            resp = requests.get(f"{self.llm_base_url}/models", headers=headers, timeout=5)
            if resp.status_code == 200:
                provider_name = "Online" if "groq" in self.llm_base_url else "Custom Provider"
                return {"ok": True, "msg": f"{provider_name}: {self.llm_model}"}
            return {"ok": False, "msg": f"LLM Error: {resp.status_code}"}
        except Exception as e:
            return {"ok": False, "msg": f"Verbindungsfehler: {str(e)[:50]}"}

    def refresh_stats_manual(self):
        """
        Builds a dynamic stats summary AND the full engineering standards for the LLM.

        FIX: The old code truncated reference_manual to 1500 chars in the LLM system
        prompt, which silently dropped risk thresholds. Now we store standards and
        stats separately and inject them in full into every prompt.
        """
        if self.unified_df.empty:
            self.unified_df = get_unified_df()
        df = self.unified_df

        total = len(df)
        risks  = df["Risiko"].value_counts().to_dict() if not df.empty else {}
        sparten = df["Sparte"].value_counts().to_dict() if not df.empty else {}

        # Per-sparte risk breakdown — gives LLM concrete numbers to cite
        risk_by_sparte_lines = []
        if not df.empty:
            for sp in df["Sparte"].unique():
                sp_df = df[df["Sparte"] == sp]
                r = sp_df["Risiko"].value_counts().to_dict()
                risk_by_sparte_lines.append(
                    f"  {sp}: Hoch={r.get('Hoch',0)}, Mittel={r.get('Mittel',0)}, "
                    f"Niedrig={r.get('Niedrig',0)}, Unbekannt={r.get('Unbekannt',0)}"
                )

        self.stats_summary = (
            f"CURRENT INFRASTRUCTURE SUMMARY (as of {CURRENT_YEAR}):\n"
            f"- TOTAL CONNECTIONS: {total}\n"
            f"- DISTRIBUTION: {', '.join([f'{k}: {v}' for k, v in sparten.items()])}\n"
            f"- OVERALL RISK LEVELS: {', '.join([f'{k}: {v}' for k, v in risks.items()])}\n"
            f"- RISK BY SPARTE:\n" + "\n".join(risk_by_sparte_lines)
        )

        # FIX: reference_manual now contains FULL engineering standards (no truncation).
        # The LLM system prompt will inject this directly.
        self.reference_manual = (
            self.stats_summary
            + "\n\n"
            + ENGINEERING_STANDARDS
        )

        # Append Word reference doc if present
        ref_path = "excel_data/Hausanschluss_KI_Referenzhandbuch.docx"
        if os.path.exists(ref_path):
            try:
                import docx as _docx
                doc = _docx.Document(ref_path)
                self.reference_manual += "\n" + "\n".join([p.text for p in doc.paragraphs])
            except:
                pass

    def init_or_refresh_kb(self, utility: Optional[str] = None, reset: bool = False) -> int:
        self.unified_df = get_unified_df()
        self.refresh_stats_manual()
        utils = [utility] if utility else ALL_UTILITIES

        if reset:
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
                metas.append({
                    "utility": util,
                    "id": str(row.get("Kundennummer", "")),
                    "name": str(row.get("Kundenname", ""))
                })

            if docs:
                batch_size = 500
                for j in range(0, len(docs), batch_size):
                    b_docs  = docs[j:j+batch_size]
                    b_ids   = ids[j:j+batch_size]
                    b_metas = metas[j:j+batch_size]
                    b_embeddings = self.embedder.embed(b_docs)
                    self.vs.add(ids=b_ids, embeddings=b_embeddings, metadatas=b_metas, documents=b_docs)
                    total += len(b_docs)

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
            resp = requests.post(
                f"{self.llm_base_url}/audio/transcriptions",
                headers=headers, files=files, timeout=30
            )
            if resp.status_code == 200:
                t = resp.json().get("text", "")
                return {"ok": True, "text": t}
            return {"ok": False, "text": f"LLM Error: {resp.status_code} - {resp.text}"}
        except Exception as e:
            return {"ok": False, "text": f"Verbindungsfehler: {str(e)}"}

    # ─────────────────────────────────────────────────────────────────────────
    # FAST DATAFRAME ENGINE
    # FIX: All risk-related branches now use _risk_explanation() to produce
    #      accurate, threshold-backed answers instead of generic counts.
    # ─────────────────────────────────────────────────────────────────────────
    def _try_dataframe_answer(self, question: str) -> Optional[Dict[str, Any]]:
        ql = (question or "").lower()

        # 0. Bypass for update commands → must go to Agentic Engine
        update_keywords = ["update", "ändern", "setze", "change", "aktualisier", "korrigier", "fix", "put", "schreib"]
        if any(x in ql for x in update_keywords):
            return None

        self.unified_df = get_unified_df()

        # ── 1. RISK DETAIL for a specific connection / ID ─────────────────────
        # Detect when user asks about risk for a specific customer / connection
        risk_keywords = [
            "risiko", "risk", "gefahr", "danger", "sicher", "safe", "kritisch",
            "critical", "warum", "why", "grund", "reason", "erklär", "explain",
            "bewertung", "assessment", "status", "level", "stufe"
        ]
        id_match = re.search(r'(\d+)', ql)

        if id_match and any(x in ql for x in risk_keywords):
            sid = id_match.group(1)
            search_df = self.unified_df.copy()

            target_sparte = None
            if "gas" in ql:   target_sparte = "Gas"
            elif "wasser" in ql: target_sparte = "Wasser"
            if target_sparte:
                search_df = search_df[search_df["Sparte"] == target_sparte]

            matches = pd.DataFrame()
            for col in ["Kundennummer", "Objekt-ID", "Objekt-ID_Global"]:
                if col in search_df.columns:
                    mask = search_df[col].astype(str).str.contains(rf'\b{sid}\b', regex=True, na=False)
                    if mask.any():
                        matches = search_df[mask]
                        break

            if not matches.empty:
                res = matches.iloc[0]
                explanation = _risk_explanation(res)
                lines = [
                    f"🔍 **Risikobewertung: {res.get('Sparte','')} — {res.get('Kundennummer', sid)}**",
                    f"📍 {res.get('Straße','?')} {res.get('Hausnummer','')}",
                    "",
                    explanation,
                    "",
                    f"🏗️ Material: `{res.get('Werkstoff','?')}` | Dimension: `{res.get('Dimension','?')}`",
                    f"📅 Einbaujahr: `{int(res['Einbaujahr']) if pd.notna(res.get('Einbaujahr')) else 'unbekannt'}`"
                    f" | Alter: `{int(res.get('Alter',0))}J`",
                    f"🔄 Erneuerung empfohlen bis: `{res.get('Erneuerung_empfohlen_bis','?')}`",
                ]
                return {"answer": "\n".join(lines), "hits": [], "model_used": "Risk-Detail-Engine-v2", "switched": True}

        # ── 2. General ID Lookup (no risk keywords — show full record) ────────
        if id_match and not any(x in ql for x in [
            "älter", "jahre", "vor", "nach", "count", "anzahl", "old", "older",
            "years", "more", "over", "über", "list", "table", "tabelle", "alle", "all"
        ]):
            sid = id_match.group(1)
            search_df = self.unified_df.copy()

            target_sparte = None
            if "gas" in ql:    target_sparte = "Gas"
            elif "wasser" in ql: target_sparte = "Wasser"
            if target_sparte:
                search_df = search_df[search_df["Sparte"] == target_sparte]

            matches = pd.DataFrame()
            for col in ["Kundennummer", "Objekt-ID", "Objekt-ID_Global"]:
                if col in search_df.columns:
                    mask = search_df[col].astype(str).str.contains(rf'\b{sid}\b', regex=True, na=False)
                    if mask.any():
                        matches = search_df[mask]
                        break

            if not matches.empty:
                res = matches.iloc[0]
                lines = [
                    f"✅ **Datensatz gefunden: {res.get('Sparte', '')} — {res.get('Kundennummer', sid)}**", ""
                ]

                if any(x in ql for x in ["material", "werkstoff", "type", "art"]):
                    lines.append(f"🏗️ **Material:** {res.get('Werkstoff', 'n/a')} ({res.get('Dimension', '')})")
                if any(x in ql for x in ["strasse", "straße", "hausnummer", "address", "location"]):
                    lines.append(f"📍 **Adresse:** {res.get('Straße', 'n/a')} {res.get('Hausnummer', '')}")
                    lines.append(f"🏙️ **Ort:** {res.get('Postleitzahl', '')} {res.get('Gemeinde', '')}")
                if any(x in ql for x in ["alter", "age", "year", "einbau"]):
                    lines.append(f"⏳ **Alter:** {int(res.get('Alter', 0))} Jahre (Einbau: {res.get('Einbaujahr', 'unbekannt')})")

                # Default: show all key fields
                if len(lines) <= 2:
                    lines.append(f"📍 **Adresse:** {res.get('Straße', 'n/a')} {res.get('Hausnummer', '')}")
                    lines.append(f"🏗️ **Material:** {res.get('Werkstoff', 'n/a')}")
                    lines.append(f"⚠️ **Risiko:** {res.get('Risiko', 'n/a')}")
                    lines.append(f"⏳ **Alter:** {int(res.get('Alter', 0))} Jahre")
                    lines.append(f"🔄 **Erneuerung bis:** {res.get('Erneuerung_empfohlen_bis', '?')}")

                # Map navigation
                if any(x in ql for x in ["karte", "map", "zeige", "view", "show"]):
                    if pd.notna(res.get("lat")) and pd.notna(res.get("lon")):
                        return {
                            "answer": (
                                f"📍 **Navigation zur Karte gestartet...**\n"
                                f"Ich zeige Ihnen den Anschluss `{res.get('Kundennummer', sid)}` "
                                f"({res.get('Sparte', '')}) in der "
                                f"`{res.get('Straße', '')} {res.get('Hausnummer', '')}` auf der Karte."
                            ),
                            "hits": [], "model_used": "Navigation-Engine-v1", "switched": True,
                            "pending_action": {
                                "type": "navigate_map",
                                "args": {
                                    "customer_id": str(res.get("Kundennummer", sid)),
                                    "lat": float(res["lat"]),
                                    "lon": float(res["lon"])
                                }
                            }
                        }
                    else:
                        return {
                            "answer": f"⚠️ Kunde `{sid}` gefunden, aber keine Koordinaten verfügbar.",
                            "hits": [], "model_used": "Navigation-Engine-v1", "switched": True
                        }

                dl_requested = any(x in ql for x in ["excel", "csv", "tabelle", "table", "format", "tabular"])
                resp = {"answer": "\n".join(lines), "hits": [], "model_used": "Direct-ID-Engine-v2", "switched": True}
                if dl_requested:
                    resp["download_data"] = matches.to_csv(index=False).encode('utf-8-sig')
                return resp

        # ── 3. RISK OVERVIEW — "how many are high risk / what is the risk?" ──
        # FIX: When user asks a general risk question (no specific ID), give a
        # full material-level breakdown so the answer is educational, not just a count.
        if any(x in ql for x in risk_keywords) and not id_match:
            target_sparte = None
            if "gas" in ql:    target_sparte = "Gas"
            elif "wasser" in ql: target_sparte = "Wasser"

            df = self.unified_df.copy()
            if target_sparte:
                df = df[df["Sparte"] == target_sparte]

            target_risk = None
            if any(x in ql for x in ["hoch", "high", "kritisch", "critical", "gefahr", "danger"]):
                target_risk = "Hoch"
            elif any(x in ql for x in ["mittel", "medium"]):
                target_risk = "Mittel"
            elif any(x in ql for x in ["niedrig", "low", "gut", "good"]):
                target_risk = "Niedrig"

            if target_risk:
                filtered = df[df["Risiko"] == target_risk]
            else:
                filtered = df

            total = len(df)
            lines = [
                f"📊 **Risiko-Übersicht{' — ' + target_sparte if target_sparte else ''}**",
                f"Gesamt: {total} Anschlüsse analysiert.",
                "",
            ]

            # Risk count summary
            risk_counts = df["Risiko"].value_counts()
            for level, emoji in [("Hoch", "🔴"), ("Mittel", "🟡"), ("Niedrig", "🟢"), ("Unbekannt", "⚪")]:
                cnt = risk_counts.get(level, 0)
                pct = round(100 * cnt / max(total, 1), 1)
                lines.append(f"{emoji} **{level}**: {cnt} ({pct}%)")

            lines.append("")
            lines.append("**Wie wird das Risiko berechnet?**")
            lines.append(
                "Das Risiko basiert auf dem Alter der Leitung im Vergleich zu den "
                "technischen Nutzungsdauern je Material (DVGW-Richtlinien):"
            )

            # Show thresholds per sparte
            sparten_to_show = [target_sparte] if target_sparte else list(RISK_LADDER.keys())
            for sp in sparten_to_show:
                if sp not in RISK_LADDER: continue
                lines.append(f"\n*{sp}:*")
                seen = set()
                for p in RISK_LADDER[sp]:
                    if p["material"] in seen: continue
                    seen.add(p["material"])
                    lines.append(
                        f"  • {p['material']}: Niedrig ≤{p['gut']}J | "
                        f"Mittel {p['gut']+1}–{p['mittel']}J | Hoch >{p['mittel']}J"
                    )

            # If a specific risk level was requested, show top examples
            if target_risk and not filtered.empty:
                lines.append(f"\n**Beispiele mit Risiko '{target_risk}'** (Top 5):")
                for _, r in filtered.sort_values("Alter", ascending=False).head(5).iterrows():
                    lines.append(
                        f"  → {r.get('Sparte','')} | {r.get('Straße','?')} {r.get('Hausnummer','')} | "
                        f"Material: {r.get('Werkstoff','?')} | Alter: {int(r.get('Alter',0))}J"
                    )

            return {
                "answer": "\n".join(lines),
                "hits": [], "model_used": "Risk-Overview-Engine-v2", "switched": True
            }

        # ── 4. Count Queries ──────────────────────────────────────────────────
        if any(x in ql for x in ["wie viele", "how many", "how much", "anzahl", "count",
                                   "summe", "total", "wieviel", "kritisch", "critical"]):
            target_sparte = None
            if "gas" in ql:    target_sparte = "Gas"
            elif "wasser" in ql: target_sparte = "Wasser"
            elif "strom" in ql:  target_sparte = "Strom"

            target_risk = None
            if any(x in ql for x in ["risk", "risiko", "kritisch", "critical", "gefahr", "danger"]):
                if any(x in ql for x in ["hoch", "high", "kritisch", "critical"]):
                    target_risk = "Hoch"
                elif any(x in ql for x in ["mittel", "medium"]):
                    target_risk = "Mittel"
                elif any(x in ql for x in ["niedrig", "low"]):
                    target_risk = "Niedrig"
                else:
                    target_risk = "Hoch"  # Default for unspecified "at risk"

            df = self.unified_df.copy()
            if target_sparte:
                df = df[df["Sparte"] == target_sparte]
            if target_risk:
                df = df[df["Risiko"] == target_risk]

            total = len(df)
            if total >= 0:
                risk_str = f" mit Risiko-Status **{target_risk}**" if target_risk else ""
                sparte_str = target_sparte or "Netz"
                msg = f"Wir haben insgesamt **{total} {sparte_str}-Anschlüsse**{risk_str} im System erfasst."
                if not target_sparte and not target_risk:
                    counts = self.unified_df["Sparte"].value_counts().to_dict()
                    msg += " Aufgeschlüsselt nach Sparten: " + ", ".join([f"{k}: {v}" for k, v in counts.items()])
                if target_risk:
                    msg += f"\n\n💡 *Hinweis: '{target_risk}' bedeutet, die Leitung hat die technische Nutzungsdauer für ihr Material überschritten oder befindet sich im kritischen Bereich. Siehe Risiko-Tabelle für Details.*"
                return {"answer": msg, "hits": [], "model_used": "Count-Engine-v3", "switched": True}

        # ── 5. Greetings ──────────────────────────────────────────────────────
        if ql.strip() in ["hi", "hallo", "hello", "guten tag", "hey"]:
            return {
                "answer": (
                    "Guten Tag! Ich bin das ESC Infrastructure Intelligence System. "
                    "Wie kann ich Ihnen heute bei der Analyse Ihrer Gas- oder Wasser-Anschlussdaten helfen?"
                ),
                "hits": [], "model_used": "System", "switched": False
            }

        # ── 6. Analytical Trends ──────────────────────────────────────────────
        if any(x in ql for x in ["material", "werkstoff", "anschlussart"]) and \
           any(x in ql for x in ["wann", "verbaut", "historisch", "zeitraum"]):
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
                return {
                    "answer": "\n".join(lines), "hits": [],
                    "model_used": "History-Engine", "switched": True,
                    "download_data": summary.to_csv().encode('utf-8-sig')
                }
            except:
                pass

        # ── 7. Numeric Age Filters ────────────────────────────────────────────
        age_match = re.search(r'(älter|older|>|über|over|more\s*than)\s*(?:als\s*|than\s*)?(\d+)', ql)
        if age_match:
            try:
                threshold = int(age_match.group(2))
                matches = self.unified_df[self.unified_df["Alter"] > threshold].sort_values("Alter", ascending=False)
                if not matches.empty:
                    lines = [f"📊 **Analyse: {len(matches)} Objekte älter als {threshold} Jahre**", "Top Treffer:", ""]
                    for _, r in matches.head(5).iterrows():
                        lines.append(
                            f"- {r['Sparte']} ({r['Kundennummer']}): {r.get('Straße','?')} | "
                            f"**{int(r['Alter'])}J** | Risiko: {r.get('Risiko','?')}"
                        )
                    dl_requested = any(x in ql for x in ["excel", "csv", "tabelle", "table", "format", "tabular"])
                    resp = {"answer": "\n".join(lines), "hits": [], "model_used": "Filter-Engine", "switched": True}
                    if dl_requested:
                        resp["download_data"] = matches.to_csv(index=False).encode('utf-8-sig')
                    return resp
            except:
                pass

        # ── 8. Full Table / Listing ───────────────────────────────────────────
        table_keywords = ["liste", "tabelle", "alle", "list", "table", "all",
                          "übersicht", "total", "excel", "csv", "daten", "format"]
        if any(x in ql for x in table_keywords):
            target_sparte = None
            if "gas" in ql:    target_sparte = "Gas"
            elif "wasser" in ql: target_sparte = "Wasser"

            df = self.unified_df.copy()
            if target_sparte:
                df = df[df["Sparte"].astype(str).str.contains(target_sparte, case=False, na=False)]

            # Smart NLP Filters
            if any(x in ql for x in ["high risk", "hohes risiko", "risiko hoch", "hoch"]):
                df = df[df["Risiko"] == "Hoch"]
            elif any(x in ql for x in ["medium", "mittel", "mittleres risiko"]):
                df = df[df["Risiko"] == "Mittel"]
            elif any(x in ql for x in ["low", "niedrig", "gering"]):
                df = df[df["Risiko"] == "Niedrig"]

            unique_streets = [str(s) for s in df["Straße"].dropna().unique() if len(str(s)) > 3]
            matched_streets = [s for s in unique_streets if s.lower() in ql]
            if matched_streets:
                best_street = max(matched_streets, key=lambda x: len(x))
                df = df[df["Straße"] == best_street]
                hn_match = re.search(r'\b\d{1,4}[a-zA-Z]?\b', ql.replace(best_street.lower(), ''))
                if hn_match:
                    num = hn_match.group()
                    df = df[df["Hausnummer"].astype(str).str.lower() == num.lower()]

            if target_sparte:
                answer = f"✅ **{target_sparte}-Übersicht**: {len(df)} Anschlüsse gefunden."
            else:
                answer = f"✅ **Gesamtübersicht**: {len(df)} Anschlüsse gefunden."

            if not df.empty:
                cols = ["Kundenname", "Kundennummer", "Sparte", "Straße", "Hausnummer", "Risiko", "Alter"]
                available_cols = [c for c in cols if c in df.columns]
                preview_df = df[available_cols].head(15)
                table_md = preview_df.to_markdown(index=False)
                dl_requested = any(x in ql for x in ["excel", "csv", "tabelle", "table", "format", "tabular"])
                resp = {
                    "answer": (
                        f"{answer}\n\n{table_md}\n\n"
                        "*(Oben sehen Sie die ersten 15 Zeilen. "
                        "Nutzen Sie den Button unten für den vollständigen Export als CSV)*"
                    ),
                    "hits": [], "model_used": "Full-Table-Engine", "switched": True
                }
                if dl_requested:
                    resp["download_data"] = df.to_csv(index=False).encode('utf-8-sig')
                return resp
            else:
                return {
                    "answer": (
                        f"📊 **Tabelle**: Keine Daten für "
                        f"'{target_sparte or 'Gesamt'}' gefunden, die Ihrer Anfrage entsprechen."
                    ),
                    "hits": [], "model_used": "Full-Table-Engine", "switched": True
                }

        # ── 9. General Map Navigation ─────────────────────────────────────────
        map_keywords = ["karte", "map", "landkarte", "netz-karte", "zeige", "view", "show", "öffne", "open"]
        target_sparte = None
        if "gas" in ql:    target_sparte = "Gas"
        elif "wasser" in ql: target_sparte = "Wasser"

        if any(x in ql for x in map_keywords) and not id_match and not any(x in ql for x in table_keywords):
            return {
                "answer": "🗺️ **Ich erstelle die Netz-Karte direkt hier im Chat...**",
                "hits": [], "model_used": "Navigation-Engine-v1", "switched": True,
                "pending_action": {
                    "type": "navigate_map_general",
                    "args": {"filter": target_sparte or "All"}
                }
            }

        return None

    # ─────────────────────────────────────────────────────────────────────────
    # MAIN ANSWER ENTRYPOINT
    # FIX: LLM system prompt now injects FULL engineering standards (no 1500-char
    #      truncation). Risk questions that fall through to the LLM will still
    #      get accurate threshold context.
    # ─────────────────────────────────────────────────────────────────────────
    def answer_question(
        self,
        question: str,
        utility: Optional[str] = None,
        history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        ql = (question or "").lower()

        update_keywords = ["update", "ändern", "setze", "change", "aktualisier",
                           "korrigier", "fix", "put", "schreib"]
        is_update = any(x in ql for x in update_keywords)

        # Build context-enriched query for follow-up questions
        search_query = question
        if history:
            history_to_use = (
                history[:-1]
                if history and history[-1].get("content", "") == question
                else history
            )
            last_user_msg = next(
                (h["content"] for h in reversed(history_to_use) if h["role"] == "user"), ""
            )
            if last_user_msg and len(question.split()) < 10 and not re.search(r'\d+', question):
                search_query = f"{last_user_msg}. {question}"

        # Fast dataframe engine (skipped for updates)
        if not is_update:
            df_res = self._try_dataframe_answer(search_query)
            if df_res:
                return df_res

        status = self.check_llm_status()
        if not status["ok"]:
            return {
                "answer": f"⚠️ **Service-Status**: {status['msg']}",
                "hits": [], "model_used": "Status-Check", "switched": False
            }

        hits = []
        try:
            results = self.vs.query(
                query_embeddings=self.embedder.embed([search_query]), top_k=4
            )
            hits = [
                {"meta": m, "doc": d, "score": 1 - dist}
                for m, d, dist in zip(
                    results["metadatas"][0],
                    results["documents"][0],
                    results["distances"][0]
                )
            ]
            ctx = "\n---\n".join([h["doc"] for h in hits])

            headers = {
                "Authorization": f"Bearer {self.llm_api_key}",
                "Content-Type": "application/json"
            }

            # ── AGENTIC MODE (write operations) ──────────────────────────────
            if is_update:
                tools = [
                    {
                        "type": "function",
                        "function": {
                            "name": "update_asset",
                            "description": (
                                "Updates any field of a utility asset in the database. "
                                "Call this when the user asks to change, set, or update any value."
                            ),
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "customer_id": {
                                        "type": "string",
                                        "description": "Customer ID, e.g. '3' or 'Kunde 3'."
                                    },
                                    "field_name": {
                                        "type": "string",
                                        "description": (
                                            "Column to update, e.g. Hausnummer, Schutzrohr, "
                                            "Werkstoff, Installateur Name, Gemeinde, "
                                            "Gestattungsvertrag, etc."
                                        )
                                    },
                                    "new_value": {
                                        "type": "string",
                                        "description": "New value to write."
                                    },
                                    "utility": {
                                        "type": "string",
                                        "enum": ["Gas", "Wasser", "Gemeinsam"],
                                        "description": "Utility sector. Use Gemeinsam for shared fields."
                                    }
                                },
                                "required": ["customer_id", "field_name", "new_value", "utility"]
                            }
                        }
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "navigate_to_map",
                            "description": (
                                "Navigates to the map view for a specific customer or the general map. "
                                "Call this when the user asks to see a customer, an address, or the map."
                            ),
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "customer_id": {
                                        "type": "string",
                                        "description": "Optional Customer ID. If omitted, shows general map."
                                    }
                                }
                            }
                        }
                    }
                ]
                # FIX: Full engineering standards injected into agentic mode too
                system_content = (
                    "You are the ESC Agentic Assistant with tools to update the database and navigate the map.\n\n"
                    "RISK CLASSIFICATION RULES — use these when explaining Risiko:\n"
                    f"{ENGINEERING_STANDARDS}\n\n"
                    "RULES:\n"
                    "1. To change/update a value → call 'update_asset'.\n"
                    "2. To show map / navigate → call 'navigate_to_map'.\n"
                    "CRITICAL: For map requests, ONLY call the tool — do NOT output coordinates as text.\n"
                    "Respond in the same language as the question."
                )
                payload = {
                    "model": self.llm_model,
                    "messages": [{"role": "system", "content": system_content}],
                    "tools": tools,
                    "tool_choice": "auto",
                    "temperature": 0.0,
                    "max_tokens": 400
                }
                if history:
                    h_slice = history[:-1] if history[-1].get("content", "") == question else history
                    for h in h_slice[-6:]:
                        role = "assistant" if h["role"] == "bot" else h["role"]
                        payload["messages"].append({"role": role, "content": h["content"]})
                payload["messages"].append({"role": "user", "content": f"Question: {question}"})

            # ── FAST READ MODE ────────────────────────────────────────────────
            else:
                # FIX: Inject FULL engineering standards + full stats summary.
                # Old code did reference_manual[:1500] which truncated everything.
                system_content = (
                    "You are an infrastructure data expert for energy networks (Gas, Wasser, Strom).\n\n"
                    "Answer questions accurately based on the data and Engineering Standards below.\n"
                    "When explaining Risiko (Risk), you MUST reference the exact thresholds from the "
                    "Technical Life Tables — never guess or generalize.\n\n"
                    f"{self.reference_manual}\n"
                    "\nIMPORTANT:\n"
                    "- NEVER say you lack data for counts; use the summary above.\n"
                    "- For risk questions always cite material + age + threshold.\n"
                    "- Respond in the same language as the question."
                )
                payload = {
                    "model": self.llm_model,
                    "messages": [{"role": "system", "content": system_content}],
                    "temperature": 0.1,
                    "max_tokens": 800   # FIX: was 600, increased for detailed risk explanations
                }
                if history:
                    h_slice = history[:-1] if history[-1].get("content", "") == question else history
                    for h in h_slice[-6:]:
                        role = "assistant" if h["role"] == "bot" else h["role"]
                        payload["messages"].append({"role": role, "content": h["content"]})
                payload["messages"].append({
                    "role": "user",
                    "content": f"Relevant data from database:\n{ctx}\n\nQuestion: {question}"
                })

            resp = requests.post(
                f"{self.llm_base_url}/chat/completions",
                headers=headers, json=payload, timeout=30
            )
            if resp.status_code == 200:
                choice = resp.json()["choices"][0]
                msg = choice["message"]

                # Tool calls (agentic mode)
                if "tool_calls" in msg and msg["tool_calls"]:
                    tc   = msg["tool_calls"][0]["function"]
                    args = json.loads(tc["arguments"])

                    if tc["name"] == "update_asset":
                        return {
                            "answer": (
                                f"🤖 Update erkannt:\n"
                                f"- **Kunde:** `{args.get('customer_id')}`\n"
                                f"- **Feld:** `{args.get('field_name')}`\n"
                                f"- **Neuer Wert:** `{args.get('new_value')}`\n"
                                f"- **Sparte:** `{args.get('utility')}`"
                            ),
                            "hits": hits, "model_used": self.llm_model,
                            "pending_action": {"type": "update_asset", "args": args}
                        }

                    if tc["name"] == "navigate_to_map":
                        sid = args.get("customer_id")
                        if not sid:
                            return {
                                "answer": "🗺️ **Ich öffne die Netz-Karte für Sie...**",
                                "hits": hits, "model_used": self.llm_model,
                                "pending_action": {"type": "navigate_map_general", "args": {}}
                            }
                        if self.unified_df.empty:
                            self.unified_df = get_unified_df()
                        matches = pd.DataFrame()
                        for col in ["Kundennummer", "Objekt-ID", "Objekt-ID_Global"]:
                            if col in self.unified_df.columns:
                                mask = self.unified_df[col].astype(str).str.contains(
                                    rf'\b{sid}\b', regex=True, na=False
                                )
                                if mask.any():
                                    matches = self.unified_df[mask]
                                    break
                        if not matches.empty:
                            res = matches.iloc[0]
                            if pd.notna(res.get("lat")) and pd.notna(res.get("lon")):
                                return {
                                    "answer": (
                                        f"📍 **Navigation zur Karte...**\n"
                                        f"Ich zeige Ihnen den Anschluss `{res.get('Kundennummer')}` auf der Karte."
                                    ),
                                    "hits": hits, "model_used": self.llm_model,
                                    "pending_action": {
                                        "type": "navigate_map",
                                        "args": {
                                            "customer_id": str(res.get("Kundennummer")),
                                            "lat": float(res["lat"]),
                                            "lon": float(res["lon"])
                                        }
                                    }
                                }
                        return {
                            "answer": "🗺️ **Ich öffne die Netz-Karte für Sie...**",
                            "hits": hits, "model_used": self.llm_model,
                            "pending_action": {"type": "navigate_map_general", "args": {}}
                        }

                answer = msg.get("content", "")
                return {"answer": answer, "hits": hits, "model_used": self.llm_model, "switched": False}

        except Exception:
            pass

        if hits:
            fallback = (
                "⏱️ **Zeitüberschreitung**: Relevantes aus der Datenbank:\n\n"
                + "\n".join([f"- {h['doc']}" for h in hits[:2]])
            )
            return {"answer": fallback, "hits": hits, "model_used": "Timeout-Fallback", "switched": False}

        return {"answer": "Keine Antwort gefunden.", "hits": [], "model_used": "Error", "switched": False}

    def chat_general(self, user_message: str, history: List[Dict]) -> Dict[str, Any]:
        return self.answer_question(user_message, history=history)