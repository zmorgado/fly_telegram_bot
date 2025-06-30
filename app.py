import logging
from datetime import datetime, timedelta
import requests
import time
import json
from db import init_db, save_flight
from telegram_utils import send_telegram
from get_aerolineas_token import get_token_with_selenium_wire

# --- Configuration ---
PRICE_THRESHOLD = 900  # USD, round trip notification threshold
ONE_WAY_PRICE_THRESHOLD = 400  # USD, one-way notification threshold
EXCHANGE_RATE = {
    "ARS_USD": 1200,
    "EUR_USD": 1.17
}
DESTINATIONS = [
    {"code": "VLC", "name": "Valencia"},
    {"code": "BCN", "name": "Barcelona"},
    {"code": "MAD", "name": "Madrid"},
    {"code": "SVQ", "name": "Sevilla"}
]

# --- Dynamic Date Range ---
START_DATE = datetime.now()
END_DATE = START_DATE + timedelta(days=365)

logging.basicConfig(level=logging.INFO)
logging.getLogger("seleniumwire").setLevel(logging.WARNING)

# --- Performance Metrics ---
performance_metrics = {}

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
    res = requests_get_with_retries(url, headers=headers)
    if res:
        try:
            data = res.json()
            return data.get("calendarOffers", {})
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON from {url}: {e}")
            return {}
    return {}

def validate_real_ticket_aerolineas(token, dest_code, ida_date, vuelta_date):
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
    res = requests_get_with_retries(url, headers=headers)
    if res:
        try:
            data = res.json()
            if data.get("calendarOffers", {}).get("0") and data.get("calendarOffers", {}).get("1"):
                return True, data
            if data.get("offers"):
                return True, data
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON during validation: {e}")
    return False, None

