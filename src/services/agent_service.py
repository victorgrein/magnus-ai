from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status
from src.models.models import Agent
from src.schemas.schemas import AgentCreate
from src.schemas.agent_config import (
    LLMConfig,
    SequentialConfig,
    ParallelConfig,
    LoopConfig,
)
from typing import List, Optional, Dict, Any
from src.services.mcp_server_service import get_mcp_server
import uuid
import logging

logger = logging.getLogger(__name__)


def validate_sub_agents(db: Session, sub_agents: List[uuid.UUID]) -> bool:
    """Valida se todos os sub-agentes existem"""
    for agent_id in sub_agents:
        agent = get_agent(db, agent_id)
        if not agent:
            return False
    return True


def get_agent(db: Session, agent_id: uuid.UUID) -> Optional[Agent]:
    """Busca um agente pelo ID"""
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            logger.warning(f"Agente não encontrado: {agent_id}")
            return None
        return agent
    except SQLAlchemyError as e:
        logger.error(f"Erro ao buscar agente {agent_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar agente",
        )


def get_agents_by_client(
    db: Session,
    client_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
) -> List[Agent]:
    """Busca agentes de um cliente com paginação"""
    try:
        query = db.query(Agent).filter(Agent.client_id == client_id)

        return query.offset(skip).limit(limit).all()
    except SQLAlchemyError as e:
        logger.error(f"Erro ao buscar agentes do cliente {client_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar agentes",
        )


def create_agent(db: Session, agent: AgentCreate) -> Agent:
    """Cria um novo agente"""
    try:
        # Validação adicional de sub-agentes
        if agent.type != "llm":
            if not isinstance(agent.config, dict):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Configuração inválida: deve ser um objeto com sub_agents",
                )

            if "sub_agents" not in agent.config:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Configuração inválida: sub_agents é obrigatório para agentes do tipo sequential, parallel ou loop",
                )

            if not agent.config["sub_agents"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Configuração inválida: sub_agents não pode estar vazio",
                )

            if not validate_sub_agents(db, agent.config["sub_agents"]):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Um ou mais sub-agentes não existem",
                )

        # Processa a configuração antes de criar o agente
        config = agent.config
        if isinstance(config, dict):
            # Processa servidores MCP
            if "mcp_servers" in config:
                processed_servers = []
                for server in config["mcp_servers"]:
                    # Busca o servidor MCP no banco
                    mcp_server = get_mcp_server(db, server["id"])
                    if not mcp_server:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Servidor MCP não encontrado: {server['id']}",
                        )

                    # Verifica se todas as variáveis de ambiente necessárias estão preenchidas
                    for env_key, env_value in mcp_server.environments.items():
                        if env_key not in server.get("envs", {}):
                            raise HTTPException(
                                status_code=400,
                                detail=f"Variável de ambiente '{env_key}' não fornecida para o servidor MCP {mcp_server.name}",
                            )

                    # Adiciona o servidor processado com suas ferramentas
                    processed_servers.append(
                        {
                            "id": str(server["id"]),
                            "envs": server["envs"],
                            "tools": server["tools"],
                        }
                    )

                config["mcp_servers"] = processed_servers

            # Processa sub-agentes
            if "sub_agents" in config:
                config["sub_agents"] = [
                    str(agent_id) for agent_id in config["sub_agents"]
                ]

            # Processa ferramentas
            if "tools" in config:
                config["tools"] = [
                    {"id": str(tool["id"]), "envs": tool["envs"]}
                    for tool in config["tools"]
                ]

            agent.config = config

        db_agent = Agent(**agent.model_dump())
        db.add(db_agent)
        db.commit()
        db.refresh(db_agent)
        logger.info(f"Agente criado com sucesso: {db_agent.id}")
        return db_agent
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao criar agente: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao criar agente",
        )


async def update_agent(
    db: Session, agent_id: uuid.UUID, agent_data: Dict[str, Any]
) -> Agent:
    """Atualiza um agente existente"""
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agente não encontrado")

        # Converte os UUIDs em strings antes de salvar
        if "config" in agent_data:
            config = agent_data["config"]

            # Processa servidores MCP
            if "mcp_servers" in config:
                processed_servers = []
                for server in config["mcp_servers"]:
                    # Busca o servidor MCP no banco
                    mcp_server = get_mcp_server(db, server["id"])
                    if not mcp_server:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Servidor MCP não encontrado: {server['id']}",
                        )

                    # Verifica se todas as variáveis de ambiente necessárias estão preenchidas
                    for env_key, env_value in mcp_server.environments.items():
                        if env_key not in server.get("envs", {}):
                            raise HTTPException(
                                status_code=400,
                                detail=f"Variável de ambiente '{env_key}' não fornecida para o servidor MCP {mcp_server.name}",
                            )

                    # Adiciona o servidor processado
                    processed_servers.append(
                        {
                            "id": str(server["id"]),
                            "envs": server["envs"],
                            "tools": server["tools"],
                        }
                    )

                config["mcp_servers"] = processed_servers

            # Processa sub-agentes
            if "sub_agents" in config:
                config["sub_agents"] = [
                    str(agent_id) for agent_id in config["sub_agents"]
                ]

            # Processa ferramentas
            if "tools" in config:
                config["tools"] = [
                    {"id": str(tool["id"]), "envs": tool["envs"]}
                    for tool in config["tools"]
                ]

            agent_data["config"] = config

        for key, value in agent_data.items():
            setattr(agent, key, value)

        db.commit()
        db.refresh(agent)
        return agent
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Erro ao atualizar agente: {str(e)}"
        )


def delete_agent(db: Session, agent_id: uuid.UUID) -> bool:
    """Remove um agente (soft delete)"""
    try:
        db_agent = get_agent(db, agent_id)
        if not db_agent:
            return False

        db.commit()
        logger.info(f"Agente desativado com sucesso: {agent_id}")
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao desativar agente {agent_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao desativar agente",
        )


def activate_agent(db: Session, agent_id: uuid.UUID) -> bool:
    """Reativa um agente"""
    try:
        db_agent = get_agent(db, agent_id)
        if not db_agent:
            return False

        db.commit()
        logger.info(f"Agente reativado com sucesso: {agent_id}")
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao reativar agente {agent_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao reativar agente",
        )
