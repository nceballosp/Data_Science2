# TechLogistics DSS | Challenge 02

Solución del taller de EDA, transformación y visualización. El proyecto convierte tres fuentes contaminadas de inventario, logística y feedback en una fuente de verdad auditable y un dashboard para apoyar decisiones de margen, servicio y fidelidad.

## Ejecución

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python analysis.py
python generate_tex_figures.py
streamlit run app.py
```

`analysis.py` lee los CSV desde `data/raw` y materializa los clean de cada dataset, la fuente de verdad y los archivos de excluidos en `data/processed`. `app.py` lee exclusivamente esos artefactos; no limpia ni transforma datos en memoria al iniciar.

## Streamlit Community Cloud

Suba la carpeta `Data_Science2` como repositorio o como raíz de la aplicación y configure:

- **Main file path:** `app.py`
- **Python version:** 3.11 o superior
- **Secrets:** `GROQ_API_KEY = "su_llave"` (opcional; el dashboard funciona sin IA)

No se requiere una ruta absoluta ni acceso a archivos fuera del repositorio.

## Decisiones de calidad

- Se normalizan categorías, ciudades, bodegas, fechas y lead times.
- Los nulos numéricos se imputan con mediana porque costos, edades y stock contienen valores extremos; no se usa media para no distorsionar la distribución.
- Se excluyen cantidades no positivas y ventas con fecha futura del análisis operativo, conservándolas en `excluded_transactions`.
- Los costos no positivos o atípicos según IQR se imputan con mediana y quedan contabilizados en la auditoría.
- Los SKU sin correspondencia se conservan mediante `left join` y se marcan como `Venta_Fantasma`; su ingreso sigue siendo trazable, pero no se inventa costo de producto.
- El feedback se deduplica por `Feedback_ID`, se corrigen edades fuera de 18-100 y ratings de producto fuera de 1-5.

## Entregables

- `analysis.py`: pipeline modular y métricas derivadas.
- `app.py`: Streamlit con sidebar, tabs, filtros, auditoría, excluidos, descarga e integración Groq.
- `generate_tex_figures.py`: genera las mismas visualizaciones analíticas del dashboard para el informe LaTeX.
- `data/processed/feedback_excluded.csv`: feedback duplicado excluido por `Feedback_ID`.

## Groq

No se guarda la llave en el repositorio. Configure `GROQ_API_KEY` como variable de entorno o en `.streamlit/secrets.toml`. El módulo de IA envía solo el resumen estadístico del filtro actual y no los registros completos.
