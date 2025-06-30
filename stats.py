import pandas as pd
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
import requests
import time
import json
from get_aerolineas_token import get_token_with_selenium_wire
from telegram_utils import send_telegram_pdf

# --- Configuration ---
PDF_PATH = "weekly_flight_report.pdf"
IMG_DIR = "flight_stats_imgs"
EXCHANGE_RATE = {
    "ARS_USD": 1200,
    "EUR_USD": 1.17
}
DESTINATIONS = [
    {"code": "VLC", "name": "Valencia"},
    {"code": "BCN", "name": "Barcelona"},
    {"code": "MAD", "name": "Madrid"},
    {"code": "SVQ", "name": "Sevilla"},
]
START_DATE = datetime.now()
END_DATE = START_DATE + timedelta(days=365)

# --- Robust Request Function with Retries ---
def requests_get_with_retries(url, headers, timeout=10, retries=3, backoff_factor=0.5):
    for i in range(retries):
        try:
            res = requests.get(url, headers=headers, timeout=timeout)
            if 400 <= res.status_code < 500:
                logging.error(f"Client error {res.status_code} for {url}. No more retries.")
                return None
            res.raise_for_status()
            return res
        except requests.exceptions.RequestException as e:
            logging.warning(f"Request to {url} failed (attempt {i+1}/{retries}): {e}")
            if i < retries - 1:
                time.sleep(backoff_factor * (2 ** i))
            else:
                logging.error(f"Could not connect to {url} after {retries} attempts.")
                return None

# --- Data Fetching ---

def get_level_flights():
    """Fetches all available flights from Level."""
    logging.info("Fetching flights from Level...")
    all_flights = []
    for dest in DESTINATIONS:
        day_price_map = {}
        d = START_DATE.replace(day=1)
        while d <= END_DATE:
            api_url = f"https://www.flylevel.com/nwe/flights/api/calendar/?triptype=RT&origin=EZE&destination={dest['code']}&month={d.month:02d}&year={d.year}&currencyCode=USD"
            res = requests_get_with_retries(api_url, headers={"User-Agent": "Mozilla/5.0"})
            if res:
                try:
                    for day in res.json().get("data", {}).get("dayPrices", []):
                        if day.get("price") is not None:
                            if (day["date"] not in day_price_map) or (day["price"] < day_price_map[day["date"]]["price"]):
                                day_price_map[day["date"]] = day
                except json.JSONDecodeError as e:
                    logging.error(f"Error decoding JSON from {api_url}: {e}")
            d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)

        unique_days = sorted(day_price_map.values(), key=lambda x: x["date"])
        for i, outbound in enumerate(unique_days):
            for inbound in unique_days[i+1:]:
                outbound_date = datetime.strptime(outbound["date"], "%Y-%m-%d")
                inbound_date = datetime.strptime(inbound["date"], "%Y-%m-%d")
                if (inbound_date - outbound_date).days == 14:
                    price_out_usd = round(outbound["price"] * EXCHANGE_RATE["EUR_USD"], 2)
                    price_in_usd = round(inbound["price"] * EXCHANGE_RATE["EUR_USD"], 2)
                    total_price = price_out_usd + price_in_usd
                    all_flights.append({
                        "date": outbound["date"],
                        "totalPrice": total_price,
                        "destination": dest["code"],
                        "airline": "Level"
                    })
    return all_flights

