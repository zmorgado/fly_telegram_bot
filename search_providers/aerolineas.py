from .base_provider import BaseProvider
import requests
from datetime import datetime, timedelta
from get_aerolineas_token import get_token_with_selenium_wire

EXCHANGE_RATE = {"ARS_USD": 1200}

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
    except Exception:
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
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        data = res.json()
        if data.get("calendarOffers", {}).get("0") and data.get("calendarOffers", {}).get("1"):
            return True
        if data.get("offers"):
            return True
    except Exception:
        pass
    return False

class AerolineasProvider(BaseProvider):
    def search_flights(self, origin, destination, start_date, end_date, notify_threshold=None):
        results = []
        token = get_token_with_selenium_wire()
        if not token:
            return results
        # If notify_threshold is not provided, use a high value to avoid validation
        if notify_threshold is None:
            notify_threshold = float('inf')
        for dest_code in destination:
            d = datetime.strptime(start_date, "%Y-%m-%d").replace(day=1)
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            seen = set()
            while d <= end_dt:
                leg1 = f"BUE-{dest_code}-{d.strftime('%Y%m%d')}"
                leg2 = f"{dest_code}-BUE-{d.strftime('%Y%m%d')}"
                url = f"https://api.aerolineas.com.ar/v1/flights/offers?adt=1&inf=0&chd=0&flexDates=true&cabinClass=Economy&flightType=ROUND_TRIP&leg={leg1}&leg={leg2}"
                offers = get_calendar_offers(token, url)

                ida_map, vuelta_map = {}, {}
                for offer in offers.get("0", []):
                    if offer and isinstance(offer, dict) and not offer.get("soldOut") and isinstance(offer.get("offerDetails"), dict) and offer["offerDetails"].get("fare"):
                        price_usd = int(offer["offerDetails"]["fare"].get("total") / EXCHANGE_RATE["ARS_USD"])
                        ida_map[offer.get("departure")] = {"price": price_usd}
                        web_link = f"https://www.aerolineas.com.ar/flights-offers?adt=1&inf=0&chd=0&flexDates=false&cabinClass=Economy&flightType=ONE_WAY&leg=BUE-{dest_code}-{offer.get('departure').replace('-', '')}"
                        message = f"✈️ <b>Aerolíneas Argentinas</b> | {dest_code}\n📅 Ida: <b>{offer.get('departure')}</b>\n💸 Precio solo ida: <b>${price_usd}</b>\n<a href=\"{web_link}\">Link</a>"
                        results.append({
                            "date": offer.get("departure"),
                            "price": price_usd,
                            "destination": dest_code,
                            "webLink": web_link,
                            "totalPrice": price_usd,
                            "airline": "Aerolíneas Argentinas",
                            "flight_type": "ONE_WAY",
                            "message": message
                        })

                for offer in offers.get("1", []):
                    if offer and isinstance(offer, dict) and not offer.get("soldOut") and isinstance(offer.get("offerDetails"), dict) and offer["offerDetails"].get("fare"):
                        price_usd = int(offer["offerDetails"]["fare"].get("total") / EXCHANGE_RATE["ARS_USD"])
                        vuelta_map[offer.get("departure")] = {"price": price_usd}

                for ida_date, ida_info in ida_map.items():
                    d1 = datetime.strptime(ida_date, "%Y-%m-%d")
                    vuelta_date = (d1 + timedelta(days=14)).strftime("%Y-%m-%d")
                    if vuelta_date in vuelta_map:
                        total_price = ida_info["price"] + vuelta_map[vuelta_date]["price"]
                        key = (ida_date, vuelta_date, total_price)
                        if key in seen:
                            continue
                        seen.add(key)
                        # Only validate if under notify threshold
                        if total_price < notify_threshold:
                            is_real = validate_real_ticket_aerolineas(token, dest_code, ida_date, vuelta_date)
                            if is_real:
                                web_link = f"https://www.aerolineas.com.ar/flights-offers?adt=1&inf=0&chd=0&flexDates=false&cabinClass=Economy&flightType=ROUND_TRIP&leg=BUE-{dest_code}-{d1.strftime('%Y%m%d')}&leg={dest_code}-BUE-{(d1 + timedelta(days=14)).strftime('%Y%m%d')}"
                                message = f"✈️ <b>Aerolíneas Argentinas</b> | {dest_code}{' (VALIDADO)' if total_price < notify_threshold else ''}\n📅 Ida: <b>{ida_date}</b> | Vuelta: <b>{vuelta_date}</b>\n⏳ Duración: <b>14 días</b>\n💸 Ida: <b>${ida_info['price']}</b> | Vuelta: <b>${vuelta_map[vuelta_date]['price']}</b>\n💰 Total: <b>${total_price}</b>\n<a href=\"{web_link}\">Link</a>"
                                results.append({
                                    "date": ida_date,
                                    "price": ida_info["price"],
                                    "return_date": vuelta_date,
                                    "return_price": vuelta_map[vuelta_date]["price"],
                                    "destination": dest_code,
                                    "webLink": web_link,
                                    "totalPrice": total_price,
                                    "airline": "Aerolíneas Argentinas",
                                    "flight_type": "ROUND_TRIP",
                                    "message": message
                            })
                d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        return results
