# direct_mcp.py
import asyncio
import json
from mcp import StdioServerParameters
from InlineAgent.tools import MCPStdio

# Import config from mcp_clients.py
from mcp_clients import config

async def direct_mcp_call(mcp_request):
    """
    Make a direct call to an MCP server without using InlineAgent.
    
    Args:
        mcp_request: A dictionary containing:
            - server_id: The MCP server identifier
            - tool_name: The tool name to call
            - arguments: Parameters for the tool
    
    Returns:
        The result from the MCP call
    """
    try:
        server_id = mcp_request.get('server_id', '').lower()
        tool_name = mcp_request.get('tool_name', '')
        arguments = mcp_request.get('arguments', {})
        
        # Create a new MCP client for this specific call
        mcp_client = None
        server_params = None
        
        # Select the appropriate server parameters based on server_id
        if 'time' in server_id:
            server_params = StdioServerParameters(
                command="finch",
                args=["run", "-i", "--rm", "mcp/time"],
            )
        elif 'perplexity' in server_id:
            server_params = StdioServerParameters(
                command="finch",
                args=["run", "-i", "--rm", "-e", "PERPLEXITY_API_KEY", "mcp/perplexity-ask"],
                env={"PERPLEXITY_API_KEY": config.PERPLEXITY_API_KEY},
            )
        elif 'cost' in server_id:
            server_params = StdioServerParameters(
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
        elif 'location-services-mcp' in server_id:
            server_params = StdioServerParameters(
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
        
        if not server_params:
            return {"error": f"Unknown MCP server: {server_id}"}
        
        # Create the MCP client
        mcp_client = await MCPStdio.create(server_params=server_params)
        
        try:
            # Call the tool
            result = await mcp_client.call_tool(tool_name, arguments)
            return result
        finally:
            # Clean up the MCP client
            if mcp_client:
                try:
                    await mcp_client.cleanup()
                except Exception as e:
                    print(f"Error cleaning up MCP client: {str(e)}")
    except Exception as e:
        print(f"Error in direct MCP call: {str(e)}")
        return {"error": str(e)}

# No need for a cleanup function since we clean up after each call
async def cleanup():
    """Placeholder for compatibility."""
    pass
