# mcp_integration.py
import asyncio
import json
from mcp import StdioServerParameters
from InlineAgent.tools import MCPStdio

# Import config from mcp_clients.py
from mcp_clients import config

class LocationServicesMCP:
    def __init__(self):
        self.mcp_client = None
        self.initialized = False
        
        # Define server parameters
        self.server_params = StdioServerParameters(
            command="/Users/anilnadi/Documents/G/mcp/src/aws-location-mcp-server/.venv/bin/python",
            args=[
                "-m",
                "awslabs.aws_location_server.server"
            ],
            env={
                "AWS_PROFILE": "nova",
                "AWS_REGION": "us-east-1",
                "FASTMCP_LOG_LEVEL": "ERROR"
            },
        )
    
    async def initialize(self):
        """Initialize the MCP client."""
        if self.initialized:
            return True
            
        try:
            self.mcp_client = await MCPStdio.create(server_params=self.server_params)
            self.initialized = True
            return True
        except Exception as e:
            print(f"Failed to initialize location services MCP client: {str(e)}")
            return False
    
    async def search_places(self, query, max_results=5):
        """Search for places using AWS Location Service."""
        if not self.initialized:
            await self.initialize()
        
        try:
            result = await self.mcp_client.call_tool(
                "search_places", 
                {
                    "query": query,
                    "max_results": max_results
                }
            )
            return result
        except Exception as e:
            print(f"Error searching places: {str(e)}")
            return {"error": str(e)}
    
    async def get_coordinates(self, location):
        """Get coordinates for a location."""
        if not self.initialized:
            await self.initialize()
        
        try:
            result = await self.mcp_client.call_tool(
                "get_coordinates", 
                {
                    "location": location
                }
            )
            return result
        except Exception as e:
            print(f"Error getting coordinates: {str(e)}")
            return {"error": str(e)}
    
    async def cleanup(self):
        """Clean up the MCP client."""
        if not self.initialized:
            return
            
        try:
            if self.mcp_client:
                await self.mcp_client.cleanup()
        except Exception as e:
            print(f"Error cleaning up location services MCP client: {str(e)}")
        finally:
            self.initialized = False

# Create a singleton instance
location_services = LocationServicesMCP()

async def search_places(query, max_results=5):
    """Helper function to search for places."""
    try:
        result = await location_services.search_places(query, max_results)
        return result
    finally:
        await location_services.cleanup()

async def get_coordinates(location):
    """Helper function to get coordinates for a location."""
    try:
        result = await location_services.get_coordinates(location)
        return result
    finally:
        await location_services.cleanup()

# Example usage:
# async def main():
#     places = await search_places("Home Depot in Princeton, New Jersey")
#     print(json.dumps(places, indent=2))
#     
#     coordinates = await get_coordinates("Princeton University")
#     print(json.dumps(coordinates, indent=2))
# 
# if __name__ == "__main__":
#     asyncio.run(main())
