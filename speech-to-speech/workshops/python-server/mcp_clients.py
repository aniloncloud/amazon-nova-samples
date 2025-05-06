# mcp_clients.py
import asyncio
from dotenv import load_dotenv
import os
import json
from mcp import StdioServerParameters
from InlineAgent.tools import MCPStdio

# Load environment variables
load_dotenv()

class AgentConfig:
    def __init__(self):
        self.AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
        self.AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
        self.BEDROCK_LOG_GROUP_NAME = os.getenv("BEDROCK_LOG_GROUP_NAME")
        self.PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

# Initialize config
config = AgentConfig()

class MCPClientManager:
    def __init__(self):
        self.time_mcp_client = None
        self.perplexity_mcp_client = None
        self.cost_mcp_client = None
        self.location_mcp_client = None
        self.initialized = False
        
        # Define MCP server parameters
        self.time_server_params = StdioServerParameters(
            command="finch",
            args=["run", "-i", "--rm", "mcp/time"],
        )

        self.perplexity_server_params = StdioServerParameters(
            command="finch",
            args=["run", "-i", "--rm", "-e", "PERPLEXITY_API_KEY", "mcp/perplexity-ask"],
            env={"PERPLEXITY_API_KEY": config.PERPLEXITY_API_KEY},
        )

        self.cost_server_params = StdioServerParameters(
            command="finch",
            args=[
                "run",
                "-i",
                "--rm",
                "-e",
                "AWS_ACCESS_KEY_ID",
                "-e",
                "AWS_SECRET_ACCESS_KEY",
                "-e",
                "AWS_REGION",
                "-e",
                "BEDROCK_LOG_GROUP_NAME",
                "-e",
                "stdio",
                "aws-cost-explorer-mcp:latest",
            ],
            env={
                "AWS_ACCESS_KEY_ID": config.AWS_ACCESS_KEY_ID,
                "AWS_SECRET_ACCESS_KEY": config.AWS_SECRET_ACCESS_KEY,
                "AWS_REGION": config.AWS_REGION,
                "BEDROCK_LOG_GROUP_NAME": config.BEDROCK_LOG_GROUP_NAME,
            },
        )

        self.location_server_params = StdioServerParameters(
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
        """Initialize MCP clients."""
        if self.initialized:
            return True
            
        try:
            # Create MCP clients
            self.time_mcp_client = await MCPStdio.create(server_params=self.time_server_params)
            self.perplexity_mcp_client = await MCPStdio.create(server_params=self.perplexity_server_params)
            self.cost_mcp_client = await MCPStdio.create(server_params=self.cost_server_params)
            self.location_mcp_client = await MCPStdio.create(server_params=self.location_server_params)
            
            self.initialized = True
            return True
        except Exception as e:
            print(f"Failed to initialize MCP clients: {str(e)}")
            return False
    
    async def cleanup(self):
        """Clean up MCP clients."""
        if not self.initialized:
            return
            
        # Clean up MCP clients in LIFO order
        try:
            if self.location_mcp_client:
                try:
                    await self.location_mcp_client.cleanup()
                except Exception as e:
                    print(f"Error cleaning up location MCP client: {str(e)}")
                    
            if self.cost_mcp_client:
                try:
                    await self.cost_mcp_client.cleanup()
                except Exception as e:
                    print(f"Error cleaning up cost MCP client: {str(e)}")
                    
            if self.perplexity_mcp_client:
                try:
                    await self.perplexity_mcp_client.cleanup()
                except Exception as e:
                    print(f"Error cleaning up perplexity MCP client: {str(e)}")
                    
            if self.time_mcp_client:
                try:
                    await self.time_mcp_client.cleanup()
                except Exception as e:
                    print(f"Error cleaning up time MCP client: {str(e)}")
        except Exception as e:
            print(f"Error during MCP client cleanup: {str(e)}")
        finally:
            self.initialized = False
    
    def get_client_by_id(self, server_id):
        """Get an MCP client by its identifier."""
        server_id = server_id.lower()
        
        # Map of server identifiers to clients
        client_map = {
            'time': self.time_mcp_client,
            'perplexity-ask': self.perplexity_mcp_client,
            'aws-cost-explorer-mcp': self.cost_mcp_client,
            'location-services-mcp': self.location_mcp_client
        }
        
        # Find the matching client
        for key, client in client_map.items():
            if key in server_id:
                return client
        
        return None

# Create a singleton instance
mcp_client_manager = MCPClientManager()
