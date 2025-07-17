

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from mcp.server.fastmcp import FastMCP
from search_providers.aerolineas import AerolineasProvider
from search_providers.level import LevelProvider
import stats
import asyncio

def format_flight(flight):
    if not flight:
        return "No flight found."
    return (
        f"{flight.get('airline', 'Unknown airline')} | "
        f"{flight.get('destination', '')} | "
        f"Departure: {flight.get('date', '')}"
        + (f" | Return: {flight.get('return_date', '')}" if 'return_date' in flight else "")
        + f" | Price: ${flight.get('totalPrice', 'N/A')}"
        + (f" | Link: {flight.get('webLink', '')}" if 'webLink' in flight else "")
    )

def get_flight_summaries(provider, origin, destination, start_date, end_date):
    """Query a provider and return a list of formatted flight summaries."""
    results = provider.search_flights(origin, destination, start_date, end_date)
    return [format_flight(f) for f in results]

def get_stats_summary():
    level = stats.get_level_flights()
    aerolineas = stats.get_aerolineas_flights()
    all_flights = level + aerolineas
    if not all_flights:
        return "No stats available."
    best = min(all_flights, key=lambda f: f.get("totalPrice", float("inf")))
    return f"Best deal: {format_flight(best)}"

server = FastMCP("Flight Search Server")

@server.tool()
async def search_aerolineas(origin: str, destination: list, start_date: str, end_date: str):
    """Search flights using Aerolineas provider."""
    provider = AerolineasProvider()
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, get_flight_summaries, provider, origin, destination, start_date, end_date)
    return results

@server.tool()
async def search_level(origin: str, destination: list, start_date: str, end_date: str):
    """Search flights using Level provider."""
    provider = LevelProvider()
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, get_flight_summaries, provider, origin, destination, start_date, end_date)
    return results

@server.tool()
async def flight_stats_summary():
    """Get a summary of flight search statistics (best deal)."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, get_stats_summary)
    return result

if __name__ == "__main__":
    server.run(transport='stdio')
# {
#   "mcpServers": {
#     "telegram-bot-pasajes": {
#       "command": "uv",
#       "args": [
#         "--directory",
#         "/Users/esemb/Desktop/code/telegram-bot-pasajes/mcp-client",
#         "run",
#         "mcp_flight_server.py"
#       ]
#     }
#   }
# }