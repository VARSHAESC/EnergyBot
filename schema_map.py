# -*- coding: utf-8 -*-
"""
schema_map.py
─────────────
Maps raw Excel column names (which vary between client file versions) to
canonical internal names used throughout the backend.

Old format: 67 columns (synthetic test data, Kundenname field)
New format: 84 columns (real client data, Kunden field, + 28 Strom columns)
"""
import pandas as pd

# Maps canonical_name -> list of possible raw column names (in priority order)
COLUMN_MAP = {
    # Identity
    "Kundenname":           ["Kundenname", "Kunden"],
    "Gemeinde":             ["Gemeinde"],
    "Postleitzahl":         ["Postleitzahl"],
    "Straße":               ["Straße", "Strasse", "Strae"],
    "Hausnummer":           ["Hausnummer"],
    "lat":                  ["Breitengrad (Latitude)"],
    "lon":                  ["Längengrad (Longitude)"],
    "Objekt_ID":            ["Objekt-ID (Nummer bspw.)"],

    # Water
    "Wasser Einbaudatum/ Fertigmeldung":    ["Wasser Einbaudatum/ Fertigmeldung"],
    "Wasser Werkstoff Anschlussleitung":    ["Wasser Werkstoff Anschlussleitung"],
    "Wasser (Letztes) Inspektionsdatum":    ["Wasser (Letztes) Inspektionsdatum"],
    "Wasser Keine Mängel":                  ["Wasser Keine Mängel"],
    "Wasser Dimension Anschlussleitung":    ["Wasser Dimension Anschlussleitung"],
    "Wasser Anschlusslänge Hausanschluss":  ["Wasser Anschlusslänge Hausanschluss"],

    # Gas
    "Gas Einbaudatum/ Fertigmeldung":       ["Gas Einbaudatum/ Fertigmeldung"],
    "Gas Werkstoff Anschlussleitung":       ["Gas Werkstoff Anschlussleitung"],
    "Gas (Letztes) Inspektionsdatum":       ["Gas (Letztes) Inspektionsdatum"],
    "Gas Keine Mängel":                     ["Gas Keine Mängel"],
    "Gas Druckstufe":                       ["Gas Druckstufe"],
    "Gas Dimension Anschlussleitung":       ["Gas Dimension Anschlussleitung"],
    "Gas Länge Anschlussleitung":           ["Gas Länge Anschlussleitung"],
}


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rename DataFrame columns from raw Excel names to canonical internal names.
    - Strips trailing/leading whitespace from ALL column names first.
    - Maps known variant names to their canonical equivalent.
    - Columns not in the map are left as-is (safe — no data is dropped).
    - Returns the normalised DataFrame.
    """
    # Step 1: strip whitespace (fixes Werkstoff trailing space and similar)
    df.columns = [c.strip() for c in df.columns]

    # Step 2: rename variants to canonical names
    rename_map = {}
    for canonical, variants in COLUMN_MAP.items():
        for variant in variants:
            if variant in df.columns and variant != canonical:
                rename_map[variant] = canonical

    if rename_map:
        df = df.rename(columns=rename_map)

    return df


def validate_required_columns(df: pd.DataFrame) -> list:
    """
    Returns a list of missing required columns.
    Call after normalise_columns(). Empty list = all good.
    """
    required = ["Straße", "Hausnummer", "lat", "lon", "Kundenname"]
    return [c for c in required if c not in df.columns]
