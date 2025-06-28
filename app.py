import logging
from datetime import datetime, timedelta
import requests
from db import init_db, save_flight
from telegram_utils import send_telegram
from get_aerolineas_token import get_token_with_selenium_wire
from stats import analyze_flight_stats
import json

# Configuración
STORING_PRICE_THRESHOLD = 1100
PRICE_THRESHOLD = 900
EXCHANGE_RATE = {
    "ARS_USD": 1200,   # Pesos argentinos a dólares
    "EUR_USD": 1.17    # Euros a dólares (ejemplo, ajustar según mercado)
}  # Tipo de cambio ARS/USD
ONE_WAY_PRICE_THRESHOLD = 400  # USD for both airlines

DESTINATIONS = [
    {"code": "VLC", "name": "Valencia"},
    {"code": "BCN", "name": "Barcelona"},
    {"code": "MAD", "name": "Madrid"},
    {"code": "SVQ", "name": "Sevilla"}
]
START_DATE = datetime(2025, 10, 1)
END_DATE = datetime(2026, 6, 15)

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

def validate_real_ticket_aerolineas(token, dest_code, ida_date, vuelta_date):
    """
    Consulta la API de Aerolíneas con flexDates=false para validar si existe un ticket real para la combinación ida/vuelta.
    Devuelve True si hay al menos una oferta, False si no.
    """
    leg1 = f"BUE-{dest_code}-{ida_date.replace('-', '')}"
    leg2 = f"{dest_code}-BUE-{vuelta_date.replace('-', '')}"
    url = (
        "https://api.aerolineas.com.ar/v1/flights/offers"
        f"?adt=1&inf=0&chd=0&flexDates=false&cabinClass=Economy&flightType=ROUND_TRIP"
        f"&leg={leg1}&leg={leg2}"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        data = res.json()
        offers = data.get("calendarOffers", {})
        if offers.get("0") and offers.get("1"):
            return True, offers
        if data.get("offers"):
            return True, data
        return False, data
    except Exception as e:
        logging.warning(f"Error validando ticket real Aerolíneas: {e}")
        return False, None

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
            # Notificación solo ida para Level
            if outbound["price"] is not None:
                price_usd = round(outbound["price"] * EXCHANGE_RATE["EUR_USD"], 2)
                if price_usd < ONE_WAY_PRICE_THRESHOLD:
                    web_link = f"https://www.flylevel.com/Flight/Select?culture=es-ES&triptype=OW&o1=EZE&d1={dest['code']}&dd1={outbound['date']}&ADT=1&CHD=0&INL=0&r=false&mm=false&forcedCurrency=USD&forcedCulture=es-ES&newecom=true&currency=USD"
                    msg = (
                        f"✈️ <b>Level</b> | {dest['name']}\n"
                        f"📅 Ida: <b>{outbound['date']}</b>\n"
                        f"💸 Precio solo ida: <b>${price_usd} USD</b>\n"
                        f'<a href="{web_link}">Link</a>'
                    )
                    send_telegram(msg, parse_mode="HTML")
            for inbound in unique_days[i+1:]:
                inbound_date = datetime.strptime(inbound["date"], "%Y-%m-%d")
                # Solo considerar regresos exactamente 14 días después de la ida
                if (inbound_date - outbound_date).days != 14:
                    continue
                if inbound_date > END_DATE:
                    continue
                if outbound["price"] is None or inbound["price"] is None:
                    continue
                # Convertir ambos precios de EUR a USD
                price_out_usd = round(outbound["price"] * EXCHANGE_RATE["EUR_USD"], 2)
                price_in_usd = round(inbound["price"] * EXCHANGE_RATE["EUR_USD"], 2)
                total_price = price_out_usd + price_in_usd
                if min_total_price is None or total_price < min_total_price:
                    min_total_price = total_price
                    min_combo = (outbound, inbound)
                # Solo guardar y notificar si está por debajo del umbral
                if total_price < STORING_PRICE_THRESHOLD:
                    se_guardo = True
                    web_link = get_web_link(dest["code"], outbound["date"], inbound["date"])
                    save_flight({
                        "date": outbound["date"],
                        "price": price_out_usd,
                        "return_date": inbound["date"],
                        "return_price": price_in_usd,
                        "destination": dest["code"],
                        "webLink": web_link,
                        "totalPrice": total_price,
                        "airline": "Level"
                    })
                # Guardar para análisis estadístico
                level_stats.append({
                    "date": outbound["date"],
                    "price": price_out_usd,
                    "destination": dest["code"]
                })
                # Solo guardar y notificar si está por debajo del umbral
                if total_price < PRICE_THRESHOLD:
                    duration = (inbound_date - outbound_date).days
                    msg = (
                        f"✈️ <b>Level</b> | {dest['name']}\n"
                        f"📅 Ida: <b>{outbound['date']}</b>  |  Vuelta: <b>{inbound['date']}</b>\n"
                        f"⏳ Duración: <b>{duration} días</b>\n"
                        f"💸 Ida: <b>${price_out_usd} USD</b>  |  Vuelta: <b>${price_in_usd} USD</b>\n"
                        f"💰 Total: <b>${total_price} USD</b>\n"
                        f'<a href="{web_link}">Link</a>'
                    )
                    send_telegram(msg, parse_mode="HTML")
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
            # Log explícito si no hay vuelos disponibles en ROUND TRIP
            if not offers.get("0") and not offers.get("1"):
                logging.warning(f"[AEROLINEAS] Sin vuelos disponibles para {dest['code']} en ROUND TRIP.")
            ida_map = {}
            vuelta_map = {}
            min_total_price = None
            min_ida = None
            se_guardo = False
            # Mapear todas las idas y vueltas con su precio y objeto
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
                price_usd = int(price_ars / EXCHANGE_RATE["ARS_USD"])
                ida_map[outbound_date] = {"price": price_usd, "obj": offer}
                aerolineas_stats.append({
                    "date": outbound_date,
                    "price": price_usd,
                    "destination": dest["code"]
                })
                # Notificación solo ida
                if price_usd < ONE_WAY_PRICE_THRESHOLD:
                    web_link = f"https://www.aerolineas.com.ar/flights-offers?adt=1&inf=0&chd=0&flexDates=false&cabinClass=Economy&flightType=ONE_WAY&leg=BUE-{dest['code']}-{outbound_date.replace('-', '')}"
                    msg = (
                        f"✈️ <b>Aerolíneas Argentinas</b> | {dest['name']}\n"
                        f"📅 Ida: <b>{outbound_date}</b>\n"
                        f"💸 Precio solo ida: <b>${price_usd}</b>\n"
                        f'<a href="{web_link}">Link</a>'
                    )
                    send_telegram(msg, parse_mode="HTML")                    
                if min_ida is None or price_usd < min_ida[1]:
                    min_ida = (outbound_date, price_usd)
            for offer in offers.get("1", []):
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
                return_date = offer.get("departure")
                if not offer_details.get("fare"):
                    continue
                price_ars = offer_details["fare"].get("total")
                if not price_ars:
                    continue
                price_usd = int(price_ars / EXCHANGE_RATE["ARS_USD"])
                vuelta_map[return_date] = {"price": price_usd, "obj": offer}
                # No notificación solo vuelta
            # Procesar solo combinaciones ida/vuelta con 14 días exactos
            api_saved = False  # Solo guardar una vez por ciclo
            for ida_date, ida_info in ida_map.items():
                d1 = None
                try:
                    d1 = datetime.strptime(ida_date, "%Y-%m-%d")
                except Exception:
                    continue
                vuelta_date = (d1 + timedelta(days=14)).strftime("%Y-%m-%d")
                if vuelta_date > END_DATE.strftime("%Y-%m-%d"):
                    continue
                if vuelta_date not in vuelta_map:
                    continue
                total_price = ida_info["price"] + vuelta_map[vuelta_date]["price"]
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
                    # Validar ticket real antes de guardar/notificar
                    is_real, real_response = validate_real_ticket_aerolineas(token, dest["code"], ida_date, vuelta_date)
                    if not is_real:
                        continue  # No notificar ni guardar si no es real
                    se_guardo = True
                    save_flight({
                        "date": ida_date,
                        "price": ida_info["price"],
                        "return_date": vuelta_date,
                        "return_price": vuelta_map[vuelta_date]["price"],
                        "destination": dest["code"],
                        "webLink": web_link,
                        "totalPrice": total_price,
                        "airline": "Aerolíneas Argentinas"
                    })
                    if total_price < PRICE_THRESHOLD:
                        duration = 14
                        msg = (
                            f"✈️ <b>Aerolíneas Argentinas</b> | {dest['name']} (VALIDADO)\n"
                            f"📅 Ida: <b>{ida_date}</b>  |  Vuelta: <b>{vuelta_date}</b>\n"
                            f"⏳ Duración: <b>{duration} días</b>\n"
                            f"💸 Ida: <b>${ida_info['price']}</b>  |  Vuelta: <b>${vuelta_map[vuelta_date]['price']}</b>\n"
                            f"💰 Total: <b>${total_price}</b>\n"
                            f'<a href="{web_link}">Link</a>'
                        )
                        send_telegram(msg, parse_mode="HTML")
                        # Guardar solo la respuesta relevante de la API para la combinación notificada
                        if not api_saved and real_response:
                            fname = f"aerolineas_api_{dest['code']}_{ida_date}_{vuelta_date}_real.json"
                            with open(fname, "w", encoding="utf-8") as f:
                                json.dump(real_response, f, ensure_ascii=False, indent=2)
                            api_saved = True
            d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        if not se_guardo and min_ida and isinstance(min_ida, (list, tuple)) and len(min_ida) >= 2:
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
