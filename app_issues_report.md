# EnergyBot App Issues Report
**Date: 2026-04-27**

This report summarizes technical issues and risks identified in the current EnergyBot codebase, specifically focused on the FastAPI backend, RAG engine, and utility modules.

## 1. High-Priority Issues

### A. Column Name Inconsistency
There is a significant discrepancy in how column names are referenced across different modules. This will cause `/update-asset` operations to fail with `KeyError` or "Not Found" messages.
- **Discrepancy:** `geo_utils.py` looks for `"Kunden"`, `rag_engine.py` looks for `"Kundennummer"`, and `schema_map.py` normalizes names to `"Kundenname"`.
- **Location:** 
  - `geo_utils.py`: `update_excel_record()` (line 738)
  - `rag_engine.py`: `apply_update()` (line 262)
- **Risk:** Data updates will likely crash or fail to find records even when they exist.

### B. Concurrency and File Locking
The application uses Excel as its primary database but lacks a mechanism to handle concurrent access.
- **Problem:** If multiple users update assets at the same time, or if the file is open in Microsoft Excel, the write operation will fail or corrupt the data.
- **Risk:** Runtime crashes and potential permanent loss of data integrity.

---

## 2. Medium-Priority Issues

### A. Data Type Safety
Values sent via the API are strings. When updating the Excel file, these strings are written directly into columns that may expect numbers or dates.
- **Problem:** Writing a string into a numeric column (e.g., `Länge`) will break future analytical calculations and chart rendering.
- **Risk:** Dashboard crashes or incorrect KPI calculations.

### B. Duplicate Update Logic
The system has two separate implementations for updating Excel records.
- **Location 1:** `geo_utils.py:update_excel_record` (contains fuzzy matching logic).
- **Location 2:** `rag_engine.py:apply_update` (uses simplified exact matching).
- **Risk:** Maintenance overhead and inconsistent behavior depending on which part of the code triggers an update.

---

## 3. Low-Priority / Architectural Issues

### A. Hardcoded Data Paths
Paths to `excel_data/` and `data/` are inconsistent across `geo_utils.py` and `rag_engine.py`.
- **Risk:** Moving the data folder might break secondary features (like manual lookups) while the main dashboard continues to work.

### B. Reactive Encoding Fixes
The `_fix_encoding` utility in `geo_utils.py` manually replaces corrupted characters (e.g., `Strae` -> `Straße`).
- **Risk:** This is a "cat-and-mouse" approach. If the source Excel file is generated with new artifacts, the UI and filtering logic will fail until the code is manually updated.

---

## Recommended Next Steps
1. **Unify Column Access:** Use the `normalise_columns` logic from `schema_map.py` consistently before any read or write operation.
2. **Add File Locking:** Implement a simple locking mechanism for the Excel file during write operations.
3. **Consolidate Code:** Use `geo_utils.py:update_excel_record` as the single source of truth for all data modifications.
4. **Cast Inputs:** Ensure API inputs are cast to the correct numeric types before being written to Excel.
