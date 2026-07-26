"""Dashboard Streamlit para TechLogistics."""
import json
import os

import pandas as pd
import plotly.express as px
import streamlit as st

from Data_Science2.src.analysis import executive_metrics, load_processed, summarize_for_ai
from Data_Science2.src.transparency import build_transparency


st.set_page_config(page_title="TechLogistics DSS", page_icon="📊", layout="wide")
st.title("TechLogistics | Sistema de Soporte a la Decisión")
st.caption("EDA, transformación y visualización de rentabilidad, operación y fidelidad")


@st.cache_data
def get_data():
    return load_processed()


try:
    data, audit, truth = get_data()
except Exception as exc:
    st.error(f"No fue posible cargar los datos: {exc}")
    st.stop()

with st.sidebar:
    st.header("Filtros")
    min_date = truth["Fecha_Venta"].min().date()
    max_date = truth["Fecha_Venta"].max().date()
    dates = st.date_input("Periodo de venta", (min_date, max_date), min_value=min_date, max_value=max_date)
    categories = st.multiselect("Categoría", sorted(truth["Categoria"].dropna().unique()), default=None)
    warehouses = st.multiselect("Bodega", sorted(truth["Bodega_Origen"].dropna().unique()), default=None)
    if st.button("Refrescar análisis"):
        st.cache_data.clear()
        st.rerun()
    modelo_groq = st.selectbox(
    "Modelo",
    ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it"],
    index=0,
    )

filtered = truth.copy()
if isinstance(dates, tuple) and len(dates) == 2:
    filtered = filtered[filtered["Fecha_Venta"].dt.date.between(dates[0], dates[1])]
if categories:
    filtered = filtered[filtered["Categoria"].isin(categories)]
if warehouses:
    filtered = filtered[filtered["Bodega_Origen"].isin(warehouses)]
filtered = filtered.copy()
filtered["Ticket_Activo"] = filtered["Ticket_Soporte"].fillna(0).gt(0.5)
filtered["Dias_Revision"] = (pd.Timestamp.now().normalize() - filtered["Ultima_Revision"]).dt.days

m = executive_metrics(filtered)
cols = st.columns(6)
for col, label, value in zip(cols, ["Ingresos", "Margen", "Margen %", "Ventas fantasma", "NPS promedio", "Tickets"],
                             [f"${m['ingreso_total']:,.0f}", f"${m['margen_total']:,.0f}", f"{m['margen_pct']:.1f}%",
                              f"{m['ventas_fantasma']:,}", f"{m['nps_promedio']:.1f}", f"{m['tickets_pct']:.1f}%"]):
    col.metric(label, value)

tab_transparency, tab_ops, tab_client, tab_ai = st.tabs(["Transparencia", "Operaciones", "Cliente", "Insights de IA"])

with tab_transparency:
    st.subheader("Transparencia de transformación")
    st.caption("Comparativo calculado desde data/raw y data/processed; no se genera audit.json.")
    transparency = build_transparency()
    st.dataframe(transparency, use_container_width=True, hide_index=True)
    chart = transparency.melt(id_vars="Dataset", value_vars=["Health raw (%)", "Health clean (%)"],
                              var_name="Estado", value_name="Health Score")
    st.plotly_chart(px.bar(chart, x="Dataset", y="Health Score", color="Estado", barmode="group",
                           title="Health Score antes y después"), use_container_width=True)
    st.plotly_chart(px.bar(transparency, x="Dataset", y=["Nulos raw (%)", "Nulos clean (%)"], barmode="group",
                           title="Nulidad antes y después"), use_container_width=True)

