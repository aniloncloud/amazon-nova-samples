# inline_agent_mcp.py
import asyncio
import json
from mcp import StdioServerParameters
from InlineAgent.tools import MCPStdio
from InlineAgent.action_group import ActionGroup
from InlineAgent.agent import InlineAgent

# Import config from mcp_clients.py
from mcp_clients import config

class InlineAgentMCP:
    def __init__(self):
        self.initialized = False
    
    async def invoke(self, query):
        """Invoke InlineAgent with the given query."""
        try:
            # Create MCP clients for this invocation
            time_mcp_client = await MCPStdio.create(
                server_params=StdioServerParameters(
                    command="finch",
                    args=["run", "-i", "--rm", "mcp/time"],
                )
            )
            
            perplexity_mcp_client = await MCPStdio.create(
                server_params=StdioServerParameters(
                    command="finch",
                    args=["run", "-i", "--rm", "-e", "PERPLEXITY_API_KEY", "mcp/perplexity-ask"],
                    env={"PERPLEXITY_API_KEY": config.PERPLEXITY_API_KEY},
                )
            )
            
            cost_mcp_client = await MCPStdio.create(
                server_params=StdioServerParameters(
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
            )
            
            location_mcp_client = await MCPStdio.create(
                server_params=StdioServerParameters(
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
            )
            
            # Define action groups
            time_action_group = ActionGroup(
                name="TimeActionGroup",
                description="Helps user get current time and convert time.",
                mcp_clients=[time_mcp_client],
            )

            perplexity_action_group = ActionGroup(
                name="SearchActionGroup",
                description="Helps user search for information using Perplexity.",
                mcp_clients=[perplexity_mcp_client],
            )
            
            cost_action_group = ActionGroup(
                name="CostExplorerActionGroup",
                description="Helps user analyze AWS costs and usage.",
                mcp_clients=[cost_mcp_client],
            )
            
            location_action_group = ActionGroup(
                name="LocationActionGroup",
                description="Helps user with location-based services like searching places and getting coordinates.",
                mcp_clients=[location_mcp_client],
            )
            
            try:
                # Invoke agent
                result = await InlineAgent(
                    # Provide the model
                    foundation_model="amazon.nova-micro-v1:0",
                    # Concise instruction
                    instruction="""You are a helpful assistant that resolves user queries. 
                    You can help with time conversion, search for information, analyze AWS costs, and provide location-based services.""",
                    # Provide the agent name and action groups
                    agent_name="s2s_mcp_agent",
                    action_groups=[
                        time_action_group, 
                        perplexity_action_group, 
                        cost_action_group,
                        location_action_group
                    ],
                ).invoke(input_text=query)
                
                return result
            finally:
                # Clean up MCP clients
                try:
                    await location_mcp_client.cleanup()
                except Exception as e:
                    print(f"Error cleaning up location MCP client: {str(e)}")
                
                try:
                    await cost_mcp_client.cleanup()
                except Exception as e:
                    print(f"Error cleaning up cost MCP client: {str(e)}")
                
                try:
                    await perplexity_mcp_client.cleanup()
                except Exception as e:
                    print(f"Error cleaning up perplexity MCP client: {str(e)}")
                
                try:
                    await time_mcp_client.cleanup()
                except Exception as e:
                    print(f"Error cleaning up time MCP client: {str(e)}")
        except Exception as e:
            print(f"Error invoking InlineAgent: {str(e)}")
            return {"error": str(e)}

# Create a singleton instance
inline_agent = InlineAgentMCP()

async def invoke_agent(query):
    """Helper function to invoke the agent."""
    return await inline_agent.invoke(query)

async def cleanup_agent():
    """Placeholder for compatibility."""
    pass
