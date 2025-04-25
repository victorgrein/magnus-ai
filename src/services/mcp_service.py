from typing import Any, Dict, List, Optional, Tuple
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioServerParameters,
    SseServerParams,
)
from contextlib import AsyncExitStack
import os
import logging
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class MCPService:
    def __init__(self):
        self.tools = []
        self.exit_stack = AsyncExitStack()

    async def _connect_to_mcp_server(self, server_config: Dict[str, Any]) -> Tuple[List[Any], Optional[AsyncExitStack]]:
        """Conecta a um servidor MCP específico e retorna suas ferramentas."""
        try:
            # Determina o tipo de servidor (local ou remoto)
            if "url" in server_config:
                # Servidor remoto (SSE)
                connection_params = SseServerParams(
                    url=server_config["url"],
                    headers=server_config.get("headers", {})
                )
            else:
                # Servidor local (Stdio)
                command = server_config.get("command", "npx")
                args = server_config.get("args", [])
                
                # Adiciona variáveis de ambiente se especificadas
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
            logger.error(f"Erro ao conectar ao servidor MCP: {e}")
            return [], None

    def _filter_incompatible_tools(self, tools: List[Any]) -> List[Any]:
        """Filtra ferramentas incompatíveis com o modelo."""
        problematic_tools = [
            "create_pull_request_review",  # Esta ferramenta causa o erro 400 INVALID_ARGUMENT
        ]

        filtered_tools = []
        removed_count = 0

        for tool in tools:
            if tool.name in problematic_tools:
                logger.warning(f"Removendo ferramenta incompatível: {tool.name}")
                removed_count += 1
            else:
                filtered_tools.append(tool)

        if removed_count > 0:
            logger.warning(f"Removidas {removed_count} ferramentas incompatíveis.")

        return filtered_tools

    async def build_tools(self, mcp_config: Dict[str, Any]) -> Tuple[List[Any], AsyncExitStack]:
        """Constrói uma lista de ferramentas a partir de múltiplos servidores MCP."""
        self.tools = []
        self.exit_stack = AsyncExitStack()

        # Processa cada servidor MCP da configuração
        for server_name, server_config in mcp_config.get("mcpServers", {}).items():
            logger.info(f"Conectando ao servidor MCP: {server_name}")
            try:
                tools, exit_stack = await self._connect_to_mcp_server(server_config)

                if tools and exit_stack:
                    # Filtra ferramentas incompatíveis
                    filtered_tools = self._filter_incompatible_tools(tools)
                    self.tools.extend(filtered_tools)
                    
                    # Registra o exit_stack com o AsyncExitStack
                    await self.exit_stack.enter_async_context(exit_stack)
                    logger.info(f"Conectado com sucesso. Adicionadas {len(filtered_tools)} ferramentas.")
                else:
                    logger.warning(f"Falha na conexão ou nenhuma ferramenta disponível para {server_name}")

            except Exception as e:
                logger.error(f"Erro ao conectar ao servidor MCP {server_name}: {e}")
                continue

        logger.info(f"MCP Toolset criado com sucesso. Total de {len(self.tools)} ferramentas.")

        return self.tools, self.exit_stack 