def get_aerolineas_flights():
    """Fetches all available flights from Aerolineas Argentinas."""
    logging.info("Fetching flights from Aerolíneas Argentinas...")
    token = get_token_with_selenium_wire()
    if not token:
        logging.error("Could not get token for Aerolíneas Argentinas.")
        return []

    all_flights = []
    for dest in DESTINATIONS:
        d = START_DATE.replace(day=1)
        while d <= END_DATE:
            leg1 = f"BUE-{dest['code']}-{d.strftime('%Y%m%d')}"
            leg2 = f"{dest['code']}-BUE-{d.strftime('%Y%m%d')}"
            url = f"https://api.aerolineas.com.ar/v1/flights/offers?adt=1&inf=0&chd=0&flexDates=true&cabinClass=Economy&flightType=ROUND_TRIP&leg={leg1}&leg={leg2}"
            headers = {"Authorization": f"Bearer {token}", "User-Agent": "Mozilla/5.0", "Accept": "application/json"}
            res = requests_get_with_retries(url, headers=headers)
            if res:
                try:
                    offers = res.json().get("calendarOffers", {})
                    ida_map, vuelta_map = {}, {}
                    for offer in offers.get("0", []):
                        if offer and isinstance(offer, dict) and not offer.get("soldOut") and isinstance(offer.get("offerDetails"), dict) and offer["offerDetails"].get("fare"):
                            price_usd = int(offer["offerDetails"]["fare"].get("total") / EXCHANGE_RATE["ARS_USD"])
                            ida_map[offer.get("departure")] = {"price": price_usd}
                    for offer in offers.get("1", []):
                        if offer and isinstance(offer, dict) and not offer.get("soldOut") and isinstance(offer.get("offerDetails"), dict) and offer["offerDetails"].get("fare"):
                            price_usd = int(offer["offerDetails"]["fare"].get("total") / EXCHANGE_RATE["ARS_USD"])
                            vuelta_map[offer.get("departure")] = {"price": price_usd}

                    for ida_date, ida_info in ida_map.items():
                        d1 = datetime.strptime(ida_date, "%Y-%m-%d")
                        vuelta_date = (d1 + timedelta(days=14)).strftime("%Y-%m-%d")
                        if vuelta_date in vuelta_map:
                            total_price = ida_info["price"] + vuelta_map[vuelta_date]["price"]
                            all_flights.append({
                                "date": ida_date,
                                "totalPrice": total_price,
                                "destination": dest["code"],
                                "airline": "Aerolíneas Argentinas"
                            })
                except json.JSONDecodeError as e:
                    logging.error(f"Error decoding JSON from {url}: {e}")
            d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    return all_flights

# --- Data Analysis & Visualization ---

def generate_visualizations(df):
    """Generates and saves all visualizations."""
    if df.empty:
        return {}
    os.makedirs(IMG_DIR, exist_ok=True)
    
    visualizations = {
        "price_trends": plot_price_trends(df),
        "top_destinations": plot_top_destinations(df),
        "price_distribution": plot_price_distribution(df),
        "price_vs_destination": plot_price_vs_destination(df),
    }
    return {k: v for k, v in visualizations.items() if v}

# --- Nuevo gráfico: Precio vs Destino por Aerolínea ---
def plot_price_vs_destination(df):
    """Boxplot de precios por destino y aerolínea, asegurando todos los destinos."""
    path = os.path.join(IMG_DIR, "price_vs_destination.png")
    plt.figure(figsize=(18, 8))
    plt.rcParams.update({'font.size': 16, 'font.family': 'DejaVu Sans'})
    destinos_order = [d['code'] for d in DESTINATIONS]
    for airline in df['airline'].unique():
        subset = df[df['airline'] == airline]
        sns.boxplot(
            data=subset,
            x='destination',
            y='totalPrice',
            order=destinos_order,
            width=0.5,
            boxprops=dict(alpha=0.6),
            showfliers=False,
            label=airline
        )
    plt.title("Price Distribution per Destination by Airline", fontsize=22)
    plt.xlabel("Destination", fontsize=18)
    plt.ylabel("Total Price (USD)", fontsize=18)
    plt.xticks(fontsize=16)
    plt.legend(df['airline'].unique(), title="Airline", fontsize=16, title_fontsize=18)
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()
    return path

# --- Asegurar todos los destinos en top_destinations ---
def plot_top_destinations(df):
    """Plots and saves a grouped bar chart of top destinations by airline, asegurando todos los destinos."""
    path = os.path.join(IMG_DIR, "top_destinations.png")
    plt.figure(figsize=(16, 8))
    plt.rcParams.update({'font.size': 16, 'font.family': 'DejaVu Sans'})
    destinos_order = [d['code'] for d in DESTINATIONS]
    airlines = df['airline'].unique()
    dest_counts = df.groupby(['destination', 'airline']).size().unstack(fill_value=0)
    # Asegurar que todos los destinos estén presentes
    for dest in destinos_order:
        if dest not in dest_counts.index:
            dest_counts.loc[dest] = [0]*len(dest_counts.columns)
    dest_counts = dest_counts.loc[destinos_order]
    dest_counts.plot(kind='bar', stacked=False, ax=plt.gca())
    plt.title("Top Destinations by Airline (Last 7 Days)", fontsize=22)
    plt.xlabel("Destination", fontsize=18)
    plt.ylabel("Number of Flights", fontsize=18)
    plt.xticks(rotation=45, fontsize=16)
    plt.legend(title="Airline", fontsize=16, title_fontsize=18)
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()
    return path

