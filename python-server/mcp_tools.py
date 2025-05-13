# mcp_tools.py
import json
import asyncio
import traceback
from mcp import StdioServerParameters, ClientSession
from mcp.client.stdio import stdio_client

# Dictionary to store server parameters for different MCP tools
MCP_SERVER_PARAMS = {
    "location": StdioServerParameters(
        command="uvx",
        args=["awslabs.aws_location_server@latest"],
        env={
            "AWS_PROFILE": "nova",
            "AWS_REGION": "us-east-1",
            "FASTMCP_LOG_LEVEL": "ERROR"
        }
    )
    # Add more server parameters here as needed
    # "another_tool": StdioServerParameters(...)
}

async def invoke_mcp_tool(server_name, tool_name, arguments):
    """
    Generic function to invoke any MCP tool
    
    Args:
        server_name: Name of the MCP server (key in MCP_SERVER_PARAMS)
        tool_name: Name of the tool to invoke
        arguments: Dictionary of arguments to pass to the tool
        
    Returns:
        The result from the MCP tool
    """
    if server_name not in MCP_SERVER_PARAMS:
        return {"error": f"Unknown MCP server: {server_name}"}
    
    server_params = MCP_SERVER_PARAMS[server_name]
    
    try:
        print(f"Creating MCP client connection for {server_name}...")
        async with stdio_client(server_params) as (read, write):
            print(f"Initializing client session...")
            async with ClientSession(read, write) as session:
                await session.initialize()
                print(f"Invoking tool {tool_name} with arguments: {arguments}")
                result = await session.call_tool(tool_name, arguments)
                print(f"Tool invocation successful, result: {result}")
                
                # Extract the actual data from the CallToolResult object
                if hasattr(result, 'content') and result.content:
                    # If there's text content, parse it as JSON
                    for content_item in result.content:
                        if content_item.type == 'text':
                            try:
                                return json.loads(content_item.text)
                            except json.JSONDecodeError:
                                return {"text": content_item.text}
                
                # Fallback if we can't extract structured data
                return {"result": str(result)}
    except Exception as e:
        print(f"Error invoking MCP tool {server_name}.{tool_name}: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return {"error": str(e)}

# Convenience function for location tools (for backward compatibility)
async def invoke_location_mcp(tool_name, arguments):
    """
    Invoke a tool from the AWS Location MCP server
    
    Args:
        tool_name: Name of the tool to invoke (e.g., 'search_places')
        arguments: Dictionary of arguments to pass to the tool
        
    Returns:
        The result from the MCP tool
    """
    return await invoke_mcp_tool("location", tool_name, arguments)

async def handle_location_tool_request(query):
    """
    Handle a location tool request from the S2S session manager
    
    Args:
        query: The query from the tool use content
        
    Returns:
        The result from the location tool
    """
    if not query:
        return {"result": "No query provided for location service"}
    
    try:
        # Handle the case where query is already a dictionary
        if isinstance(query, dict):
            query_data = query
        else:
            # Try to parse it as JSON if it's a string
            try:
                query_data = json.loads(query)
            except (json.JSONDecodeError, TypeError):
                return {"result": "Invalid query format for location service"}
        
        # Check if the inner tool is also "locationMcpTool"
        if query_data.get("tool") == "locationMcpTool":
            # The agent is using locationMcpTool as both outer and inner tool
            # We need to use the query parameter to determine which AWS Location tool to use
            query_text = query_data.get("params", {}).get("query", "")
            
            if not query_text:
                return {"result": "No search query provided for location service"}
                
            # Use search_places as the default tool for location queries
            location_tool = "search_places"
            location_params = {"query": query_text}
        else:
            # The agent is specifying a specific AWS Location tool
            location_tool = query_data.get("tool")
            location_params = query_data.get("params", {})
            
            if not location_tool:
                return {"result": "No location tool specified"}
        
        print(f"Invoking AWS Location tool: {location_tool} with params: {location_params}")
        
        # Invoke the appropriate MCP tool
        result = await invoke_location_mcp(location_tool, location_params)
        return {"result": result}
    except Exception as e:
        print(f"Error using location service: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return {"result": f"Error using location service: {str(e)}"}

# Generic handler for tool requests
async def handle_tool_request(tool_name, query):
    """
    Generic handler for tool requests from the S2S session manager
    
    Args:
        tool_name: Name of the tool to use
        query: The query from the tool use content
        
    Returns:
        The result from the tool
    """
    # Map tool names to their handlers
    tool_handlers = {
        "locationMcpTool": handle_location_tool_request,
        # Add more tool handlers here as needed
        # "anotherTool": handle_another_tool_request,
    }
    
    if tool_name in tool_handlers:
        return await tool_handlers[tool_name](query)
    else:
        return {"error": f"Unknown tool: {tool_name}"}

async def cleanup():
    """Clean up the MCP client - no longer needed with context managers"""
    pass  # Context managers handle cleanup automatically
