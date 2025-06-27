# Telegram Bot Pasajes (Python)

Esta app en Python consulta periódicamente precios de vuelos en Level (en EUR) y Aerolíneas Argentinas (en ARS), convierte precios a USD, guarda oportunidades en SQLite y notifica por Telegram cuando detecta precios bajos. El objetivo es encontrar oportunidades reales (precios bajos y disponibles), evitar duplicados, mejorar la eficiencia y robustez, y facilitar el análisis de costos adicionales. Incluye logging detallado para depuración y análisis estadístico automático.

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

- Edita los umbrales de precio en el código:
  - `STORING_PRICE_THRESHOLD` (ida y vuelta, guardar en DB): **1100 USD**
  - `PRICE_THRESHOLD` (ida y vuelta, notificar): **900 USD**
  - `ONE_WAY_PRICE_THRESHOLD` (solo ida, notificar): **400 USD**
- Modifica destinos y fechas en las variables `DESTINATIONS`, `START_DATE` y `END_DATE`.
  - Por defecto, el rango cubre de octubre 2025 a junio 2026, ideal para aprovechar la temporada alta de LEVEL y Aerolíneas.
- El tipo de cambio se configura en el diccionario `EXCHANGE_RATE`.

## Estructura del proyecto

- `app.py`: Lógica principal, scraping, consulta de APIs, deduplicación, logging y notificaciones.
- `db.py`: Funciones de base de datos SQLite.
- `telegram_utils.py`: Envío de mensajes por Telegram (con soporte para HTML y emojis).
- `get_aerolineas_token.py`: Obtención automática del token de Aerolíneas usando Selenium Wire.
- `stats.py`: Análisis estadístico y generación de PDF con gráficos (bar plot, scatter, boxplot, heatmap).
- `requirements.txt`: Dependencias del proyecto.

## Logging y robustez

- Logging detallado de cada request, status code y respuesta parcial.
- Warnings explícitos cuando la API no devuelve vuelos disponibles.
- Validación robusta de combinaciones y deduplicación de oportunidades.
- Validación de tickets reales en Aerolíneas antes de notificar (opcional).
- Guarda la respuesta original de la API para el primer vuelo notificado (útil para análisis de costos adicionales).

## Requisitos

- Python >= 3.10
- requests
- selenium-wire
- reportlab
- matplotlib
- seaborn
- numpy
- python-dotenv (opcional, para cargar variables de entorno)

## Análisis y visualización

- Al finalizar cada consulta, se puede generar un archivo PDF con:
  - Estadísticas básicas (promedio, mediana, mínimo, máximo, desvío estándar).
  - Detección de outliers y gaps de fechas.
  - Sugerencias de fechas alternativas.
  - Gráficos: bar plot, scatter plot, boxplot y heatmap de precios.
- Personaliza los análisis en `stats.py`.

## Recomendaciones de uso

- Aprovecha la ventana de octubre 2025 a junio 2026 para captar oportunidades en la temporada alta de LEVEL y Aerolíneas.
- Ajusta los thresholds según el contexto económico y tu perfil de oportunidad.
- Consulta manualmente en la web de las aerolíneas si tienes dudas sobre la disponibilidad real.
- Revisa los logs para depurar problemas de token, cambios en la API o falta de resultados.

---
