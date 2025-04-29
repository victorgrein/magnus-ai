from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status
from src.models.models import Agent
from src.schemas.schemas import AgentCreate
from typing import List, Optional, Dict, Any
from src.services.mcp_server_service import get_mcp_server
import uuid
import logging

logger = logging.getLogger(__name__)


def validate_sub_agents(db: Session, sub_agents: List[uuid.UUID]) -> bool:
    """Validate if all sub-agents exist"""
    for agent_id in sub_agents:
        agent = get_agent(db, agent_id)
        if not agent:
            return False
    return True


def get_agent(db: Session, agent_id: uuid.UUID) -> Optional[Agent]:
    """Search for an agent by ID"""
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            logger.warning(f"Agent not found: {agent_id}")
            return None

        return agent
    except SQLAlchemyError as e:
        logger.error(f"Error searching for agent {agent_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error searching for agent",
        )


def get_agents_by_client(
    db: Session,
    client_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
) -> List[Agent]:
    """Search for agents by client with pagination"""
    try:
        query = db.query(Agent).filter(Agent.client_id == client_id)

        agents = query.offset(skip).limit(limit).all()

        return agents
    except SQLAlchemyError as e:
        logger.error(f"Error searching for client agents {client_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error searching for agents",
        )


def create_agent(db: Session, agent: AgentCreate) -> Agent:
    """Create a new agent"""
    try:
        # Additional sub-agent validation
        if agent.type != "llm":
            if not isinstance(agent.config, dict):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid configuration: must be an object with sub_agents",
                )

            if "sub_agents" not in agent.config:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid configuration: sub_agents is required for sequential, parallel or loop agents",
                )

            if not agent.config["sub_agents"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid configuration: sub_agents cannot be empty",
                )

            if not validate_sub_agents(db, agent.config["sub_agents"]):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="One or more sub-agents do not exist",
                )

        # Process the configuration before creating the agent
        config = agent.config
        if isinstance(config, dict):
            # Process MCP servers
            if "mcp_servers" in config:
                processed_servers = []
                for server in config["mcp_servers"]:
                    # Search for MCP server in the database
                    mcp_server = get_mcp_server(db, server["id"])
                    if not mcp_server:
                        raise HTTPException(
                            status_code=400,
                            detail=f"MCP server not found: {server['id']}",
                        )

                    # Check if all required environment variables are provided
                    for env_key, env_value in mcp_server.environments.items():
                        if env_key not in server.get("envs", {}):
                            raise HTTPException(
                                status_code=400,
                                detail=f"Environment variable '{env_key}' not provided for MCP server {mcp_server.name}",
                            )

                    # Add the processed server with its tools
                    processed_servers.append(
                        {
                            "id": str(server["id"]),
                            "envs": server["envs"],
                            "tools": server["tools"],
                        }
                    )

                config["mcp_servers"] = processed_servers

            # Process sub-agents
            if "sub_agents" in config:
                config["sub_agents"] = [
                    str(agent_id) for agent_id in config["sub_agents"]
                ]

            # Process tools
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
        logger.info(f"Agent created successfully: {db_agent.id}")

        return db_agent
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error creating agent: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating agent",
        )


async def update_agent(
    db: Session, agent_id: uuid.UUID, agent_data: Dict[str, Any]
) -> Agent:
    """Update an existing agent"""
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Convert UUIDs to strings before saving
        if "config" in agent_data:
            config = agent_data["config"]

            # Process MCP servers
            if "mcp_servers" in config:
                processed_servers = []
                for server in config["mcp_servers"]:
                    # Search for MCP server in the database
                    mcp_server = get_mcp_server(db, server["id"])
                    if not mcp_server:
                        raise HTTPException(
                            status_code=400,
                            detail=f"MCP server not found: {server['id']}",
                        )

                    # Check if all required environment variables are provided
                    for env_key, env_value in mcp_server.environments.items():
                        if env_key not in server.get("envs", {}):
                            raise HTTPException(
                                status_code=400,
                                detail=f"Environment variable '{env_key}' not provided for MCP server {mcp_server.name}",
                            )

                    # Add the processed server
                    processed_servers.append(
                        {
                            "id": str(server["id"]),
                            "envs": server["envs"],
                            "tools": server["tools"],
                        }
                    )

                config["mcp_servers"] = processed_servers

            # Process sub-agents
            if "sub_agents" in config:
                config["sub_agents"] = [
                    str(agent_id) for agent_id in config["sub_agents"]
                ]

            # Process tools
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
        raise HTTPException(status_code=500, detail=f"Error updating agent: {str(e)}")


def delete_agent(db: Session, agent_id: uuid.UUID) -> bool:
    """Remove an agent (soft delete)"""
    try:
        db_agent = get_agent(db, agent_id)
        if not db_agent:
            return False

        db.commit()
        logger.info(f"Agent deactivated successfully: {agent_id}")
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error deactivating agent {agent_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deactivating agent",
        )


def activate_agent(db: Session, agent_id: uuid.UUID) -> bool:
    """Reactivate an agent"""
    try:
        db_agent = get_agent(db, agent_id)
        if not db_agent:
            return False

        db.commit()
        logger.info(f"Agent reactivated successfully: {agent_id}")
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error reactivating agent {agent_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error reactivating agent",
        )
