"""Genera el PDF de hallazgos con evidencia visual reproducible."""
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from analysis import executive_metrics, run_pipeline


OUT = Path(__file__).resolve().parent / "Informe_Hallazgos_TechLogistics.pdf"


def _title_page(pdf, metrics, audit):
    fig = plt.figure(figsize=(11.69, 8.27))
    fig.text(0.08, 0.78, "TechLogistics S.A.S.", fontsize=28, weight="bold")
    fig.text(0.08, 0.69, "Informe ejecutivo de EDA, transformación y visualización", fontsize=18)
    text = (f"Ingresos trazables: ${metrics['ingreso_total']:,.0f}\n"
            f"Margen neto estimado: ${metrics['margen_total']:,.0f} ({metrics['margen_pct']:.1f}%)\n"
            f"Ventas fantasma: {metrics['ventas_fantasma']:,} | Ingreso en riesgo: ${metrics['ingreso_fantasma']:,.0f}\n"
            f"Health Score: {audit['before_health']:.1f}% antes -> {audit['after_health']:.1f}% después")
    fig.text(0.08, 0.48, text, fontsize=16, linespacing=1.8)
    fig.text(0.08, 0.15, "Alcance: datos de inventario, logística y feedback de clientes.\nLas ventas huérfanas se conservan y se etiquetan; no se atribuye costo de producto inexistente.", fontsize=11)
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def _plot(pdf, title, x, y, xlabel, ylabel, kind="bar"):
    fig, ax = plt.subplots(figsize=(11.69, 8.27))
    if kind == "scatter":
        ax.scatter(x, y, alpha=0.65, color="#0b7285")
    else:
        ax.bar(x, y, color="#e76f51")
        ax.tick_params(axis="x", rotation=35)
    ax.set_title(title, fontsize=17, weight="bold")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


def main():
    data, audit, truth = run_pipeline()
    metrics = executive_metrics(truth)
    with PdfPages(OUT) as pdf:
        _title_page(pdf, metrics, audit)
        sku = truth.groupby("SKU_ID", as_index=False)["Margen_USD"].sum().nsmallest(15, "Margen_USD")
        _plot(pdf, "Evidencia 1 | Fuga de capital: SKUs con margen negativo", sku["SKU_ID"], sku["Margen_USD"], "SKU", "Margen USD")
        city = truth.groupby("Ciudad_Destino", as_index=False).agg(Entrega=("Tiempo_Entrega_Real", "mean"), NPS=("NPS", "mean"))
        _plot(pdf, "Evidencia 2 | Crisis logística: entrega vs NPS", city["Entrega"], city["NPS"], "Días promedio de entrega", "NPS promedio", "scatter")
        cat = truth.groupby("Categoria", as_index=False).agg(Stock=("Stock_Actual", "mean"), NPS=("NPS", "mean"))
        _plot(pdf, "Evidencia 3 | Paradoja de disponibilidad y fidelidad", cat["Stock"], cat["NPS"], "Stock promedio", "NPS promedio", "scatter")
        wh = truth.groupby("Bodega_Origen", as_index=False).agg(Antiguedad=("Dias_Desde_Revision", "mean"), Tickets=("Ticket", "mean"))
        _plot(pdf, "Evidencia 4 | Operación a ciegas y tickets", wh["Bodega_Origen"], wh["Tickets"].mul(100), "Bodega", "Tickets (%)")
        fig = plt.figure(figsize=(11.69, 8.27))
        fig.text(0.08, 0.88, "Plan de acción priorizado", fontsize=22, weight="bold")
        actions = [
            "1. Alta: congelar temporalmente SKUs con margen negativo y conciliar el catálogo de ventas fantasma antes de renegociar precios.",
            "2. Media: cambiar o auditar el operador en las ciudades con mayor entrega y menor NPS; usar la brecha contra lead time como SLA.",
            "3. Baja: calendarizar conteos físicos por bodega y activar alertas de stock alto con NPS negativo y tickets crecientes.",
        ]
        fig.text(0.08, 0.70, "\n\n".join(actions), fontsize=15, linespacing=1.8, wrap=True)
        fig.text(0.08, 0.15, "Interpretación: el deterioro de margen combina fallas de precio/costo y baja trazabilidad. La decisión debe separar volumen rentable de ventas sin control de inventario.", fontsize=11, wrap=True)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
    print(f"Informe generado en {OUT}")


if __name__ == "__main__":
    main()
