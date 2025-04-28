from typing import Any, Dict, List, Optional, Tuple
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioServerParameters,
    SseServerParams,
)
from contextlib import AsyncExitStack
import os
from src.utils.logger import setup_logger
from src.services.mcp_server_service import get_mcp_server
from sqlalchemy.orm import Session

logger = setup_logger(__name__)

class MCPService:
    def __init__(self):
        self.tools = []
        self.exit_stack = AsyncExitStack()

    async def _connect_to_mcp_server(self, server_config: Dict[str, Any]) -> Tuple[List[Any], Optional[AsyncExitStack]]:
        """Connect to a specific MCP server and return its tools."""
        try:
            # Determines the type of server (local or remote)
            if "url" in server_config:
                # Remote server (SSE)
                connection_params = SseServerParams(
                    url=server_config["url"],
                    headers=server_config.get("headers", {})
                )
            else:
                # Local server (Stdio)
                command = server_config.get("command", "npx")
                args = server_config.get("args", [])
                
                # Adds environment variables if specified
                env = server_config.get("env", {})
                if env:
                    for key, value in env.items():
                        os.environ[key] = value

                connection_params = StdioServerParameters(
                    command=command,
                    args=args,
                    env=env
                )

            tools, exit_stack = await MCPToolset.from_server(
                connection_params=connection_params
            )
            return tools, exit_stack

        except Exception as e:
            logger.error(f"Error connecting to MCP server: {e}")
            return [], None

    def _filter_incompatible_tools(self, tools: List[Any]) -> List[Any]:
        """Filters incompatible tools with the model."""
        problematic_tools = [
            "create_pull_request_review",  # This tool causes the 400 INVALID_ARGUMENT error
        ]

        filtered_tools = []
        removed_count = 0

        for tool in tools:
            if tool.name in problematic_tools:
                logger.warning(f"Removing incompatible tool: {tool.name}")
                removed_count += 1
            else:
                filtered_tools.append(tool)

        if removed_count > 0:
            logger.warning(f"Removed {removed_count} incompatible tools.")

        return filtered_tools
    
    def _filter_tools_by_agent(self, tools: List[Any], agent_tools: List[str]) -> List[Any]:
        """Filters tools compatible with the agent."""
        filtered_tools = []
        for tool in tools:
            logger.info(f"Tool: {tool.name}")
            if tool.name in agent_tools:
                filtered_tools.append(tool)
        return filtered_tools

    async def build_tools(self, mcp_config: Dict[str, Any], db: Session) -> Tuple[List[Any], AsyncExitStack]:
        """Builds a list of tools from multiple MCP servers."""
        self.tools = []
        self.exit_stack = AsyncExitStack()

        # Process each MCP server in the configuration
        for server in mcp_config.get("mcp_servers", []):
            try:
                # Search for the MCP server in the database
                mcp_server = get_mcp_server(db, server['id'])
                if not mcp_server:
                    logger.warning(f"Servidor MCP não encontrado: {server['id']}")
                    continue

                # Prepares the server configuration
                server_config = mcp_server.config_json.copy()
                
                # Replaces the environment variables in the config_json
                if 'env' in server_config:
                    for key, value in server_config['env'].items():
                        if value.startswith('env@@'):
                            env_key = value.replace('env@@', '')
                            if env_key in server.get('envs', {}):
                                server_config['env'][key] = server['envs'][env_key]
                            else:
                                logger.warning(f"Environment variable '{env_key}' not provided for the MCP server {mcp_server.name}")
                                continue

                logger.info(f"Connecting to MCP server: {mcp_server.name}")
                tools, exit_stack = await self._connect_to_mcp_server(server_config)

                if tools and exit_stack:
                    # Filters incompatible tools
                    filtered_tools = self._filter_incompatible_tools(tools)
                    
                    # Filters tools compatible with the agent
                    agent_tools = server.get('tools', [])
                    filtered_tools = self._filter_tools_by_agent(filtered_tools, agent_tools)
                    self.tools.extend(filtered_tools)
                    
                    # Registers the exit_stack with the AsyncExitStack
                    await self.exit_stack.enter_async_context(exit_stack)
                    logger.info(f"Connected successfully. Added {len(filtered_tools)} tools.")
                else:
                    logger.warning(f"Failed to connect or no tools available for {mcp_server.name}")

            except Exception as e:
                logger.error(f"Error connecting to MCP server {server['id']}: {e}")
                continue

        logger.info(f"MCP Toolset created successfully. Total of {len(self.tools)} tools.")

        return self.tools, self.exit_stack 