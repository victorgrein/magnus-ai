import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Dict, List, Optional, Tuple
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioServerParameters,
    SseServerParams,
)
from google.adk.tools import BaseTool

# Configuração do logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MCPBuilder:
    def __init__(self, mcp_config: Dict):
        """
        Inicializa o MCPBuilder com a configuração dos servidores MCP.
        
        Args:
            mcp_config (Dict): Configuração dos servidores MCP no formato:
                {
                    "mcpServers": {
                        "server_name": {
                            "command": "npx",
                            "args": ["-y", "@modelcontextprotocol/server-name"],
                            "env": {"API_KEY": "value"},
                            "url": "https://server-url/sse",
                            "headers": {"Authorization": "Bearer token"}
                        }
                    }
                }
        """
        self.mcp_config = mcp_config
        self.tools: List[BaseTool] = []
        self.exit_stack = AsyncExitStack()

    async def connect_to_mcp_server(self, server_name: str, server_config: Dict) -> Tuple[List[BaseTool], Optional[AsyncExitStack]]:
        """
        Conecta a um servidor MCP específico e retorna suas ferramentas.
        
        Args:
            server_name (str): Nome do servidor MCP
            server_config (Dict): Configuração do servidor
            
        Returns:
            Tuple[List[BaseTool], Optional[AsyncExitStack]]: Lista de ferramentas e stack de saída
        """
        try:
            # Configura variáveis de ambiente se especificadas
            if "env" in server_config:
                for key, value in server_config["env"].items():
                    import os
                    os.environ[key] = value

            # Determina os parâmetros de conexão baseado na configuração
            if "url" in server_config:
                connection_params = SseServerParams(
                    url=server_config["url"],
                    headers=server_config.get("headers", {})
                )
            else:
                connection_params = StdioServerParameters(
                    command=server_config["command"],
                    args=server_config["args"]
                )

            logger.info(f"Conectando ao servidor MCP: {server_name}")
            tools, exit_stack = await MCPToolset.from_server(
                connection_params=connection_params
            )
            return tools, exit_stack

        except Exception as e:
            logger.error(f"Erro ao conectar ao servidor MCP {server_name}: {str(e)}")
            return [], None

    async def build(self) -> Tuple[List[BaseTool], AsyncExitStack]:
        """
        Constrói a lista de ferramentas MCP a partir da configuração.
        
        Returns:
            Tuple[List[BaseTool], AsyncExitStack]: Lista de ferramentas e stack de saída
        """
        self.tools = []
        self.exit_stack = AsyncExitStack()

        if "mcpServers" not in self.mcp_config:
            logger.warning("Nenhuma configuração de servidor MCP encontrada")
            return [], self.exit_stack

        for server_name, server_config in self.mcp_config["mcpServers"].items():
            try:
                tools, exit_stack = await self.connect_to_mcp_server(server_name, server_config)

                if tools and exit_stack:
                    # Filtrar ferramentas incompatíveis antes de adicionar
                    filtered_tools = self.filter_incompatible_tools(tools)
                    self.tools.extend(filtered_tools)
                    
                    # Registrar o exit_stack com o AsyncExitStack
                    await self.exit_stack.enter_async_context(exit_stack)
                    logger.info(
                        f"Conectado com sucesso ao servidor {server_name}. "
                        f"Adicionadas {len(filtered_tools)} de {len(tools)} ferramentas."
                    )
                else:
                    logger.warning(f"Falha na conexão ou nenhuma ferramenta disponível para o servidor {server_name}")
            except Exception as e:
                logger.error(f"Erro ao conectar ao servidor MCP {server_name}: {str(e)}")
                continue

        logger.info(f"MCP Toolset criado com sucesso. Total de {len(self.tools)} ferramentas.")
        return self.tools, self.exit_stack 