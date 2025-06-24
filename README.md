# Telegram Bot Pasajes (Python)

Esta app en Python consulta periódicamente APIs de vuelos (Level y Aerolíneas Argentinas), guarda los resultados en SQLite y notifica por Telegram si encuentra combinaciones de ida y vuelta por debajo de un umbral de precio. Además, genera un reporte PDF con análisis y visualizaciones estadísticas de los precios encontrados.

## Instalación

1. Instala todas las dependencias:
   ```sh
   pip install -r requirements.txt
   ```
2. Configura tus variables de entorno `TELEGRAM_TOKEN` y `TELEGRAM_CHAT_ID`.
   Puedes agregarlas en tu entorno o en un archivo `.env` (usando python-dotenv si lo deseas).
3. Ejecuta la app:
   ```sh
   python app.py
   ```

## Configuración

- Edita el umbral de precio en el código (`PRICE_THRESHOLD`).
- Puedes modificar destinos y fechas en las variables `DESTINATIONS`, `START_DATE` y `END_DATE`.

## Estructura
- `app.py`: Lógica principal de la aplicación.
- `db.py`: Funciones de base de datos SQLite.
- `telegram_utils.py`: Envío de mensajes por Telegram.
- `stats.py`: Análisis estadístico y generación de PDF con gráficos (bar plot, scatter, boxplot, heatmap).
- `flight_stats.pdf`: Reporte generado automáticamente con análisis y visualizaciones.

## Requisitos
- Python >= 3.10
- requests
- reportlab
- matplotlib
- seaborn
- numpy

---

### Visualización y análisis

Al finalizar cada consulta, se genera un archivo `flight_stats.pdf` con:
- Estadísticas básicas (promedio, mediana, mínimo, máximo, desvío estándar).
- Detección de outliers y gaps de fechas.
- Sugerencias de fechas alternativas.
- Gráficos: bar plot, scatter plot, boxplot y heatmap de precios.

Puedes personalizar los análisis y visualizaciones en `stats.py`.
