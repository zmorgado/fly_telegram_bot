import pandas as pd
import sqlite3
import logging
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import os

from telegram_utils import send_telegram_pdf

# --- Configuration ---
DB_FILE = "flights.db"
PDF_PATH = "weekly_flight_report.pdf"
IMG_DIR = "flight_stats_imgs"

# --- Data Fetching ---

def get_weekly_data():
    """Obtiene los datos de vuelos de los últimos 7 días desde la base de datos."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            query = "SELECT * FROM flights WHERE created_at >= date('now', '-7 days')"
            df = pd.read_sql_query(query, conn)
            logging.info(f"Se obtuvieron correctamente {len(df)} registros de los últimos 7 días.")
            return df
    except sqlite3.Error as e:
        logging.error(f"Error al obtener los datos semanales desde SQLite: {e}")
        return pd.DataFrame()

# --- Data Analysis & Visualization ---

def generate_visualizations(df):
    """Genera y guarda todas las visualizaciones."""
    if df.empty:
        return {}
    os.makedirs(IMG_DIR, exist_ok=True)
    
    visualizations = {
        "price_trends": plot_price_trends(df),
        "top_destinations": plot_top_destinations(df),
        "price_distribution": plot_price_distribution(df),
        "airline_comparison": plot_airline_comparison(df),
    }
    return {k: v for k, v in visualizations.items() if v}

def plot_price_trends(df):
    """Plots and saves a line chart of average price per day."""
    path = os.path.join(IMG_DIR, "price_trends.png")
    plt.figure(figsize=(10, 5))
    df['date'] = pd.to_datetime(df['date'])
    avg_price_per_day = df.groupby(df['date'].dt.date)['totalPrice'].mean()
    avg_price_per_day.plot(kind='line', marker='o')
    plt.title("Tendencia del Precio Promedio (Últimos 7 Días)")
    plt.xlabel("Fecha")
    plt.ylabel("Precio Promedio (USD)")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    return path

def plot_top_destinations(df):
    """Plots and saves a bar chart of the most popular destinations."""
    path = os.path.join(IMG_DIR, "top_destinations.png")
    plt.figure(figsize=(10, 5))
    dest_counts = df['destination'].value_counts().nlargest(10)
    sns.barplot(x=dest_counts.index, y=dest_counts.values, palette="viridis")
    plt.title("Top 10 Destinos (Últimos 7 Días)")
    plt.xlabel("Destino")
    plt.ylabel("Número de Vuelos")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    return path

def plot_price_distribution(df):
    """Plots and saves a histogram of flight prices."""
    path = os.path.join(IMG_DIR, "price_distribution.png")
    plt.figure(figsize=(10, 5))
    sns.histplot(df['totalPrice'], bins=20, kde=True)
    plt.title("Distribución de los Precios de Vuelos (Últimos 7 Días)")
    plt.xlabel("Precio Total (USD)")
    plt.ylabel("Frecuencia")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    return path

def plot_airline_comparison(df):
    """Plots and saves a boxplot comparing prices by airline."""
    path = os.path.join(IMG_DIR, "airline_comparison.png")
    plt.figure(figsize=(10, 5))
    sns.boxplot(x='airline', y='totalPrice', data=df)
    plt.title("Comparación de Precios por Aerolínea (Últimos 7 Días)")
    plt.xlabel("Aerolínea")
    plt.ylabel("Precio Total (USD)")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    return path

# --- PDF Generation ---

def create_pdf_report(df, visualizations):
    """Crea un informe PDF con estadísticas y visualizaciones."""
    doc = SimpleDocTemplate(PDF_PATH, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Título
    story.append(Paragraph("Informe Semanal de Estadísticas de Vuelos", styles['Title']))
    story.append(Spacer(1, 0.25 * inch))

    # Resumen
    story.append(Paragraph("Resumen de la Semana", styles['h2']))
    summary_text = f"Este informe cubre los datos de vuelos de los últimos 7 días. Se analizaron un total de {len(df)} vuelos."
    story.append(Paragraph(summary_text, styles['BodyText']))
    story.append(Spacer(1, 0.25 * inch))

    # Tabla de Métricas Clave
    if not df.empty:
        key_metrics = {
            "Precio Promedio": f"${df['totalPrice'].mean():.2f}",
            "Precio Mediano": f"${df['totalPrice'].median():.2f}",
            "Precio Mínimo": f"${df['totalPrice'].min():.2f}",
            "Precio Máximo": f"${df['totalPrice'].max():.2f}",
        }
        table_data = [["Métrica", "Valor"]] + list(key_metrics.items())
        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(table)
        story.append(Spacer(1, 0.25 * inch))

    # Visualizaciones y Conclusiones
    for title, path in visualizations.items():
        story.append(Paragraph(title.replace("_", " ").title(), styles['h2']))
        story.append(Image(path, width=6 * inch, height=3 * inch))
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph("Conclusión:", styles['h3']))
        conclusion_text = get_conclusion(title, df)
        story.append(Paragraph(conclusion_text, styles['BodyText']))
        story.append(Spacer(1, 0.25 * inch))

    doc.build(story)
    logging.info(f"Informe PDF creado exitosamente: {PDF_PATH}")

def get_conclusion(title, df):
    if title == "price_trends":
        avg_price = df['totalPrice'].mean()
        return f"El precio promedio de los vuelos en los últimos 7 días fue de ${avg_price:.2f}. La línea de tendencia muestra las fluctuaciones diarias, lo que puede ayudar a identificar los días más económicos para volar."
    if title == "top_destinations":
        top_dest = df['destination'].value_counts().idxmax()
        return f"El destino más popular en los últimos 7 días fue {top_dest}. Esta información puede usarse para entender la demanda de viajes actual."
    if title == "price_distribution":
        median_price = df['totalPrice'].median()
        return f"La mayoría de los vuelos se agrupan alrededor del precio mediano de ${median_price:.2f}. La distribución ayuda a comprender el rango de precios e identificar vuelos inusualmente baratos o caros."
    if title == "airline_comparison":
        avg_prices = df.groupby('airline')['totalPrice'].mean()
        comparison = " vs ".join([f"{name} (${price:.2f})" for name, price in avg_prices.items()])
        return f"Este gráfico compara la distribución de precios de las aerolíneas. En promedio, los precios son: {comparison}. Esto ayuda a elegir la aerolínea más económica."
    return ""

# --- Main Execution ---

def generate_and_send_report():
    """Función principal para generar y enviar el informe semanal."""
    logging.basicConfig(level=logging.INFO)
    logging.info("Iniciando la generación del informe semanal...")
    
    df = get_weekly_data()
    if df.empty:
        logging.warning("No hay datos disponibles para el informe semanal. Se omite el envío.")
        return

    visualizations = generate_visualizations(df)
    create_pdf_report(df, visualizations)
    
    caption = f"Informe semanal de vuelos [{datetime.now().strftime('%Y-%m-%d')}]"
    send_telegram_pdf(PDF_PATH, caption=caption)

if __name__ == "__main__":
    generate_and_send_report()