def plot_price_trends(df):
    """Plots and saves a line chart of average price per day, differentiated by airline."""
    path = os.path.join(IMG_DIR, "price_trends.png")
    plt.figure(figsize=(16, 8))
    plt.rcParams.update({'font.size': 16, 'font.family': 'DejaVu Sans'})
    df['date'] = pd.to_datetime(df['date'])
    avg_price_per_day = df.groupby([df['date'].dt.date, 'airline'])['totalPrice'].mean().unstack()
    avg_price_per_day.plot(kind='line', marker='o', ax=plt.gca())
    plt.title("Average Price Trend by Airline (Last 7 Days)", fontsize=22)
    plt.xlabel("Date", fontsize=18)
    plt.ylabel("Average Price (USD)", fontsize=18)
    plt.grid(True)
    plt.legend(title="Airline", fontsize=16, title_fontsize=18)
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()
    return path

def plot_price_distribution(df):
    """Plots and saves overlapping density plots of flight prices by airline."""
    path = os.path.join(IMG_DIR, "price_distribution.png")
    plt.figure(figsize=(16, 8))
    plt.rcParams.update({'font.size': 16, 'font.family': 'DejaVu Sans'})
    sns.kdeplot(data=df, x='totalPrice', hue='airline', fill=True, common_norm=False)
    plt.title("Price Distribution by Airline (Last 7 Days)", fontsize=22)
    plt.xlabel("Total Price (USD)", fontsize=18)
    plt.ylabel("Density", fontsize=18)
    plt.legend(title="Airline", fontsize=16, title_fontsize=18)
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()
    return path

# --- PDF Generation ---

def create_pdf_report(df, visualizations):
    """Creates a PDF report with statistics and visualizations."""
    doc = SimpleDocTemplate(PDF_PATH, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Weekly Flight Statistics Report", styles['Title']))
    story.append(Spacer(1, 0.25 * inch))

    story.append(Paragraph("Weekly Summary", styles['h2']))
    summary_text = f"This report covers flight data from the last 7 days, analyzing {len(df)} flights."
    story.append(Paragraph(summary_text, styles['BodyText']))
    story.append(Spacer(1, 0.25 * inch))

    if not df.empty:
        key_metrics = {
            "Average Price": f"${df['totalPrice'].mean():.2f}",
            "Median Price": f"${df['totalPrice'].median():.2f}",
            "Minimum Price": f"${df['totalPrice'].min():.2f}",
            "Maximum Price": f"${df['totalPrice'].max():.2f}",
        }
        table_data = [["Metric", "Value"]] + list(key_metrics.items())
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

    for title, path in visualizations.items():
        story.append(Paragraph(title.replace("_", " ").title(), styles['h2']))
        story.append(Image(path, width=7.5 * inch, height=4 * inch))
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph("Conclusion:", styles['h3']))
        conclusion_text = get_conclusion(title, df)
        story.append(Paragraph(conclusion_text, styles['BodyText']))
        story.append(Spacer(1, 0.25 * inch))

    doc.build(story)
    logging.info(f"PDF report created successfully: {PDF_PATH}")

def get_conclusion(title, df):
    if title == "price_trends":
        return "The line chart displays the daily average flight prices for each airline. This helps identify which airline consistently offers lower prices and reveals how their pricing strategies compare over time."
    if title == "top_destinations":
        return "The grouped bar chart shows the number of flight deals found per destination, broken down by airline. This highlights which airline offers more opportunities for specific routes and what the most competitive destinations are."
    if title == "price_distribution":
        return "The density plot illustrates the distribution of flight prices for each airline. This visualization helps in understanding the typical price range for each carrier and identifying which one is more likely to offer deals at lower price points."
    if title == "price_vs_destination":
        return "The boxplot shows the distribution of prices for each destination, separated by airline. This allows a direct comparison of price ranges and medians for each route and carrier, facilitando la identificación de oportunidades y outliers."
    return ""

# --- Main Execution ---

def main():
    """Main function to generate and send the weekly report."""
    logging.basicConfig(level=logging.INFO)
    # if datetime.now().weekday() != 6: # 0=lunes, 6=domingo
    #     logging.info("Today is not Sunday. Skipping weekly report.")
    #     return

    logging.info("Initiating the generation of the weekly report...")
    
    level_flights = get_level_flights()
    aerolineas_flights = get_aerolineas_flights()
    
    all_flights = level_flights + aerolineas_flights
    if not all_flights:
        logging.warning("No data available for the weekly report. Skipping.")
        return

    df = pd.DataFrame(all_flights)
    visualizations = generate_visualizations(df)
    create_pdf_report(df, visualizations)
    
    caption = f"Weekly flight report [{datetime.now().strftime('%Y-%m-%d')}]"
    send_telegram_pdf(PDF_PATH, caption=caption)

if __name__ == "__main__":
    main()
