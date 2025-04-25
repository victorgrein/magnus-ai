import asyncio
from src.services.agent_builder import AgentBuilder
from src.services.mcp_builder import MCPBuilder

async def main():
    # Configuração dos servidores MCP
    mcp_config = {
        "brave-search": {
            "url": "http://localhost:8000",
            "headers": {
                "Authorization": "Bearer seu_token_aqui"
            }
        },
        "google-calendar-mcp": {
            "url": "http://localhost:8001",
            "headers": {
                "Authorization": "Bearer seu_token_aqui"
            }
        }
    }

    # Configuração do agente
    agent_config = {
        "model": "gemini-pro",
        "name": "Agente de Pesquisa",
        "description": "Agente especializado em pesquisas e agendamentos",
        "instruction": "Use as ferramentas disponíveis para realizar pesquisas e agendamentos",
        "tools": {
            "custom_tool": {
                "type": "search",
                "config": {
                    "api_key": "sua_chave_aqui"
                }
            }
        }
    }

    # Cria o builder
    builder = AgentBuilder(None)  # None pois não estamos usando banco de dados neste exemplo
    builder.set_mcp_config(mcp_config)

    # Constrói o agente
    agent, exit_stack = await builder.build_agent(agent_config)

    try:
        # Usa o agente
        response = await agent.run("Pesquise sobre inteligência artificial")
        print(response)
    finally:
        # Limpa os recursos
        await exit_stack.aclose()

if __name__ == "__main__":
    asyncio.run(main()) 