with tab_ops:
    st.subheader("Rentabilidad, demanda y crisis logística")
    timeline = filtered.groupby(filtered["Fecha_Venta"].dt.to_period("M").astype(str), as_index=False).agg(
        Ingresos=("Ingreso_USD", "sum"), Margen=("Margen_USD", "sum"))
    st.plotly_chart(px.line(timeline, x="Fecha_Venta", y=["Ingresos", "Margen"], markers=True,
                            title="Evolución mensual de ingresos y margen"), use_container_width=True)
    left, right = st.columns(2)
    sku_margin = filtered.groupby("SKU_ID", as_index=False).agg(Margen_USD=("Margen_USD", "sum"), Ingreso_USD=("Ingreso_USD", "sum"))
    online_negative = filtered[filtered["Canal_Venta"].eq("Online")].groupby("SKU_ID", as_index=False).agg(
        Margen_USD=("Margen_USD", "sum"), Ingreso_USD=("Ingreso_USD", "sum"),
        Unidades=("Cantidad_Vendida", "sum")).query("Margen_USD < 0").sort_values("Margen_USD")
    with left:
        st.plotly_chart(px.bar(sku_margin[sku_margin["Margen_USD"] < 0].nsmallest(15, "Margen_USD"),
                               x="Margen_USD", y="SKU_ID", orientation="h", color="Margen_USD",
                               color_continuous_scale="Reds", title="Fuga de capital: SKUs con margen negativo"),
                         use_container_width=True)
    with right:
        st.plotly_chart(px.bar(online_negative.head(10), x="Margen_USD", y="SKU_ID", orientation="h",
                               hover_data=["Ingreso_USD", "Unidades"], color="Margen_USD",
                               color_continuous_scale="Reds", title="Canal Online: SKU con pérdida"),
                         use_container_width=True)
    city = filtered.groupby("Ciudad_Destino", as_index=False).agg(Tiempo_Entrega=("Tiempo_Entrega_Real", "mean"), NPS=("NPS", "mean"))
    city_fig = px.scatter(city, x="Tiempo_Entrega", y="NPS", text="Ciudad_Destino", size_max=18,
                          title="Crisis logística: entrega vs. NPS por ciudad")
    city_fig.add_hline(y=0, line_dash="dash", line_color="red")
    st.plotly_chart(city_fig, use_container_width=True)
    combo = filtered.groupby(["Ciudad_Destino", "Bodega_Origen"], as_index=False).agg(
        Entrega=("Tiempo_Entrega_Real", "mean"), NPS=("NPS", "mean"), Tickets=("Ticket_Activo", "mean"),
        Ordenes=("Transaccion_ID", "count"))
    combo["Zona"] = combo["Ciudad_Destino"] + " / " + combo["Bodega_Origen"]
    st.plotly_chart(px.scatter(combo.sort_values("NPS").head(15), x="Entrega", y="NPS", size="Ordenes",
                               color="Tickets", hover_name="Zona", color_continuous_scale="Reds",
                               title="Zonas críticas: ciudad y bodega"), use_container_width=True)
    ghost = filtered.groupby("Venta_Fantasma", as_index=False).agg(Ingreso=("Ingreso_USD", "sum"),
                                                                    Ordenes=("Transaccion_ID", "count"))
    ghost["Tipo"] = ghost["Venta_Fantasma"].map({True: "SKU sin catálogo", False: "SKU catalogado"})
    st.plotly_chart(px.pie(ghost, names="Tipo", values="Ingreso", hole=0.45,
                           title="Venta invisible: ingreso con y sin catálogo"), use_container_width=True)
    channel = filtered.groupby("Canal_Venta", as_index=False).agg(Ingresos=("Ingreso_USD", "sum"), Margen=("Margen_USD", "sum"))
    status = filtered.groupby("Estado_Envio", as_index=False).agg(Ventas=("Transaccion_ID", "count"),
                                                                    Entrega=("Tiempo_Entrega_Real", "mean"))
    left, right = st.columns(2)
    with left:
        st.plotly_chart(px.bar(channel, x="Canal_Venta", y=["Ingresos", "Margen"], barmode="group",
                               title="Ingresos y margen por canal"), use_container_width=True)
    with right:
        st.plotly_chart(px.bar(status, x="Estado_Envio", y="Ventas", color="Entrega",
                               title="Volumen por estado de envío"), use_container_width=True)
    st.dataframe(filtered.groupby("Bodega_Origen", as_index=False).agg(
        Tiempo_Entrega=("Tiempo_Entrega_Real", "mean"), NPS=("NPS", "mean"), Tickets=("Ticket_Activo", "mean"),
        Dias_Revision=("Dias_Revision", "mean")).sort_values("NPS"), use_container_width=True)
    with st.expander("Ver registros excluidos"):
        st.dataframe(data["excluded_transactions"], use_container_width=True)
        st.dataframe(data["excluded_inventory"], use_container_width=True)
        st.dataframe(data["excluded_feedback"], use_container_width=True)

