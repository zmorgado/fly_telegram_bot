import logging
from datetime import datetime, timedelta
import requests
from db import init_db, save_flight
from telegram_utils import send_telegram
from get_aerolineas_token import get_token_with_selenium_wire
from stats import analyze_flight_stats

# Configuración
STORING_PRICE_THRESHOLD = 900
PRICE_THRESHOLD = 800
EXCHANGE_RATE = 1200  # Tipo de cambio ARS/USD

DESTINATIONS = [
    {"code": "VLC", "name": "Valencia"},
    {"code": "BCN", "name": "Barcelona"},
    {"code": "MAD", "name": "Madrid"}
]
START_DATE = datetime(2026, 5, 1)
END_DATE = datetime(2026, 6, 16)

logging.basicConfig(level=logging.INFO)

logging.getLogger("seleniumwire").setLevel(logging.WARNING)

def get_api_url(destination, month, year):
    return f"https://www.flylevel.com/nwe/flights/api/calendar/?triptype=RT&origin=EZE&destination={destination}&month={month:02d}&year={year}&currencyCode=USD"

def get_web_link(destination, date, return_date):
    return (
        f"https://www.flylevel.com/Flight/Select?culture=es-ES&triptype=RT&o1=EZE&d1={destination}"
        f"&dd1={date}&ADT=1&CHD=0&INL=0&r=true&mm=false&dd2={return_date}&forcedCurrency=USD&forcedCulture=es-ES&newecom=true&currency=USD"
    )

def get_calendar_offers(token, url):
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        data = res.json()
        return data.get("calendarOffers", {})
    except Exception as e:
        logging.error(f"Error consultando calendarOffers: {e}")
        return {}

