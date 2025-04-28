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
from src.services.mcp_server_service import get_mcp_server
from sqlalchemy.orm import Session

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
    
    def _filter_tools_by_agent(self, tools: List[Any], agent_tools: List[str]) -> List[Any]:
        """Filtra ferramentas compatíveis com o agente."""
        filtered_tools = []
        for tool in tools:
            logger.info(f"Ferramenta: {tool.name}")
            if tool.name in agent_tools:
                filtered_tools.append(tool)
        return filtered_tools

    async def build_tools(self, mcp_config: Dict[str, Any], db: Session) -> Tuple[List[Any], AsyncExitStack]:
        """Constrói uma lista de ferramentas a partir de múltiplos servidores MCP."""
        self.tools = []
        self.exit_stack = AsyncExitStack()

        # Processa cada servidor MCP da configuração
        for server in mcp_config.get("mcp_servers", []):
            try:
                # Busca o servidor MCP no banco
                mcp_server = get_mcp_server(db, server['id'])
                if not mcp_server:
                    logger.warning(f"Servidor MCP não encontrado: {server['id']}")
                    continue

                # Prepara a configuração do servidor
                server_config = mcp_server.config_json.copy()
                
                # Substitui as variáveis de ambiente no config_json
                if 'env' in server_config:
                    for key, value in server_config['env'].items():
                        if value.startswith('env@@'):
                            env_key = value.replace('env@@', '')
                            if env_key in server.get('envs', {}):
                                server_config['env'][key] = server['envs'][env_key]
                            else:
                                logger.warning(f"Variável de ambiente '{env_key}' não fornecida para o servidor MCP {mcp_server.name}")
                                continue

                logger.info(f"Conectando ao servidor MCP: {mcp_server.name}")
                tools, exit_stack = await self._connect_to_mcp_server(server_config)

                if tools and exit_stack:
                    # Filtra ferramentas incompatíveis
                    filtered_tools = self._filter_incompatible_tools(tools)
                    
                    # Filtra ferramentas compatíveis com o agente
                    agent_tools = server.get('tools', [])
                    filtered_tools = self._filter_tools_by_agent(filtered_tools, agent_tools)
                    self.tools.extend(filtered_tools)
                    
                    # Registra o exit_stack com o AsyncExitStack
                    await self.exit_stack.enter_async_context(exit_stack)
                    logger.info(f"Conectado com sucesso. Adicionadas {len(filtered_tools)} ferramentas.")
                else:
                    logger.warning(f"Falha na conexão ou nenhuma ferramenta disponível para {mcp_server.name}")

            except Exception as e:
                logger.error(f"Erro ao conectar ao servidor MCP {server['id']}: {e}")
                continue

        logger.info(f"MCP Toolset criado com sucesso. Total de {len(self.tools)} ferramentas.")

        return self.tools, self.exit_stack 