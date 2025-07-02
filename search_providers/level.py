from .base_provider import BaseProvider
import requests
from datetime import datetime, timedelta

EXCHANGE_RATE = {"EUR_USD": 1.17}

class LevelProvider(BaseProvider):
    def search_flights(self, origin, destination, start_date, end_date):
        results = []
        # destination is a list of airport codes (e.g., ["MAD", "BCN"])
        for dest_code in destination:
            day_price_map = {}
            d = datetime.strptime(start_date, "%Y-%m-%d").replace(day=1)
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            while d <= end_dt:
                api_url = f"https://www.flylevel.com/nwe/flights/api/calendar/?triptype=RT&origin=EZE&destination={dest_code}&month={d.month:02d}&year={d.year}&currencyCode=USD"
                try:
                    res = requests.get(api_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                    res.raise_for_status()
                    for day in res.json().get("data", {}).get("dayPrices", []):
                        if day.get("price") is not None:
                            if (day["date"] not in day_price_map) or (day["price"] < day_price_map[day["date"]]["price"]):
                                day_price_map[day["date"]] = day
                except Exception:
                    continue
                d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)

            unique_days = sorted(day_price_map.values(), key=lambda x: x["date"])
            for i, outbound in enumerate(unique_days):
                outbound_date = datetime.strptime(outbound["date"], "%Y-%m-%d")
                if not (datetime.strptime(start_date, "%Y-%m-%d") <= outbound_date <= end_dt):
                    continue

                # One-way
                if outbound["price"] is not None:
                    price_usd = round(outbound["price"] * EXCHANGE_RATE["EUR_USD"], 2)
                    web_link = f"https://www.flylevel.com/Flight/Select?culture=es-ES&triptype=OW&o1=EZE&d1={dest_code}&dd1={outbound['date']}&ADT=1&CHD=0&INL=0&r=false&mm=false&forcedCurrency=USD&forcedCulture=es-ES&newecom=true&currency=USD"
                    message = f"✈️ <b>Level</b> | {dest_code}\n📅 Ida: <b>{outbound['date']}</b>\n💸 Precio solo ida: <b>${price_usd} USD</b>\n<a href=\"{web_link}\">Link</a>"
                    results.append({
                        "date": outbound["date"],
                        "price": price_usd,
                        "destination": dest_code,
                        "webLink": web_link,
                        "totalPrice": price_usd,
                        "airline": "Level",
                        "flight_type": "ONE_WAY",
                        "message": message
                    })

                # Round-trip (14 days)
                for inbound in unique_days[i+1:]:
                    inbound_date = datetime.strptime(inbound["date"], "%Y-%m-%d")
                    if (inbound_date - outbound_date).days != 14 or inbound_date > end_dt:
                        continue
                    if inbound["price"] is None:
                        continue

                    price_out_usd = round(outbound["price"] * EXCHANGE_RATE["EUR_USD"], 2)
                    price_in_usd = round(inbound["price"] * EXCHANGE_RATE["EUR_USD"], 2)
                    total_price = price_out_usd + price_in_usd
                    web_link = f"https://www.flylevel.com/Flight/Select?culture=es-ES&triptype=RT&o1=EZE&d1={dest_code}&dd1={outbound['date']}&ADT=1&CHD=0&INL=0&r=true&mm=false&dd2={inbound['date']}&forcedCurrency=USD&forcedCulture=es-ES&newecom=true&currency=USD"
                    message = f"✈️ <b>Level</b> | {dest_code}\n📅 Ida: <b>{outbound['date']}</b> | Vuelta: <b>{inbound['date']}</b>\n⏳ Duración: <b>14 días</b>\n💸 Ida: <b>${price_out_usd} USD</b> | Vuelta: <b>${price_in_usd} USD</b>\n💰 Total: <b>${total_price} USD</b>\n<a href=\"{web_link}\">Link</a>"
                    results.append({
                        "date": outbound["date"],
                        "price": price_out_usd,
                        "return_date": inbound["date"],
                        "return_price": price_in_usd,
                        "destination": dest_code,
                        "webLink": web_link,
                        "totalPrice": total_price,
                        "airline": "Level",
                        "flight_type": "ROUND_TRIP",
                        "message": message
                    })
        return results
