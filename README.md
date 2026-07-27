# TechLogistics DSS - Challenge 02

Solucion del taller de EDA, transformacion y visualizacion para TechLogistics. El proyecto integra tres fuentes con problemas de calidad: inventario, transacciones logisticas y feedback de clientes. El resultado es un pipeline reproducible, una fuente de verdad procesada, un dashboard interactivo en Streamlit y un informe ejecutivo en LaTeX.

**Curso:** Fundamentos en Ciencia de Datos — Maestría en Ciencia de Datos y Analítica, EAFIT  
**Fecha límite de entrega:** sábado 01 de agosto de 2026  
**Fecha de entrega real:** [27/07/2026]  

**Integrantes del equipo:**

| Nombre Completo                  | Cédula         |
| -------------------------------- | -------------- |
| Eduardo Andres Piñeros Manjarres | 1067841294     |
| Juan Jose Vasquez Gomez          | 1017924089     |
| Natalia Ceballos Posada          | 1034987681     |

---

## 1. Problema de negocio

El analisis busca identificar riesgos que afectan rentabilidad, servicio y fidelizacion:

1. Detectar SKUs y canales con margen negativo.
2. Localizar ciudades y bodegas con cuellos de botella logisticos y NPS bajo.
3. Cuantificar las ventas de SKUs ausentes del maestro de inventario.
4. Encontrar categorias con stock alto pero sentimiento negativo.
5. Relacionar la antiguedad de la revision de inventario con la tasa de tickets de soporte.

La fuente de verdad es `data/processed/truth_dataset.csv`. Las ventas con SKU no encontrado no se eliminan: se conservan y se marcan como `Venta_Fantasma` para medir el ingreso expuesto.

## 2. Aplicacion en la nube