def check_flights():
    logging.info("Iniciando consulta de vuelos para Level...")
    level_stats = []
    for dest in DESTINATIONS:
        day_price_map = {}
        d = START_DATE.replace(day=1)
        while d <= END_DATE:
            api_url = get_api_url(dest["code"], d.month, d.year)
            try:
                res = requests.get(api_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                res.raise_for_status()
                for day in res.json().get("data", {}).get("dayPrices", []):
                    # Solo guardar el menor precio para cada fecha
                    if (day["date"] not in day_price_map) or (day["price"] < day_price_map[day["date"]]["price"]):
                        day_price_map[day["date"]] = day
            except Exception as e:
                logging.error("Error consultando API: %s", e)
            d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        # Trabajar con días únicos ordenados
        unique_days = sorted(day_price_map.values(), key=lambda x: x["date"])
        min_total_price = None
        min_combo = None
        se_guardo = False
        for i, outbound in enumerate(unique_days):
            outbound_date = datetime.strptime(outbound["date"], "%Y-%m-%d")
            if outbound_date < START_DATE or outbound_date > END_DATE:
                continue
            for inbound in unique_days[i+1:]:
                inbound_date = datetime.strptime(inbound["date"], "%Y-%m-%d")
                # Solo considerar regresos exactamente 14 días después de la ida
                if (inbound_date - outbound_date).days != 14:
                    continue
                if inbound_date > END_DATE:
                    continue
                if outbound["price"] is None or inbound["price"] is None:
                    continue
                total_price = outbound["price"] + inbound["price"]
                if min_total_price is None or total_price < min_total_price:
                    min_total_price = total_price
                    min_combo = (outbound, inbound)
                # Solo guardar y notificar si está por debajo del umbral
                if total_price < STORING_PRICE_THRESHOLD:
                    se_guardo = True
                    web_link = get_web_link(dest["code"], outbound["date"], inbound["date"])
                    save_flight({
                        "date": outbound["date"],
                        "price": outbound["price"],
                        "return_date": inbound["date"],
                        "return_price": inbound["price"],
                        "destination": dest["code"],
                        "webLink": web_link,
                        "totalPrice": total_price
                    })
                # Guardar para análisis estadístico
                level_stats.append({
                    "date": outbound["date"],
                    "price": outbound["price"],
                    "destination": dest["code"]
                })
                # Solo guardar y notificar si está por debajo del umbral
                if total_price < PRICE_THRESHOLD:
                    msg = (
                        f"¡Oportunidad Level!\nDestino: {dest['name']}\nIda: {outbound['date']} (${outbound['price']})"
                        f"\nVuelta: {inbound['date']} (${inbound['price']})\nTotal: ${total_price}\n{web_link}"
                    )
                    send_telegram(msg)
        if not se_guardo and min_combo:
            outbound, inbound = min_combo
            logging.info(f"[Level] Menor combinación para {dest['name']}: Ida {outbound['date']} (${outbound['price']}), Vuelta {inbound['date']} (${inbound['price']}), Total: ${min_total_price}")
    logging.info("Consulta completada para Level.")

    # --- Aerolíneas Argentinas ---
    logging.info("Iniciando consulta de vuelos para Aerolíneas Argentinas...")
    token = get_token_with_selenium_wire()
    if not token:
        logging.error("No se pudo obtener el token de Aerolíneas Argentinas.")
        return

    aerolineas_stats = []
    for dest in DESTINATIONS:
        d = START_DATE.replace(day=1)
        seen = set()  # Para evitar duplicados
        while d <= END_DATE:
            # Construir legs para el mes completo (flexDates=true)
            leg1 = f"BUE-{dest['code']}-{d.strftime('%Y%m%d')}"
            leg2 = f"{dest['code']}-BUE-{d.strftime('%Y%m%d')}"  # Placeholder, se ignora por flexDates
            url = (
                "https://api.aerolineas.com.ar/v1/flights/offers"
                f"?adt=1&inf=0&chd=0&flexDates=true&cabinClass=Economy&flightType=ROUND_TRIP"
                f"&leg={leg1}&leg={leg2}"
            )
            offers = get_calendar_offers(token, url)
            # Construir mapa de fechas y precios (solo si hay ofertas)
            ida_map = {}
            min_total_price = None
            min_ida = None
            se_guardo = False
            for offer in offers.get("0", []):
                if not isinstance(offer, dict):
                    continue
                if offer.get("soldOut"):
                    continue
                offer_details = offer.get("offerDetails")
                if not offer_details:
                    continue
                seat_info = offer_details.get("seatAvailability", {})
                if seat_info and seat_info.get("seats", 0) < 1:
                    continue
                outbound_date = offer.get("departure")
                if not offer_details.get("fare"):
                    continue
                price_ars = offer_details["fare"].get("total")
                if not price_ars:
                    continue
                price_usd = int(price_ars / EXCHANGE_RATE)
                ida_map[outbound_date] = price_usd
                aerolineas_stats.append({
                    "date": outbound_date,
                    "price": price_usd,
                    "destination": dest["code"]
                })
                if min_total_price is None or price_usd < min_total_price:
                    min_total_price = price_usd
                    min_ida = (outbound_date, price_usd)
            # Procesar solo combinaciones ida/vuelta con 14 días exactos
            for ida_date, total_price in ida_map.items():
                try:
                    d1 = datetime.strptime(ida_date, "%Y-%m-%d")
                except Exception:
                    continue
                vuelta_date = (d1 + timedelta(days=14)).strftime("%Y-%m-%d")
                if vuelta_date > END_DATE.strftime("%Y-%m-%d"):
                    continue
                # Evitar duplicados exactos
                key = (ida_date, vuelta_date, total_price)
                if key in seen:
                    continue
                seen.add(key)
                leg1 = f"BUE-{dest['code']}-{d1.strftime('%Y%m%d')}"
                leg2 = f"{dest['code']}-BUE-{(d1+timedelta(days=14)).strftime('%Y%m%d')}"
                web_link = (
                    f"https://www.aerolineas.com.ar/flights-offers?adt=1&inf=0&chd=0&flexDates=false&cabinClass=Economy&flightType=ROUND_TRIP&leg={leg1}&leg={leg2}"
                )
                # Solo guardar y notificar si está por debajo del umbral
                if total_price < STORING_PRICE_THRESHOLD:
                    se_guardo = True
                    save_flight({
                        "date": ida_date,
                        "price": total_price,
                        "return_date": vuelta_date,
                        "return_price": None,
                        "destination": dest["code"],
                        "webLink": web_link,
                        "totalPrice": total_price
                    })
                    if total_price < PRICE_THRESHOLD:
                        msg = (
                            f"¡Oportunidad Aerolíneas!\nDestino: {dest['name']}\nIda: {ida_date} (${total_price})"
                            f"\nVuelta: {vuelta_date}\nTotal: ${total_price}\n{web_link}"
                        )
                        send_telegram(msg)
            d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        if not se_guardo and min_ida:
            logging.info(f"[Aerolíneas] Menor opción para {dest['name']}: Ida {min_ida[0]} (${min_ida[1]})")
    logging.info("Consulta completada para Aerolíneas Argentinas.")

    # Análisis estadístico: TODO: descomentar cuando se mejore la implementación
    # logging.info("Iniciando análisis estadístico de vuelos...")
    
    # analyze_flight_stats({
    #     "level": level_stats,
    #     "aerolineas": aerolineas_stats
    # })

def main():
    init_db()
    # while True:
    check_flights()
        # time.sleep(120)  # 2 minutos

if __name__ == "__main__":
    main()
