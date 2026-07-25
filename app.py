"""Dashboard Streamlit para TechLogistics."""
import json
import os

import plotly.express as px
import streamlit as st

from analysis import executive_metrics, run_pipeline, summarize_for_ai


st.set_page_config(page_title="TechLogistics DSS", page_icon="📊", layout="wide")
st.title("TechLogistics | Sistema de Soporte a la Decisión")
st.caption("EDA, transformación y visualización de rentabilidad, operación y fidelidad")


@st.cache_data
def get_data():
    return run_pipeline()


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

filtered = truth.copy()
if isinstance(dates, tuple) and len(dates) == 2:
    filtered = filtered[filtered["Fecha_Venta"].dt.date.between(dates[0], dates[1])]
if categories:
    filtered = filtered[filtered["Categoria"].isin(categories)]
if warehouses:
    filtered = filtered[filtered["Bodega_Origen"].isin(warehouses)]

m = executive_metrics(filtered)
cols = st.columns(6)
for col, label, value in zip(cols, ["Ingresos", "Margen", "Margen %", "Ventas fantasma", "NPS promedio", "Tickets"],
                             [f"${m['ingreso_total']:,.0f}", f"${m['margen_total']:,.0f}", f"{m['margen_pct']:.1f}%",
                              f"{m['ventas_fantasma']:,}", f"{m['nps_promedio']:.1f}", f"{m['tickets_pct']:.1f}%"]):
    col.metric(label, value)

tab_audit, tab_ops, tab_client, tab_ai = st.tabs(["Auditoría", "Operaciones", "Cliente", "Insights de IA"])

with tab_audit:
    st.subheader("Transparencia: antes vs. después")
    rows = []
    for name in audit["before"]:
        before, after = audit["before"][name], audit["after"][name]
        rows.append({"Dataset": name, "Filas antes": before["rows"], "Filas después": after["rows"],
                     "Nulos antes %": before["null_pct"], "Nulos después %": after["null_pct"],
                     "Duplicados eliminados": audit["excluded"][name].get("duplicates_removed", 0)})
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.metric("Health Score antes", f"{audit['before_health']:.1f}%")
    st.metric("Health Score después", f"{audit['after_health']:.1f}%")
    st.write("**Decisiones documentadas**")
    for key, reason in audit["reasons"].items():
        st.write(f"- **{key}:** {reason}")
    st.download_button("Descargar auditoría JSON", json.dumps(audit, ensure_ascii=False, indent=2),
                       "auditoria_limpieza.json", "application/json")
    with st.expander("Ver registros excluidos"):
        st.dataframe(data["excluded_transactions"], use_container_width=True)
        st.dataframe(data["excluded_inventory"], use_container_width=True)

with tab_ops:
    st.subheader("Rentabilidad y crisis logística")
    left, right = st.columns(2)
    sku_margin = filtered.groupby("SKU_ID", as_index=False).agg(Margen_USD=("Margen_USD", "sum"), Ingreso_USD=("Ingreso_USD", "sum"))
    with left:
        st.plotly_chart(px.bar(sku_margin.nsmallest(15, "Margen_USD"), x="Margen_USD", y="SKU_ID", orientation="h",
                               title="15 SKUs con menor margen"), use_container_width=True)
    with right:
        city = filtered.groupby("Ciudad_Destino", as_index=False).agg(Tiempo_Entrega=("Tiempo_Entrega_Real", "mean"), NPS=("NPS", "mean"))
        st.plotly_chart(px.scatter(city, x="Tiempo_Entrega", y="NPS", text="Ciudad_Destino", size_max=18,
                                   title="Entrega vs NPS por ciudad"), use_container_width=True)
    st.dataframe(filtered.groupby("Bodega_Origen", as_index=False).agg(
        Tiempo_Entrega=("Tiempo_Entrega_Real", "mean"), NPS=("NPS", "mean"), Tickets=("Ticket", "mean"),
        Dias_Revision=("Dias_Desde_Revision", "mean")).sort_values("NPS"), use_container_width=True)

with tab_client:
    st.subheader("Fidelidad, disponibilidad y soporte")
    category = filtered.groupby("Categoria", as_index=False).agg(Stock=("Stock_Actual", "mean"), NPS=("NPS", "mean"),
                                                                  Tickets=("Ticket", "mean"), Margen=("Margen_USD", "sum"))
    st.plotly_chart(px.scatter(category, x="Stock", y="NPS", size="Tickets", color="Categoria", hover_data=["Margen"],
                               title="Disponibilidad alta vs. sentimiento negativo"), use_container_width=True)
    st.dataframe(category.sort_values("NPS"), use_container_width=True)
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
                    model="llama3-8b-8192", messages=[{"role": "user", "content": prompt}], temperature=0.2)
                st.write(response.choices[0].message.content)
            except Exception as exc:
                st.error(f"Error en la integración Groq: {exc}")
    st.json(summarize_for_ai(filtered))
