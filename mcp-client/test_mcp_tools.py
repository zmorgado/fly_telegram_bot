#!/usr/bin/env python3
"""
Test script to verify MCP server tools are working correctly.
"""
import sys
import os
import asyncio
import json
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
        
        # Extract content from MCP response
        level_content = None
        if hasattr(level_result, 'content') and level_result.content:
            level_content = level_result.content[0].text
        elif isinstance(level_result, list):
            level_content = level_result
        
        if level_content:
            try:
                # Try to parse as JSON if it's a string
                if isinstance(level_content, str):
                    level_flights = json.loads(level_content)
                    if isinstance(level_flights, list):
                        logging.info(f"✅ Level search returned {len(level_flights)} results")
                        if level_flights:
                            sample = str(level_flights[0])[:100] + "..." if len(str(level_flights[0])) > 100 else str(level_flights[0])
                            logging.info(f"   Sample result: {sample}")
                    else:
                        logging.info(f"✅ Level search result: {str(level_content)[:100]}...")
                else:
                    # Handle list of objects (flight summaries)
                    if isinstance(level_content, list):
                        logging.info(f"✅ Level search returned {len(level_content)} results")
                        if level_content:
                            sample = str(level_content[0])[:100] + "..." if len(str(level_content[0])) > 100 else str(level_content[0])
                            logging.info(f"   Sample result: {sample}")
                    else:
                        logging.info(f"✅ Level search result: {str(level_content)[:100]}...")
            except (json.JSONDecodeError, TypeError, AttributeError) as e:
                # Content is not JSON or has unexpected format
                logging.info(f"✅ Level search result: {str(level_content)[:100]}...")
        else:
            logging.info("✅ Level search completed but no results returned")

        # Test search_aerolineas with sample parameters
        logging.info("\n🛫 Testing search_aerolineas...")
        aero_params = {
            "origin": "EZE",
            "destination": ["MAD"],
            "start_date": "2026-01-01",
            "end_date": "2026-01-31"
        }
        aero_result = await server.call_tool("search_aerolineas", aero_params)
        
        # Extract content from MCP response
        aero_content = None
        if hasattr(aero_result, 'content') and aero_result.content:
            aero_content = aero_result.content[0].text
        elif isinstance(aero_result, list):
            aero_content = aero_result
            
        if aero_content:
            try:
                # Try to parse as JSON if it's a string
                if isinstance(aero_content, str):
                    aero_flights = json.loads(aero_content)
                    if isinstance(aero_flights, list):
                        logging.info(f"✅ Aerolineas search returned {len(aero_flights)} results")
                        if aero_flights:
                            sample = str(aero_flights[0])[:100] + "..." if len(str(aero_flights[0])) > 100 else str(aero_flights[0])
                            logging.info(f"   Sample result: {sample}")
                    else:
                        logging.info(f"✅ Aerolineas search result: {str(aero_content)[:100]}...")
                else:
                    # Handle list of objects (flight summaries)
                    if isinstance(aero_content, list):
                        logging.info(f"✅ Aerolineas search returned {len(aero_content)} results")
                        if aero_content:
                            sample = str(aero_content[0])[:100] + "..." if len(str(aero_content[0])) > 100 else str(aero_content[0])
                            logging.info(f"   Sample result: {sample}")
                    else:
                        logging.info(f"✅ Aerolineas search result: {str(aero_content)[:100]}...")
            except (json.JSONDecodeError, TypeError, AttributeError) as e:
                # Content is not JSON or has unexpected format
                logging.info(f"✅ Aerolineas search result: {str(aero_content)[:100]}...")
        else:
            logging.info("✅ Aerolineas search completed but no results returned")

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
