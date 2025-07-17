import logging
import time
from db import init_db, save_flight
from telegram_utils import send_telegram
from config import REGIONS
from importlib import import_module

logging.basicConfig(level=logging.INFO)
logging.getLogger("seleniumwire").setLevel(logging.WARNING)

performance_metrics = {}

def load_provider_class(provider_name):
    module = import_module(f"search_providers.{provider_name}")
    class_name = provider_name.capitalize() + "Provider"
    return getattr(module, class_name)

def run_region_search(region_name, region_config):
    logging.info(f"Starting flight search for region: {region_name}")
    start_time = time.time()
    for provider_name in region_config["providers"]:
        ProviderClass = load_provider_class(provider_name)
        provider = ProviderClass()
        logging.info(f"  Using provider: {provider_name}")
        thresholds = region_config["thresholds"]
        # Pass notify threshold to AerolineasProvider for efficient validation
        if provider_name == "aerolineas":
            results = provider.search_flights(
                origin=None,
                destination=region_config["destinations"],
                start_date=region_config["date_range"][0],
                end_date=region_config["date_range"][1],
                notify_threshold=thresholds["notify"]
            )
        else:
            results = provider.search_flights(
                origin=None,
                destination=region_config["destinations"],
                start_date=region_config["date_range"][0],
                end_date=region_config["date_range"][1]
            )

        # Buscar la mejor combinación para round trip y one way
        best_one_way = None
        best_one_way_price = float('inf')
        best_round_trip = None
        best_round_trip_price = float('inf')
        for flight in results:
            if flight.get("flight_type") == "ONE_WAY":
                if flight["totalPrice"] < best_one_way_price:
                    best_one_way = flight
                    best_one_way_price = flight["totalPrice"]
            else:
                if flight["totalPrice"] < best_round_trip_price:
                    best_round_trip = flight
                    best_round_trip_price = flight["totalPrice"]

        if best_one_way:
            logging.info(
                "[BEST ONE WAY] Region: %s | Provider: %s | Date: %s | Dest: %s | Price: $%s USD | Link: %s",
                region_name,
                provider_name,
                best_one_way.get('date'),
                best_one_way.get('destination'),
                best_one_way.get('totalPrice'),
                best_one_way.get('webLink')
            )
        else:
            logging.info(
                "[BEST ONE WAY] Region: %s | Provider: %s | No results found.",
                region_name,
                provider_name
            )

        if best_round_trip:
            logging.info(
                "[BEST ROUND TRIP] Region: %s | Provider: %s | Date: %s | Dest: %s | Price: $%s USD | Link: %s",
                region_name,
                provider_name,
                best_round_trip.get('date'),
                best_round_trip.get('destination'),
                best_round_trip.get('totalPrice'),
                best_round_trip.get('webLink')
            )
        else:
            logging.info(
                "[BEST ROUND TRIP] Region: %s | Provider: %s | No results found.",
                region_name,
                provider_name
            )

        # Normalize and process results
        for flight in results:
            # Apply region-specific thresholds
            if flight.get("flight_type") == "ONE_WAY":
                if flight["totalPrice"] < thresholds["one_way"]:
                    save_flight(flight)
                    send_telegram(flight["message"], parse_mode="HTML")
            else:
                if flight["totalPrice"] < thresholds["notify"]:
                    save_flight(flight)
                    send_telegram(flight["message"], parse_mode="HTML")
    performance_metrics[f"{region_name}_search_time"] = time.time() - start_time
    logging.info("Flight search for region %s completed.", region_name)

def main():
    init_db()
    for region_name, region_config in REGIONS.items():
        run_region_search(region_name, region_config)
    logging.info("--- Performance Metrics ---")
    for key, value in performance_metrics.items():
        logging.info("%s: %.2f minutes", key, value/60)

if __name__ == "__main__":
    main()

def check_flights():
    start_time = time.time()
    logging.info("Starting flight search for Level...")
    level_start_time = time.time()
    # ...existing code...