[Abrir TechLogistics DSS en Streamlit Community Cloud](https://datascience2-aw35j6n2pppnemtlcs5e9y.streamlit.app)

Configuracion recomendada en Streamlit Community Cloud:

- **Repository:** repositorio que contiene la carpeta `Data_Science2`.
- **Main file path:** `Data_Science2/src/app.py` si se publica desde la raiz del repositorio, o `src/app.py` si `Data_Science2` es la raiz configurada.
- **Python:** 3.11 o superior.
- **Secrets opcional:** `GROQ_API_KEY = "su_llave"`.

La aplicacion no depende de rutas absolutas ni de archivos fuera del repositorio. Al desplegar, los archivos de `data/processed` deben estar versionados o debe ejecutarse `python src/analysis.py` antes de iniciar Streamlit.

## 3. Instalacion local

Desde la carpeta `Data_Science2`:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r src/requirements.txt
```

En Linux o macOS:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r src/requirements.txt
```

## 4. Ejecucion

Primero regenere los artefactos procesados desde los datos crudos:

```bash
python src/analysis.py
```

Despues inicie el dashboard:

```bash
streamlit run src/app.py
```

Para compilar el informe localmente usando las imagenes exportadas desde la app:

```bash
cd informe
pdflatex Informe_Hallazgos_TechLogistics.tex
pdflatex Informe_Hallazgos_TechLogistics.tex
```

La compilacion requiere una distribucion LaTeX con `pdflatex`, por ejemplo MiKTeX o TeX Live.

## 5. Flujo de datos

```text
data/raw/*.csv
        |
        v
src/analysis.py
        |
        +--> data/processed/*_clean.csv
        +--> data/processed/*_excluded.csv
        +--> data/processed/truth_dataset.csv
                         |
                         +--> src/app.py
                         +--> informe/tex_figures/*.png --> informe/Informe_Hallazgos_TechLogistics.tex
```

`src/analysis.py` es el unico modulo que limpia y transforma los datos. `src/app.py` carga exclusivamente los archivos materializados en `data/processed`; no realiza limpieza ni mantiene una fuente de verdad temporal en memoria.

Archivos de entrada esperados en `data/raw`:

- `inventario_central_v2.csv`
- `transacciones_logistica_v2.csv`
- `feedback_clientes_v2.csv`

Archivos generados en `data/processed`:

- `inventory_clean.csv`, `transactions_clean.csv` y `feedback_clean.csv`.
- `inventory_excluded.csv`, `transactions_excluded.csv` y `feedback_excluded.csv`.
- `truth_dataset.csv`.

## 6. Calidad y transformacion

- Se normalizan categorias, ciudades, bodegas, fechas, estados, canales y tiempos de entrega.
- Se excluyen cantidades no positivas y ventas con fecha futura del analisis operativo.
- Los costos no positivos o atipicos se imputan con la mediana y se conservan en `inventory_excluded.csv` para trazabilidad.
- Se deduplica el feedback por `Feedback_ID`; los registros descartados quedan en `feedback_excluded.csv`.
- Se corrigen edades fuera del rango esperado y ratings de producto fuera de 1 a 5.
- Se usa `left join` entre transacciones e inventario para no perder ventas sin SKU maestro.
- No se genera ni se requiere `audit.json`. La pestaña Transparencia compara directamente los datos crudos, limpios y excluidos.

## 7. Metricas derivadas

El dataset de verdad agrega cinco metricas de negocio:

- `Venta_Fantasma`: indica que el SKU de la transaccion no existe en el maestro de inventario.
- `Ingreso_USD`: ingreso de la transaccion, calculado como precio por cantidad.
- `Margen_USD`: ingreso menos costo estimado del producto.
- `Margen_Pct`: margen relativo sobre el ingreso.
- `Brecha_Entrega_Dias`: diferencia entre tiempo real y tiempo comprometido de entrega.

La aplicacion calcula adicionalmente indicadores agregados para las tarjetas y graficas, como ingresos, margen total, margen porcentual, NPS promedio, ventas fantasma y tasa de tickets.

## Dashboard Streamlit

La app incluye filtros por periodo, categoria y bodega, y cuatro modulos:

- **Transparencia:** comparacion de filas, nulos y health score entre raw y procesado, sin persistir un archivo de auditoria.
- **Operaciones:** evolucion mensual de ingresos y margen, SKUs con margen negativo, perdida en Online, entrega versus NPS, zonas criticas, venta invisible, canales y estados de envio.
- **Cliente:** stock versus NPS por categoria, ratings de producto y logistica, y antiguedad de revision versus tickets por bodega.
- **Insights de IA:** resumen estadistico y recomendaciones con Groq cuando se configura `GROQ_API_KEY`. No se envian registros completos al modelo.

## 8. Informe ejecutivo

El informe [Informe_Hallazgos_TechLogistics.tex](informe/Informe_Hallazgos_TechLogistics.tex) responde los cinco puntos del reto con tablas, conclusiones y visualizaciones alineadas con el dashboard. El PDF compilado se encuentra en [informe/Informe_Hallazgos_TechLogistics.pdf](informe/Informe_Hallazgos_TechLogistics.pdf).

Las seis imagenes utilizadas por el informe se exportan desde las visualizaciones del dashboard y se almacenan en `informe/tex_figures`:

1. Margen negativo y fuga de capital.
2. Crisis logistica y relacion entre entrega y NPS.
3. Venta invisible e ingreso en riesgo.
4. Stock alto y fidelidad negativa.
5. Riesgo operativo por antiguedad de revision y tickets.
6. Matriz de correlacion logistica y de satisfaccion.

## 9. Estructura principal

```text
Data_Science2/
|-- src/
|   |-- analysis.py
|   |-- app.py
|   |-- transparency.py
|   `-- requirements.txt
|-- data/
|   |-- raw/
|   `-- processed/
|-- informe/
|   |-- Informe_Hallazgos_TechLogistics.tex
|   |-- Informe_Hallazgos_TechLogistics.pdf
|   `-- tex_figures/
|-- .gitignore
`-- README.md
```

La carpeta `venv/` es local y `.miktex/` esta excluida por `.gitignore`; ninguna de las dos debe versionarse.

## 10. Configuracion de IA

Groq es opcional. Para habilitar el modulo de recomendaciones, configure la llave como variable de entorno:

```powershell
$env:GROQ_API_KEY = "su_llave"
```

En Streamlit Community Cloud, agregue la misma variable desde **Settings > Secrets**. La llave no debe escribirse en el codigo ni subirse al repositorio.
