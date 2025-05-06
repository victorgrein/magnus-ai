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


# Helper function to generate API keys
def generate_api_key() -> str:
    """Generate a secure API key"""
    # Format: sk-proj-{random 64 chars}

    return str(uuid.uuid4())


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


def validate_sub_agents(db: Session, sub_agents: List[Union[uuid.UUID, str]]) -> bool:
    """Validate if all sub-agents exist"""
    logger.info(f"Validating sub-agents: {sub_agents}")

    if not sub_agents:
        logger.warning("Empty sub-agents list")
        return False

    for agent_id in sub_agents:
        # Ensure the ID is in the correct format
        agent_id_str = str(agent_id)
        logger.info(f"Validating sub-agent with ID: {agent_id_str}")

        agent = get_agent(db, agent_id_str)
        if not agent:
            logger.warning(f"Sub-agent not found: {agent_id_str}")
            return False
        logger.info(f"Valid sub-agent: {agent.name} (ID: {agent_id_str})")

    logger.info(f"All {len(sub_agents)} sub-agents are valid")
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

        # Para agentes workflow, não fazemos nenhuma validação específica
        # apenas garantimos que config é um dicionário
        elif agent.type == "workflow":
            if not isinstance(agent.config, dict):
                agent.config = {}

            # Garantir a API key
            if "api_key" not in agent.config or not agent.config["api_key"]:
                agent.config["api_key"] = generate_api_key()

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
        if config is None:
            config = {}
            agent.config = config

        # Ensure config is a dictionary
        if not isinstance(config, dict):
            config = {}
            agent.config = config

        # Generate automatic API key if not provided or empty
        if not config.get("api_key") or config.get("api_key") == "":
            logger.info("Generating automatic API key for new agent")
            config["api_key"] = generate_api_key()

        # Preservar todos os campos originais
        processed_config = {}
        processed_config["api_key"] = config.get("api_key", "")

        # Copiar campos originais
        if "tools" in config:
            processed_config["tools"] = config["tools"]

        if "custom_tools" in config:
            processed_config["custom_tools"] = config["custom_tools"]

        if "sub_agents" in config:
            processed_config["sub_agents"] = config["sub_agents"]

        if "custom_mcp_servers" in config:
            processed_config["custom_mcp_servers"] = config["custom_mcp_servers"]

        # Preservar outros campos não processados especificamente
        for key, value in config.items():
            if key not in [
                "api_key",
                "tools",
                "custom_tools",
                "sub_agents",
                "custom_mcp_servers",
                "mcp_servers",
            ]:
                processed_config[key] = value

        # Processar apenas campos que precisam de processamento
        # Process MCP servers
        if "mcp_servers" in config and config["mcp_servers"] is not None:
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

            processed_config["mcp_servers"] = processed_servers
        elif "mcp_servers" in config:
            processed_config["mcp_servers"] = config["mcp_servers"]

        # Process custom MCP servers
        if "custom_mcp_servers" in config and config["custom_mcp_servers"] is not None:
            processed_custom_servers = []
            for server in config["custom_mcp_servers"]:
                # Validate URL format
                if not server.get("url"):
                    raise HTTPException(
                        status_code=400,
                        detail="URL is required for custom MCP servers",
                    )

                # Add the custom server
                processed_custom_servers.append(
                    {"url": server["url"], "headers": server.get("headers", {})}
                )

            processed_config["custom_mcp_servers"] = processed_custom_servers

        # Process sub-agents
        if "sub_agents" in config and config["sub_agents"] is not None:
            processed_config["sub_agents"] = [
                str(agent_id) for agent_id in config["sub_agents"]
            ]

        # Process tools
        if "tools" in config and config["tools"] is not None:
            processed_tools = []
            for tool in config["tools"]:
                # Convert tool id to string
                tool_id = tool["id"]

                # Validar envs para garantir que não é None
                envs = tool.get("envs", {})
                if envs is None:
                    envs = {}

                processed_tools.append({"id": str(tool_id), "envs": envs})
            processed_config["tools"] = processed_tools

        agent.config = processed_config

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

            # Preservar todos os campos originais
            processed_config = {}
            processed_config["api_key"] = config.get("api_key", "")

            # Copiar campos originais
            if "tools" in config:
                processed_config["tools"] = config["tools"]

            if "custom_tools" in config:
                processed_config["custom_tools"] = config["custom_tools"]

            if "sub_agents" in config:
                processed_config["sub_agents"] = config["sub_agents"]

            if "custom_mcp_servers" in config:
                processed_config["custom_mcp_servers"] = config["custom_mcp_servers"]

            # Preservar outros campos não processados especificamente
            for key, value in config.items():
                if key not in [
                    "api_key",
                    "tools",
                    "custom_tools",
                    "sub_agents",
                    "custom_mcp_servers",
                    "mcp_servers",
                ]:
                    processed_config[key] = value

            # Processar apenas campos que precisam de processamento
            # Process MCP servers
            if "mcp_servers" in config and config["mcp_servers"] is not None:
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

                processed_config["mcp_servers"] = processed_servers
            elif "mcp_servers" in config:
                processed_config["mcp_servers"] = config["mcp_servers"]

            # Process custom MCP servers
            if (
                "custom_mcp_servers" in config
                and config["custom_mcp_servers"] is not None
            ):
                processed_custom_servers = []
                for server in config["custom_mcp_servers"]:
                    # Validate URL format
                    if not server.get("url"):
                        raise HTTPException(
                            status_code=400,
                            detail="URL is required for custom MCP servers",
                        )

                    # Add the custom server
                    processed_custom_servers.append(
                        {"url": server["url"], "headers": server.get("headers", {})}
                    )

                processed_config["custom_mcp_servers"] = processed_custom_servers

            # Process sub-agents
            if "sub_agents" in config and config["sub_agents"] is not None:
                processed_config["sub_agents"] = [
                    str(agent_id) for agent_id in config["sub_agents"]
                ]

            # Process tools
            if "tools" in config and config["tools"] is not None:
                processed_tools = []
                for tool in config["tools"]:
                    # Convert tool id to string
                    tool_id = tool["id"]

                    # Validar envs para garantir que não é None
                    envs = tool.get("envs", {})
                    if envs is None:
                        envs = {}

                    processed_tools.append({"id": str(tool_id), "envs": envs})
                processed_config["tools"] = processed_tools

            agent_data["config"] = processed_config

        # Ensure all config objects are serializable (convert UUIDs to strings)
        if "config" in agent_data and agent_data["config"] is not None:
            agent_data["config"] = _convert_uuid_to_str(agent_data["config"])

        # Check if the agent has API key and generate one if not
        agent_config = agent.config or {}
        if "config" not in agent_data:
            agent_data["config"] = agent_config

        if not agent_config.get("api_key") and (
            "config" not in agent_data or not agent_data["config"].get("api_key")
        ):
            logger.info(f"Generating missing API key for existing agent: {agent_id}")
            if "config" not in agent_data:
                agent_data["config"] = {}
            agent_data["config"]["api_key"] = generate_api_key()

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