with tab_client:
    st.subheader("Fidelidad, disponibilidad y soporte")
    category = filtered.groupby("Categoria", as_index=False).agg(Stock=("Stock_Actual", "mean"), NPS=("NPS", "mean"),
                                                                  Tickets=("Ticket_Activo", "mean"), Margen=("Margen_USD", "sum"))
    category_fig = px.scatter(category, x="Stock", y="NPS", size="Tickets", color="Categoria", hover_data=["Margen"],
                              title="Diagnóstico de fidelidad: stock alto vs. NPS negativo")
    category_fig.add_hline(y=0, line_dash="dash", line_color="red")
    category_fig.add_vline(x=category["Stock"].median(), line_dash="dot", line_color="gray")
    st.plotly_chart(category_fig, use_container_width=True)
    st.dataframe(category.sort_values("NPS"), use_container_width=True)
    ratings = filtered.groupby("Categoria", as_index=False).agg(Rating_Producto=("Rating_Producto", "mean"),
                                                                  Rating_Logistica=("Rating_Logistica", "mean"))
    st.plotly_chart(px.bar(ratings, x="Categoria", y=["Rating_Producto", "Rating_Logistica"], barmode="group",
                           title="Rating de producto vs. logística por categoría"), use_container_width=True)
    warehouse = filtered.groupby("Bodega_Origen", as_index=False).agg(Stock=("Stock_Actual", "mean"),
                                                                        NPS=("NPS", "mean"), Tickets=("Ticket_Activo", "mean"),
                                                                        Revision=("Dias_Revision", "mean"))
    risk_fig = px.scatter(warehouse, x="Revision", y="Tickets", size="Stock", color="NPS",
                          hover_name="Bodega_Origen", color_continuous_scale="RdYlGn",
                          title="Riesgo operativo: antigüedad de revisión vs. tickets")
    risk_fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(risk_fig, use_container_width=True)
    st.info("La paradoja de stock alto y NPS negativo debe contrastarse con rating de producto, tickets y margen: disponibilidad no equivale a calidad ni a valor percibido.")

with tab_ai:
    st.subheader("Recomendaciones estratégicas")
    st.caption("El modelo recibe únicamente el resumen estadístico del filtro actual.")
    if st.button("Generar análisis con Llama-3"):
        try:
            key = st.secrets.get("GROQ_API_KEY")
        except Exception:
            key = None
        key = key or os.getenv("GROQ_API_KEY")
        if not key:
            st.warning("Configura GROQ_API_KEY en .streamlit/secrets.toml o como variable de entorno.")
        else:
            try:
                from groq import Groq
                summary = summarize_for_ai(filtered)
                prompt = ("Actúa como consultor senior de TechLogistics. Con este resumen JSON, redacta exactamente "
                          "tres párrafos de recomendaciones accionables, priorizadas y dirigidas a la junta. "
                          "No inventes datos:\n" + json.dumps(summary, ensure_ascii=False))
                response = Groq(api_key=key).chat.completions.create(
                    model=modelo_groq, messages=[{"role": "user", "content": prompt}], temperature=0.2)
                st.write(response.choices[0].message.content)
            except Exception as exc:
                st.error(f"Error en la integración Groq: {exc}")
    st.json(summarize_for_ai(filtered))
