"""Pipeline reproducible de EDA, calidad, integración y feature engineering."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "raw"
TODAY = pd.Timestamp.now().normalize()


def _read_csv(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de datos: {path}")
    return pd.read_csv(path)


def _quality(df: pd.DataFrame, name: str, duplicate_rows: int = 0) -> dict[str, Any]:
    return {
        "dataset": name,
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "null_pct": float(df.isna().mean().mean() * 100),
        "null_by_column": (df.isna().mean() * 100).round(2).to_dict(),
        "duplicates": int(duplicate_rows),
    }


def _iqr_mask(series: pd.Series) -> pd.Series:
    q1, q3 = series.quantile([0.25, 0.75])
    iqr = q3 - q1
    return (series < q1 - 1.5 * iqr) | (series > q3 + 1.5 * iqr)


def _normalise_category(value: Any) -> str:
    value = str(value).strip().lower()
    mapping = {
        "smart-phone": "Smartphones", "smartphone": "Smartphones",
        "laptop": "Laptops", "laptops": "Laptops",
        "monitor": "Monitores", "monitores": "Monitores",
        "tablet": "Tablets", "tablets": "Tablets",
        "accesorios": "Accesorios", "???": "Sin categoría",
    }
    return mapping.get(value, value.title())


def _normalise_city(value: Any) -> str:
    value = str(value).strip().lower()
    mapping = {
        "bog": "Bogotá", "bogotá": "Bogotá", "med": "Medellín",
        "medellín": "Medellín", "cali": "Cali",
        "bucaramanga": "Bucaramanga", "barranquilla": "Barranquilla",
    }
    return mapping.get(value, value.title())


def _normalise_lead(value: Any) -> float:
    text = str(value).lower().replace("días", "").strip()
    if text == "inmediato":
        return 0.0
    if "-" in text:
        a, b = text.split("-", 1)
        return (float(a) + float(b)) / 2
    try:
        return float(text)
    except ValueError:
        return np.nan


def load_and_clean() -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """Carga los tres CSV y devuelve datos limpios, excluidos y auditoría."""
    raw_inv = _read_csv("inventario_central_v2.csv")
    raw_tx = _read_csv("transacciones_logistica_v2.csv")
    raw_fb = _read_csv("feedback_clientes_v2.csv")
    audit: dict[str, Any] = {"before": {}, "after": {}, "excluded": {}}

    inv = raw_inv.copy()
    audit["before"]["Inventario"] = _quality(inv, "Inventario")
    inv["Categoria"] = inv["Categoria"].map(_normalise_category)
    inv["Bodega_Origen"] = inv["Bodega_Origen"].astype(str).str.strip().str.upper()
    inv["Stock_Actual"] = pd.to_numeric(inv["Stock_Actual"], errors="coerce")
    inv["Costo_Unitario_USD"] = pd.to_numeric(inv["Costo_Unitario_USD"], errors="coerce")
    inv["Lead_Time_Dias"] = inv["Lead_Time_Dias"].map(_normalise_lead)
    inv["Ultima_Revision"] = pd.to_datetime(inv["Ultima_Revision"], errors="coerce")
    inv_cost_outlier = _iqr_mask(inv["Costo_Unitario_USD"])
    inv_excluded = inv[inv_cost_outlier | (inv["Costo_Unitario_USD"] <= 0)].copy()
    inv["Stock_Actual"] = inv["Stock_Actual"].fillna(inv["Stock_Actual"].median()).clip(lower=0)
    inv["Lead_Time_Dias"] = inv["Lead_Time_Dias"].fillna(inv["Lead_Time_Dias"].median())
    inv["Costo_Unitario_USD"] = inv["Costo_Unitario_USD"].where(~inv_cost_outlier)
    inv["Costo_Unitario_USD"] = inv["Costo_Unitario_USD"].fillna(inv["Costo_Unitario_USD"].median())
    audit["excluded"]["Inventario"] = {"outliers_costos": int(len(inv_excluded))}

    tx = raw_tx.copy()
    audit["before"]["Transacciones"] = _quality(tx, "Transacciones")
    tx["Fecha_Venta"] = pd.to_datetime(tx["Fecha_Venta"], dayfirst=True, errors="coerce")
    future = tx["Fecha_Venta"] > TODAY
    invalid_qty = tx["Cantidad_Vendida"] <= 0
    outlier_delivery = _iqr_mask(tx["Tiempo_Entrega_Real"])
    tx_excluded = tx[future | invalid_qty].copy()
    tx = tx.loc[~(future | invalid_qty)].copy()
    tx["Costo_Envio"] = tx["Costo_Envio"].fillna(tx["Costo_Envio"].median())
    tx["Estado_Envio"] = tx["Estado_Envio"].fillna("Desconocido").astype(str).str.strip().str.title()
    tx["Ciudad_Destino"] = tx["Ciudad_Destino"].map(_normalise_city)
    audit["excluded"]["Transacciones"] = {
        "fechas_futuras": int(future.sum()), "cantidades_no_positivas": int(invalid_qty.sum()),
        "outliers_entrega": int(outlier_delivery.sum()), "rows_removed": int(len(tx_excluded)),
    }

    fb = raw_fb.copy()
    audit["before"]["Feedback"] = _quality(fb, "Feedback")
    fb_dups = fb.duplicated(subset=["Feedback_ID"], keep="first")
    fb = fb.loc[~fb_dups].copy()
    fb["Rating_Producto"] = pd.to_numeric(fb["Rating_Producto"], errors="coerce").where(lambda x: x.between(1, 5))
    fb["Rating_Producto"] = fb["Rating_Producto"].fillna(fb["Rating_Producto"].median())
    fb["Edad_Cliente"] = pd.to_numeric(fb["Edad_Cliente"], errors="coerce").where(lambda x: x.between(18, 100))
    fb["Edad_Cliente"] = fb["Edad_Cliente"].fillna(fb["Edad_Cliente"].median())
    fb["Ticket_Soporte"] = fb["Ticket_Soporte_Abierto"].astype(str).str.lower().isin(["sí", "si", "1", "yes"])
    fb["Satisfaccion_NPS"] = pd.to_numeric(fb["Satisfaccion_NPS"], errors="coerce").clip(-100, 100)
    fb["Satisfaccion_NPS"] = fb["Satisfaccion_NPS"].fillna(fb["Satisfaccion_NPS"].median())
    audit["excluded"]["Feedback"] = {"duplicates_removed": int(fb_dups.sum()), "rows_removed": int(fb_dups.sum())}

    for key, frame in [("Inventario", inv), ("Transacciones", tx), ("Feedback", fb)]:
        audit["after"][key] = _quality(frame, key)
    audit["before_health"] = health_score(audit["before"])
    audit["after_health"] = health_score(audit["after"])
    audit["reasons"] = {
        "Inventario": "Se imputaron nulos con mediana y se recortó stock negativo a cero; costos IQR se imputaron con mediana.",
        "Transacciones": "Se excluyeron cantidades no positivas y fechas futuras; costos de envío faltantes se imputaron con mediana.",
        "Feedback": "Se conservaron ratings válidos, se imputaron ratings/edades inválidos con mediana y se deduplicó por Feedback_ID.",
    }
    return {"inventory": inv, "transactions": tx, "feedback": fb, "excluded_transactions": tx_excluded, "excluded_inventory": inv_excluded}, audit


def health_score(audit_section: dict[str, dict[str, Any]]) -> float:
    if not audit_section:
        return 0.0
    null_penalty = np.mean([min(x["null_pct"], 100) for x in audit_section.values()])
    dup_penalty = np.mean([min(x["duplicates"] / max(x["rows"], 1) * 100, 100) for x in audit_section.values()])
    return round(max(0.0, 100 - null_penalty - dup_penalty), 2)


def build_truth(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    tx = data["transactions"].copy()
    inv = data["inventory"].copy()
    fb = data["feedback"].groupby("Transaccion_ID", as_index=False).agg(
        NPS=("Satisfaccion_NPS", "mean"), Rating_Producto=("Rating_Producto", "mean"),
        Rating_Logistica=("Rating_Logistica", "mean"), Ticket_Soporte=("Ticket_Soporte", "mean"),
    )
    truth = tx.merge(inv, on="SKU_ID", how="left", indicator="_catalog_match")
    truth = truth.merge(fb, on="Transaccion_ID", how="left")
    truth["Venta_Fantasma"] = truth["_catalog_match"].eq("left_only")
    truth["Ingreso_USD"] = truth["Cantidad_Vendida"] * truth["Precio_Venta_Final"]
    truth["Costo_Producto_USD"] = truth["Cantidad_Vendida"] * truth["Costo_Unitario_USD"]
    truth["Margen_USD"] = truth["Ingreso_USD"] - truth["Costo_Producto_USD"] - truth["Costo_Envio"]
    truth["Margen_Pct"] = np.where(truth["Ingreso_USD"].ne(0), truth["Margen_USD"] / truth["Ingreso_USD"] * 100, np.nan)
    truth["Brecha_Entrega_Dias"] = truth["Tiempo_Entrega_Real"] - truth["Lead_Time_Dias"]
    truth["Dias_Desde_Revision"] = (TODAY - truth["Ultima_Revision"]).dt.days
    truth["Stock_Alto"] = truth["Stock_Actual"] > truth["Stock_Actual"].median()
    truth["NPS_Bajo"] = truth["NPS"] < 0
    truth["Ticket"] = truth["Ticket_Soporte"].fillna(0).gt(0.5)
    return truth


def run_pipeline() -> tuple[dict[str, pd.DataFrame], dict[str, Any], pd.DataFrame]:
    data, audit = load_and_clean()
    return data, audit, build_truth(data)


def executive_metrics(truth: pd.DataFrame) -> dict[str, float]:
    return {
        "ingreso_total": float(truth["Ingreso_USD"].sum()),
        "margen_total": float(truth["Margen_USD"].sum()),
        "margen_pct": float(truth["Margen_USD"].sum() / truth["Ingreso_USD"].sum() * 100),
        "ventas_fantasma": int(truth["Venta_Fantasma"].sum()),
        "ingreso_fantasma": float(truth.loc[truth["Venta_Fantasma"], "Ingreso_USD"].sum()),
        "nps_promedio": float(truth["NPS"].mean()),
        "tickets_pct": float(truth["Ticket"].mean() * 100),
    }


def summarize_for_ai(truth: pd.DataFrame) -> dict[str, Any]:
    m = executive_metrics(truth)
    return {**m, "top_margenes_negativos": truth.groupby("SKU_ID")["Margen_USD"].sum().nsmallest(5).round(2).to_dict(),
            "ciudades_nps": truth.groupby("Ciudad_Destino")["NPS"].mean().round(2).to_dict(),
            "bodegas_tickets": truth.groupby("Bodega_Origen")["Ticket"].mean().mul(100).round(2).to_dict()}
