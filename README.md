# Telegram Bot Pasajes (Python)

Este proyecto es un bot en Python para monitorear precios de vuelos internacionales, guardar oportunidades en una base de datos SQLite y notificar automáticamente por Telegram cuando detecta precios bajos y reales. El sistema es modular, soporta múltiples proveedores (Level, Aerolíneas Argentinas, Skyscanner, Amadeus) y permite configurar regiones, destinos, fechas y umbrales de notificación.

## Características principales

- **Búsqueda periódica** de vuelos en múltiples proveedores mediante scraping y APIs.
- **Conversión automática de monedas** (EUR/ARS a USD) usando tasas configurables.
- **Notificación por Telegram** con mensajes enriquecidos (HTML, emojis, links directos).
- **Almacenamiento en SQLite** de todas las oportunidades detectadas.
- **Validación de tickets reales** en Aerolíneas Argentinas antes de notificar (opcional).
- **Análisis estadístico** y generación automática de reportes PDF con gráficos.
- **Arquitectura modular**: fácil de agregar nuevos proveedores o regiones.
- **Configuración flexible** por región: destinos, fechas, umbrales y proveedores.
- **Logging detallado** para depuración y monitoreo.

## Instalación

1. Instala todas las dependencias:
   ```sh
   pip install -r requirements.txt
   ```
2. Configura tus variables de entorno `TELEGRAM_TOKEN` y `TELEGRAM_CHAT_ID` (puedes usar un archivo `.env`).
3. (Opcional) Si corres en CI/CD o headless, asegúrate de tener Chrome instalado y define `CHROME_PATH` si es necesario.
4. Ejecuta la app principal:
   ```sh
   python app.py
   ```

## Configuración

La configuración principal está en `config.py`:

```python
REGIONS = {
    "spain": {
        "providers": ["level", "aerolineas", "skyscanner", "amadeus"],
        "date_range": ("2026-01-01", "2026-06-30"),
        "thresholds": {"store": 1400, "notify": 1000, "one_way": 400},
        "destinations": ["MAD", "BCN"]
    },
    # ...otras regiones...
}
```

- **providers**: lista de proveedores a consultar para la región.
- **date_range**: rango de fechas (YYYY-MM-DD).
- **thresholds**: umbrales para guardar y notificar oportunidades.
- **destinations**: códigos IATA de los destinos.

## Arquitectura del proyecto

```
telegram-bot-pasajes/
├── app.py                # Lógica principal: orquestación, thresholds, notificaciones
├── config.py             # Configuración de regiones, fechas, umbrales y destinos
├── db.py                 # Funciones para SQLite (guardar y crear tabla)
├── telegram_utils.py     # Envío de mensajes y archivos por Telegram
├── get_aerolineas_token.py # Obtención automática del token de Aerolíneas (Selenium Wire)
├── stats.py              # Análisis estadístico y generación de PDF con gráficos
├── search_providers/     # Proveedores modulares (Level, Aerolíneas, Skyscanner, Amadeus)
│   ├── base_provider.py
│   ├── level.py
│   ├── aerolineas.py
│   ├── skyscanner.py
│   └── amadeus.py
├── requirements.txt      # Dependencias del proyecto
├── .env                  # Variables de entorno (no versionar)
└── .github/workflows/    # CI/CD para ejecución automática
```

## Uso y personalización

- Ajusta los umbrales y destinos en `config.py` según tus necesidades.
- Puedes agregar nuevos proveedores creando un archivo en `search_providers/` que herede de `BaseProvider`.
- El bot puede ejecutarse manualmente o programarse en CI/CD (ver `.github/workflows/run.yml`).

## Análisis y visualización

- Al finalizar cada consulta semanal, se genera un PDF con:
  - Estadísticas básicas (promedio, mediana, mínimo, máximo).
  - Gráficos: tendencias de precios, distribución, boxplot por destino y aerolínea.
  - Conclusiones automáticas para cada gráfico.
- Personaliza los análisis en `stats.py`.

## Requisitos

- Python >= 3.10
- requests, selenium-wire, reportlab, matplotlib, seaborn, numpy, pandas, python-dotenv

## Recomendaciones

- Aprovecha la ventana de octubre 2025 a junio 2026 para captar oportunidades en la temporada alta.
- Ajusta los thresholds según el contexto económico y tu perfil de oportunidad.
- Consulta manualmente en la web de las aerolíneas si tienes dudas sobre la disponibilidad real.
- Revisa los logs para depurar problemas de token, cambios en la API o falta de resultados.

---
