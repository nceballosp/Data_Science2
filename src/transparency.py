"""Comparativo de calidad raw vs. procesado sin persistir un archivo de auditoría."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"


def _health(null_pct: float, duplicates: int, rows: int) -> float:
    duplicate_pct = duplicates / max(rows, 1) * 100
    return round(max(0, 100 - null_pct - duplicate_pct), 2)


def build_transparency() -> pd.DataFrame:
    sources = [
        ("Inventario", "inventario_central_v2.csv", "inventory_clean.csv", "inventory_excluded.csv"),
        ("Transacciones", "transacciones_logistica_v2.csv", "transactions_clean.csv", "transactions_excluded.csv"),
        ("Feedback", "feedback_clientes_v2.csv", "feedback_clean.csv", "feedback_excluded.csv"),
    ]
    rows = []
    for name, raw_name, clean_name, excluded_name in sources:
        raw = pd.read_csv(RAW / raw_name)
        clean = pd.read_csv(PROCESSED / clean_name)
        excluded = pd.read_csv(PROCESSED / excluded_name) if excluded_name else pd.DataFrame()
        excluded_rows = len(excluded) if excluded_name else len(raw) - len(clean)
        raw_duplicates = raw.duplicated(subset=["Feedback_ID"]).sum() if name == "Feedback" else raw.duplicated().sum()
        clean_duplicates = clean.duplicated().sum()
        rows.append({
            "Dataset": name,
            "Filas raw": len(raw),
            "Filas clean": len(clean),
            "Filas excluidas": excluded_rows,
            "Nulos raw (%)": round(raw.isna().mean().mean() * 100, 2),
            "Nulos clean (%)": round(clean.isna().mean().mean() * 100, 2),
            "Duplicados raw": int(raw_duplicates),
            "Health raw (%)": _health(raw.isna().mean().mean() * 100, raw_duplicates, len(raw)),
            "Health clean (%)": _health(clean.isna().mean().mean() * 100, clean_duplicates, len(clean)),
        })
    return pd.DataFrame(rows)