def check_flights():
    start_time = time.time()
    logging.info("Starting flight search for Level...")
    level_start_time = time.time()
    for dest in DESTINATIONS:
        day_price_map = {}
        d = START_DATE.replace(day=1)
        while d <= END_DATE:
            api_url = get_api_url(dest["code"], d.month, d.year)
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
            outbound_date = datetime.strptime(outbound["date"], "%Y-%m-%d")
            if not (START_DATE <= outbound_date <= END_DATE):
                continue

            if outbound["price"] is not None:
                price_usd = round(outbound["price"] * EXCHANGE_RATE["EUR_USD"], 2)
                if price_usd < ONE_WAY_PRICE_THRESHOLD:
                    web_link = f"https://www.flylevel.com/Flight/Select?culture=es-ES&triptype=OW&o1=EZE&d1={dest['code']}&dd1={outbound['date']}&ADT=1&CHD=0&INL=0&r=false&mm=false&forcedCurrency=USD&forcedCulture=es-ES&newecom=true&currency=USD"
                    save_flight({"date": outbound["date"], "price": price_usd, "destination": dest["code"], "webLink": web_link, "totalPrice": price_usd, "airline": "Level", "flight_type": "ONE_WAY"})
                    send_telegram(f"✈️ <b>Level</b> | {dest['name']}\n📅 Ida: <b>{outbound['date']}</b>\n💸 Precio solo ida: <b>${price_usd} USD</b>\n<a href=\"{web_link}\">Link</a>", parse_mode="HTML")

            for inbound in unique_days[i+1:]:
                inbound_date = datetime.strptime(inbound["date"], "%Y-%m-%d")
                if (inbound_date - outbound_date).days != 14 or inbound_date > END_DATE:
                    continue
                if inbound["price"] is None:
                    continue

                price_out_usd = round(outbound["price"] * EXCHANGE_RATE["EUR_USD"], 2)
                price_in_usd = round(inbound["price"] * EXCHANGE_RATE["EUR_USD"], 2)
                total_price = price_out_usd + price_in_usd

                if total_price < PRICE_THRESHOLD:
                    web_link = get_web_link(dest["code"], outbound["date"], inbound["date"])
                    save_flight({"date": outbound["date"], "price": price_out_usd, "return_date": inbound["date"], "return_price": price_in_usd, "destination": dest["code"], "webLink": web_link, "totalPrice": total_price, "airline": "Level"})
                    send_telegram(f"✈️ <b>Level</b> | {dest['name']}\n📅 Ida: <b>{outbound['date']}</b> | Vuelta: <b>{inbound['date']}</b>\n⏳ Duración: <b>14 días</b>\n💸 Ida: <b>${price_out_usd} USD</b> | Vuelta: <b>${price_in_usd} USD</b>\n💰 Total: <b>${total_price} USD</b>\n<a href=\"{web_link}\">Link</a>", parse_mode="HTML")
    performance_metrics["level_search_time"] = time.time() - level_start_time
    logging.info("Level flight search completed.")

    logging.info("Starting flight search for Aerolíneas Argentinas...")
    token_start_time = time.time()
    token = get_token_with_selenium_wire()
    performance_metrics["aerolineas_token_time"] = time.time() - token_start_time
    if not token:
        logging.error("Could not get token for Aerolíneas Argentinas.")
        return

    aerolineas_start_time = time.time()
    for dest in DESTINATIONS:
        d = START_DATE.replace(day=1)
        seen = set()
        while d <= END_DATE:
            leg1 = f"BUE-{dest['code']}-{d.strftime('%Y%m%d')}"
            leg2 = f"{dest['code']}-BUE-{d.strftime('%Y%m%d')}"
            url = f"https://api.aerolineas.com.ar/v1/flights/offers?adt=1&inf=0&chd=0&flexDates=true&cabinClass=Economy&flightType=ROUND_TRIP&leg={leg1}&leg={leg2}"
            offers = get_calendar_offers(token, url)

            ida_map, vuelta_map = {}, {}
            for offer in offers.get("0", []):
                if offer and isinstance(offer, dict) and not offer.get("soldOut") and isinstance(offer.get("offerDetails"), dict) and offer["offerDetails"].get("fare"):
                    price_usd = int(offer["offerDetails"]["fare"].get("total") / EXCHANGE_RATE["ARS_USD"])
                    ida_map[offer.get("departure")] = {"price": price_usd}
                    if price_usd < ONE_WAY_PRICE_THRESHOLD:
                        web_link = f"https://www.aerolineas.com.ar/flights-offers?adt=1&inf=0&chd=0&flexDates=false&cabinClass=Economy&flightType=ONE_WAY&leg=BUE-{dest['code']}-{offer.get('departure').replace('-', '')}"
                        save_flight({"date": offer.get("departure"), "price": price_usd, "destination": dest["code"], "webLink": web_link, "totalPrice": price_usd, "airline": "Aerolíneas Argentinas", "flight_type": "ONE_WAY"})
                        send_telegram(f"✈️ <b>Aerolíneas Argentinas</b> | {dest['name']}\n📅 Ida: <b>{offer.get('departure')}</b>\n💸 Precio solo ida: <b>${price_usd}</b>\n<a href=\"{web_link}\">Link</a>", parse_mode="HTML")

            for offer in offers.get("1", []):
                if offer and isinstance(offer, dict) and not offer.get("soldOut") and isinstance(offer.get("offerDetails"), dict) and offer["offerDetails"].get("fare"):
                    price_usd = int(offer["offerDetails"]["fare"].get("total") / EXCHANGE_RATE["ARS_USD"])
                    vuelta_map[offer.get("departure")] = {"price": price_usd}

            for ida_date, ida_info in ida_map.items():
                d1 = datetime.strptime(ida_date, "%Y-%m-%d")
                vuelta_date = (d1 + timedelta(days=14)).strftime("%Y-%m-%d")
                if vuelta_date in vuelta_map:
                    total_price = ida_info["price"] + vuelta_map[vuelta_date]["price"]
                    if total_price < PRICE_THRESHOLD:
                        key = (ida_date, vuelta_date, total_price)
                        if key in seen:
                            continue
                        seen.add(key)
                        
                        is_real, real_response = validate_real_ticket_aerolineas(token, dest["code"], ida_date, vuelta_date)
                        if is_real:
                            web_link = f"https://www.aerolineas.com.ar/flights-offers?adt=1&inf=0&chd=0&flexDates=false&cabinClass=Economy&flightType=ROUND_TRIP&leg=BUE-{dest['code']}-{d1.strftime('%Y%m%d')}&leg={dest['code']}-BUE-{(d1 + timedelta(days=14)).strftime('%Y%m%d')}"
                            save_flight({"date": ida_date, "price": ida_info["price"], "return_date": vuelta_date, "return_price": vuelta_map[vuelta_date]["price"], "destination": dest["code"], "webLink": web_link, "totalPrice": total_price, "airline": "Aerolíneas Argentinas"})
                            send_telegram(f"✈️ <b>Aerolíneas Argentinas</b> | {dest['name']} (VALIDADO)\n📅 Ida: <b>{ida_date}</b> | Vuelta: <b>{vuelta_date}</b>\n⏳ Duración: <b>14 días</b>\n💸 Ida: <b>${ida_info['price']}</b> | Vuelta: <b>${vuelta_map[vuelta_date]['price']}</b>\n💰 Total: <b>${total_price}</b>\n<a href=\"{web_link}\">Link</a>", parse_mode="HTML")
            d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    performance_metrics["aerolineas_search_time"] = time.time() - aerolineas_start_time
    logging.info("Aerolíneas Argentinas flight search completed.")
    performance_metrics["total_execution_time"] = time.time() - start_time

def main():
    init_db()
    check_flights()

    logging.info("--- Performance Metrics ---")
    for key, value in performance_metrics.items():
        logging.info(f"{key}: {value/60:.2f} minutes")

if __name__ == "__main__":
    main()
