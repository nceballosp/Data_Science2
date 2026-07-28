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


def build_cleaning_decisions() -> pd.DataFrame:
    """Explica decisiones de limpieza usando evidencia de los datos raw."""
    inv = pd.read_csv(RAW / "inventario_central_v2.csv")
    tx = pd.read_csv(RAW / "transacciones_logistica_v2.csv")
    fb = pd.read_csv(RAW / "feedback_clientes_v2.csv")

    def numeric_reason(series: pd.Series) -> str:
        values = pd.to_numeric(series, errors="coerce").dropna()
        skew = values.skew()
        distribution = "asimetrica" if abs(skew) >= 0.5 else "aproximadamente simetrica"
        return (f"La mediana es adecuada: distribucion {distribution} (sesgo {skew:.2f}) "
                "y es menos sensible a valores extremos que la media.")

    inv_cost = pd.to_numeric(inv["Costo_Unitario_USD"], errors="coerce")
    q1, q3 = inv_cost.quantile([0.25, 0.75])
    iqr = q3 - q1
    cost_flags = ((inv_cost < q1 - 1.5 * iqr) | (inv_cost > q3 + 1.5 * iqr) | (inv_cost <= 0)).sum()
    tx_qty = pd.to_numeric(tx["Cantidad_Vendida"], errors="coerce")
    tx_dates = pd.to_datetime(tx["Fecha_Venta"], dayfirst=True, errors="coerce")
    future = (tx_dates > pd.Timestamp.now().normalize()).sum()
    invalid_qty = (tx_qty <= 0).sum()
    fb_dups = fb.duplicated(subset=["Feedback_ID"], keep="first").sum()

    return pd.DataFrame([
        {"Dataset / campo": "Inventario / costo unitario", "Decision": "Marcar como excluidos", "Registros": int(cost_flags), "Metodo": "IQR y costo <= 0", "Justificacion": "Son valores imposibles o atipicos; imputarlos ocultaria una alerta de calidad."},
        {"Dataset / campo": "Transacciones / cantidad y fecha", "Decision": "Eliminar", "Registros": int(invalid_qty + future), "Metodo": "Reglas de validez", "Justificacion": "Cantidad no positiva o venta futura no representa una transaccion real y distorsiona ingresos y margen."},
        {"Dataset / campo": "Feedback / Feedback_ID repetido", "Decision": "Eliminar duplicados", "Registros": int(fb_dups), "Metodo": "Conservar primera ocurrencia", "Justificacion": "Evita ponderar varias veces la misma respuesta y sesgar NPS, ratings y tickets."},
        {"Dataset / campo": "Inventario / stock y lead time", "Decision": "Imputar faltantes", "Registros": int(inv["Stock_Actual"].isna().sum() + inv["Lead_Time_Dias"].isna().sum()), "Metodo": "Mediana", "Justificacion": numeric_reason(inv["Stock_Actual"])},
        {"Dataset / campo": "Inventario / costo unitario", "Decision": "Imputar faltantes", "Registros": int(inv_cost.isna().sum()), "Metodo": "Mediana", "Justificacion": numeric_reason(inv_cost)},
        {"Dataset / campo": "Transacciones / costo de envio", "Decision": "Imputar faltantes", "Registros": int(tx["Costo_Envio"].isna().sum()), "Metodo": "Mediana", "Justificacion": numeric_reason(tx["Costo_Envio"])},
        {"Dataset / campo": "Feedback / ratings y edad", "Decision": "Imputar faltantes o fuera de rango", "Registros": int(fb["Rating_Producto"].isna().sum() + fb["Edad_Cliente"].isna().sum()), "Metodo": "Mediana", "Justificacion": "Es robusta ante asimetria y outliers; evita fabricar valores extremos con el promedio."},
        {"Dataset / campo": "Transacciones / estado de envio", "Decision": "Imputar faltantes", "Registros": int(tx["Estado_Envio"].isna().sum()), "Metodo": "Categoria Desconocido", "Justificacion": "No se usa moda: asignar el estado mas frecuente inventaria un estado operativo."},
    ])
