"""Genera las figuras estáticas usadas por el informe LaTeX."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from Data_Science2.src.analysis import load_processed


ROOT = Path(__file__).resolve().parent
FIGURES = ROOT / "informe" / "tex_figures"


def _save(fig, name: str) -> None:
    fig.tight_layout()
    fig.savefig(FIGURES / name, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    FIGURES.mkdir(exist_ok=True)
    _, _, df = load_processed()
    df = df.copy()
    df["Ticket_Activo"] = df["Ticket_Soporte"].fillna(0).gt(0.5)
    df["Dias_Revision"] = (pd.Timestamp.now().normalize() - df["Ultima_Revision"]).dt.days

    # Punto 1: pérdidas generales y del canal Online.
    sku = df.groupby("SKU_ID", as_index=False)["Margen_USD"].sum()
    sku = sku[sku["Margen_USD"] < 0].nsmallest(10, "Margen_USD")
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(sku["SKU_ID"], sku["Margen_USD"], color="#d1495b")
    ax.set_title("SKUs con mayor margen negativo")
    ax.set_xlabel("Margen acumulado (USD)")
    ax.grid(axis="x", alpha=.25)
    _save(fig, "01_margen_negativo.png")

    # Punto 2: las combinaciones ciudad-bodega con peor NPS.
    zone = df.groupby(["Ciudad_Destino", "Bodega_Origen"], as_index=False).agg(
        Entrega=("Tiempo_Entrega_Real", "mean"), NPS=("NPS", "mean"), Ordenes=("Transaccion_ID", "count"))
    zone["Zona"] = zone["Ciudad_Destino"] + " / " + zone["Bodega_Origen"]
    zone = zone.nsmallest(12, "NPS")
    fig, ax = plt.subplots(figsize=(9, 5))
    sizes = zone["Ordenes"] * 0.8
    ax.scatter(zone["Entrega"], zone["NPS"], s=sizes, c=zone["NPS"], cmap="Reds_r", alpha=.85)
    for _, row in zone.iterrows():
        ax.annotate(row["Zona"], (row["Entrega"], row["NPS"]), fontsize=7, xytext=(4, 4), textcoords="offset points")
    ax.axhline(0, color="#b23a48", linestyle="--", linewidth=1)
    ax.set_title("Zonas críticas: tiempo de entrega y NPS")
    ax.set_xlabel("Entrega promedio (días)")
    ax.set_ylabel("NPS promedio")
    ax.grid(alpha=.2)
    _save(fig, "02_crisis_logistica.png")

    # Punto 3: composición del ingreso según existencia en catálogo.
    ghost = df.groupby("Venta_Fantasma")["Ingreso_USD"].sum()
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.pie([ghost.get(False, 0), ghost.get(True, 0)], labels=["SKU catalogado", "SKU sin catálogo"],
           autopct="%.1f%%", startangle=90, colors=["#2a9d8f", "#e76f51"])
    ax.set_title("Ingreso en riesgo por venta invisible")
    _save(fig, "03_venta_invisible.png")

    # Punto 4: stock alto contra NPS negativo por categoría.
    category = df.groupby("Categoria", as_index=False).agg(Stock=("Stock_Actual", "mean"), NPS=("NPS", "mean"))
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.scatter(category["Stock"], category["NPS"], s=category["Stock"] / 3, color="#2878b5")
    for _, row in category.iterrows():
        ax.annotate(row["Categoria"], (row["Stock"], row["NPS"]), fontsize=8, xytext=(4, 4), textcoords="offset points")
    ax.axhline(0, color="#b23a48", linestyle="--", linewidth=1)
    ax.axvline(category["Stock"].median(), color="gray", linestyle=":", linewidth=1)
    ax.set_title("Disponibilidad alta frente a sentimiento negativo")
    ax.set_xlabel("Stock promedio")
    ax.set_ylabel("NPS promedio")
    ax.grid(alpha=.2)
    _save(fig, "04_fidelidad.png")

    # Punto 5: antigüedad de revisión contra tickets por bodega.
    warehouse = df.groupby("Bodega_Origen", as_index=False).agg(
        Revision=("Dias_Revision", "mean"), Tickets=("Ticket_Activo", "mean"), NPS=("NPS", "mean"))
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.scatter(warehouse["Revision"], warehouse["Tickets"] * 100, s=120, c=warehouse["NPS"], cmap="RdYlGn", edgecolor="black")
    for _, row in warehouse.iterrows():
        ax.annotate(row["Bodega_Origen"], (row["Revision"], row["Tickets"] * 100), fontsize=8, xytext=(4, 4), textcoords="offset points")
    ax.set_title("Riesgo operativo: revisión atrasada y tickets")
    ax.set_xlabel("Días desde la última revisión")
    ax.set_ylabel("Tickets de soporte (%)")
    ax.grid(alpha=.2)
    _save(fig, "05_riesgo_operativo.png")
    print(f"Figuras generadas en {FIGURES}")


if __name__ == "__main__":
    main()
