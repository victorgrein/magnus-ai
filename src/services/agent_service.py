from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status
from src.models.models import Agent
from src.schemas.schemas import AgentCreate
from typing import List, Optional, Dict, Any, Union
from src.services.mcp_server_service import get_mcp_server
import uuid
import logging
import httpx

logger = logging.getLogger(__name__)


def _convert_uuid_to_str(obj):
    """
    Recursively convert all UUID objects to strings in a dictionary, list or scalar value.
    This ensures JSON serialize for complex nested objects.
    """
    if isinstance(obj, dict):
        return {key: _convert_uuid_to_str(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_convert_uuid_to_str(item) for item in obj]
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    else:
        return obj


def validate_sub_agents(db: Session, sub_agents: List[uuid.UUID]) -> bool:
    """Validate if all sub-agents exist"""
    for agent_id in sub_agents:
        agent = get_agent(db, agent_id)
        if not agent:
            return False
    return True


def get_agent(db: Session, agent_id: Union[uuid.UUID, str]) -> Optional[Agent]:
    """Search for an agent by ID"""
    try:
        # Convert to UUID if it's a string
        if isinstance(agent_id, str):
            try:
                agent_id = uuid.UUID(agent_id)
            except ValueError:
                logger.warning(f"Invalid agent ID: {agent_id}")
                return None

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


async def create_agent(db: Session, agent: AgentCreate) -> Agent:
    """Create a new agent"""
    try:
        # Special handling for a2a type agents
        if agent.type == "a2a":
            if not agent.agent_card_url:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="agent_card_url is required for a2a type agents",
                )

            try:
                # Fetch agent card information
                async with httpx.AsyncClient() as client:
                    response = await client.get(agent.agent_card_url)
                    if response.status_code != 200:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Failed to fetch agent card: HTTP {response.status_code}",
                        )
                    agent_card = response.json()

                # Update agent with information from agent card
                agent.name = agent_card.get("name", "Unknown Agent")
                agent.description = agent_card.get("description", "")

                if agent.config is None:
                    agent.config = {}

                # Store the whole agent card in config
                if isinstance(agent.config, dict):
                    agent.config["agent_card"] = agent_card
                else:
                    agent.config = {"agent_card": agent_card}

            except Exception as e:
                logger.error(f"Error fetching agent card: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to process agent card: {str(e)}",
                )

        # Additional sub-agent validation (for non-llm and non-a2a types)
        elif agent.type != "llm":
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
                    # Convert server id to UUID if it's a string
                    server_id = server["id"]
                    if isinstance(server_id, str):
                        server_id = uuid.UUID(server_id)

                    # Search for MCP server in the database
                    mcp_server = get_mcp_server(db, server_id)
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

        # Ensure all config objects are serializable (convert UUIDs to strings)
        if agent.config is not None:
            agent.config = _convert_uuid_to_str(agent.config)

        # Convert agent to dict ensuring all UUIDs are converted to strings
        agent_dict = agent.model_dump()
        agent_dict = _convert_uuid_to_str(agent_dict)

        # Create agent from the processed dictionary
        db_agent = Agent(**agent_dict)

        # Make one final check to ensure all nested objects are serializable
        # (especially nested UUIDs in config)
        if db_agent.config is not None:
            db_agent.config = _convert_uuid_to_str(db_agent.config)

        db.add(db_agent)
        db.commit()
        db.refresh(db_agent)
        logger.info(f"Agent created successfully: {db_agent.id}")

        return db_agent
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error creating agent: {str(e)}")

        # Add debugging info
        try:
            import json

            if "agent_dict" in locals():
                agent_json = json.dumps(agent_dict)
                logger.info(f"Agent creation attempt with: {agent_json[:200]}...")
        except Exception as json_err:
            logger.error(f"Could not serialize agent for debugging: {str(json_err)}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating agent: {str(e)}",
        )


async def update_agent(
    db: Session, agent_id: uuid.UUID, agent_data: Dict[str, Any]
) -> Agent:
    """Update an existing agent"""
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        if "type" in agent_data and agent_data["type"] == "a2a":
            if "agent_card_url" not in agent_data or not agent_data["agent_card_url"]:
                raise HTTPException(
                    status_code=400,
                    detail="agent_card_url is required for a2a type agents",
                )

            if not agent_data["agent_card_url"].endswith("/.well-known/agent.json"):
                raise HTTPException(
                    status_code=400,
                    detail="agent_card_url must end with /.well-known/agent.json",
                )

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(agent_data["agent_card_url"])
                    if response.status_code != 200:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Failed to fetch agent card: HTTP {response.status_code}",
                        )
                    agent_card = response.json()

                agent_data["name"] = agent_card.get("name", "Unknown Agent")
                agent_data["description"] = agent_card.get("description", "")

                if "config" not in agent_data or agent_data["config"] is None:
                    agent_data["config"] = agent.config if agent.config else {}

                agent_data["config"]["agent_card"] = agent_card

            except Exception as e:
                logger.error(f"Error fetching agent card: {str(e)}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to process agent card: {str(e)}",
                )

        elif "agent_card_url" in agent_data and agent.type == "a2a":
            if not agent_data["agent_card_url"]:
                raise HTTPException(
                    status_code=400,
                    detail="agent_card_url cannot be empty for a2a type agents",
                )

            if not agent_data["agent_card_url"].endswith("/.well-known/agent.json"):
                raise HTTPException(
                    status_code=400,
                    detail="agent_card_url must end with /.well-known/agent.json",
                )

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(agent_data["agent_card_url"])
                    if response.status_code != 200:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Failed to fetch agent card: HTTP {response.status_code}",
                        )
                    agent_card = response.json()

                agent_data["name"] = agent_card.get("name", "Unknown Agent")
                agent_data["description"] = agent_card.get("description", "")

                if "config" not in agent_data or agent_data["config"] is None:
                    agent_data["config"] = agent.config if agent.config else {}

                agent_data["config"]["agent_card"] = agent_card

            except Exception as e:
                logger.error(f"Error fetching agent card: {str(e)}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to process agent card: {str(e)}",
                )

        # Convert UUIDs to strings before saving
        if "config" in agent_data:
            config = agent_data["config"]

            # Process MCP servers
            if "mcp_servers" in config:
                processed_servers = []
                for server in config["mcp_servers"]:
                    # Convert server id to UUID if it's a string
                    server_id = server["id"]
                    if isinstance(server_id, str):
                        server_id = uuid.UUID(server_id)

                    # Search for MCP server in the database
                    mcp_server = get_mcp_server(db, server_id)
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

        # Ensure all config objects are serializable (convert UUIDs to strings)
        if "config" in agent_data and agent_data["config"] is not None:
            agent_data["config"] = _convert_uuid_to_str(agent_data["config"])

        for key, value in agent_data.items():
            setattr(agent, key, value)

        db.commit()
        db.refresh(agent)
        return agent
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating agent: {str(e)}")


def delete_agent(db: Session, agent_id: uuid.UUID) -> bool:
    """Remove an agent from the database"""
    try:
        db_agent = get_agent(db, agent_id)
        if not db_agent:
            return False

        # Actually delete the agent from the database
        db.delete(db_agent)
        db.commit()
        logger.info(f"Agent deleted successfully: {agent_id}")
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error deleting agent {agent_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting agent",
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
