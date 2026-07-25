"""Dashboard Streamlit para TechLogistics."""
import json
import os

import pandas as pd
import plotly.express as px
import streamlit as st

from analysis import executive_metrics, load_processed, summarize_for_ai


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

tab_ops, tab_client, tab_ai = st.tabs(["Operaciones", "Cliente", "Insights de IA"])

with tab_ops:
    st.subheader("Rentabilidad, demanda y crisis logística")
    timeline = filtered.groupby(filtered["Fecha_Venta"].dt.to_period("M").astype(str), as_index=False).agg(
        Ingresos=("Ingreso_USD", "sum"), Margen=("Margen_USD", "sum"))
    st.plotly_chart(px.line(timeline, x="Fecha_Venta", y=["Ingresos", "Margen"], markers=True,
                            title="Evolución mensual de ingresos y margen"), use_container_width=True)
    left, right = st.columns(2)
    sku_margin = filtered.groupby("SKU_ID", as_index=False).agg(Margen_USD=("Margen_USD", "sum"), Ingreso_USD=("Ingreso_USD", "sum"))
    with left:
        st.plotly_chart(px.bar(sku_margin.nsmallest(15, "Margen_USD"), x="Margen_USD", y="SKU_ID", orientation="h",
                               title="15 SKUs con menor margen"), use_container_width=True)
    with right:
        city = filtered.groupby("Ciudad_Destino", as_index=False).agg(Tiempo_Entrega=("Tiempo_Entrega_Real", "mean"), NPS=("NPS", "mean"))
        st.plotly_chart(px.scatter(city, x="Tiempo_Entrega", y="NPS", text="Ciudad_Destino", size_max=18,
                                   title="Entrega vs NPS por ciudad"), use_container_width=True)
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

with tab_client:
    st.subheader("Fidelidad, disponibilidad y soporte")
    category = filtered.groupby("Categoria", as_index=False).agg(Stock=("Stock_Actual", "mean"), NPS=("NPS", "mean"),
                                                                  Tickets=("Ticket_Activo", "mean"), Margen=("Margen_USD", "sum"))
    st.plotly_chart(px.scatter(category, x="Stock", y="NPS", size="Tickets", color="Categoria", hover_data=["Margen"],
                               title="Disponibilidad alta vs. sentimiento negativo"), use_container_width=True)
    st.dataframe(category.sort_values("NPS"), use_container_width=True)
    ratings = filtered.groupby("Categoria", as_index=False).agg(Rating_Producto=("Rating_Producto", "mean"),
                                                                  Rating_Logistica=("Rating_Logistica", "mean"))
    st.plotly_chart(px.bar(ratings, x="Categoria", y=["Rating_Producto", "Rating_Logistica"], barmode="group",
                           title="Rating de producto vs. logística por categoría"), use_container_width=True)
    warehouse = filtered.groupby("Bodega_Origen", as_index=False).agg(Stock=("Stock_Actual", "mean"),
                                                                        NPS=("NPS", "mean"), Tickets=("Ticket_Activo", "mean"))
    st.plotly_chart(px.scatter(warehouse, x="Stock", y="Tickets", size="Stock", color="NPS",
                               hover_name="Bodega_Origen", title="Stock, tickets y NPS por bodega"), use_container_width=True)
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
