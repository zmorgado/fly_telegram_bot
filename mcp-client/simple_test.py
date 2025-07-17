#!/usr/bin/env python3
"""
Simple test script to verify MCP server tools are working correctly.
"""
import sys
import os
import asyncio
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
logging.basicConfig(level=logging.INFO)
logging.getLogger("seleniumwire").setLevel(logging.WARNING)

from mcp_flight_server import server

async def test_tools():
    """Test all MCP server tools."""
    logging.info("🧪 Testing MCP Flight Server Tools...")

    try:
        # Test flight_stats_summary (no parameters needed)
        logging.info("\n📊 Testing flight_stats_summary...")
        stats_result = await server.call_tool("flight_stats_summary", {})
        logging.info(f"✅ Stats result: {stats_result}")
        
        # Test search_level with sample parameters
        logging.info("\n✈️ Testing search_level...")
        level_params = {
            "origin": "EZE",
            "destination": ["MAD"],
            "start_date": "2026-01-01", 
            "end_date": "2026-01-31"
        }
        level_result = await server.call_tool("search_level", level_params)
        logging.info(f"✅ Level search completed successfully")
        logging.info(f"   Result type: {type(level_result)}")
        
        # Test search_aerolineas with sample parameters  
        logging.info("\n🛫 Testing search_aerolineas...")
        aero_params = {
            "origin": "EZE",
            "destination": ["MAD"],
            "start_date": "2026-01-01",
            "end_date": "2026-01-31"
        }
        aero_result = await server.call_tool("search_aerolineas", aero_params)
        logging.info(f"✅ Aerolineas search completed successfully")
        logging.info(f"   Result type: {type(aero_result)}")

        logging.info("\n🎉 All tools tested successfully!")
        return True
        
    except Exception as e:
        logging.error(f"❌ Error testing tools: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_tools())
    if success:
        logging.info("\n✅ MCP Server is ready for Claude for Desktop integration!")
    else:
        logging.error("\n❌ MCP Server has issues that need to be resolved.")
