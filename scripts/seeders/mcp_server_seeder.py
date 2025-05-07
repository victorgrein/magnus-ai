"""
Script to create default MCP servers:
- Anthropic Claude server
- OpenAI GPT server
- Google Gemini server
- Ollama (local) server
Each with default production configurations
"""

import os
import sys
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv
from src.models.models import MCPServer

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_mcp_servers():
    """Create default MCP servers in the system"""
    try:
        # Load environment variables
        load_dotenv()

        # Get database settings
        db_url = os.getenv("POSTGRES_CONNECTION_STRING")
        if not db_url:
            logger.error("Environment variable POSTGRES_CONNECTION_STRING not defined")
            return False

        # Connect to the database
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            # Check if there are already MCP servers
            existing_servers = session.query(MCPServer).all()
            if existing_servers:
                logger.info(
                    f"There are already {len(existing_servers)} MCP servers registered"
                )
                return True

            # MCP servers definitions
            mcp_servers = [
                {
                    "name": "Sequential Thinking",
                    "description": "Sequential Thinking helps users organize their thoughts and break down complex problems through a structured workflow. By guiding users through defined cognitive stages like Problem Definition, Research, Analysis, Synthesis, and Conclusion, it provides a framework for progressive thinking. The server tracks the progression of your thinking process, identifies connections between similar thoughts, monitors progress, and generates summaries, making it easier to approach challenges methodically and reach well-reasoned conclusions.",
                    "config_type": "studio",
                    "config_json": {
                        "command": "npx",
                        "args": [
                            "-y",
                            "@modelcontextprotocol/server-sequential-thinking",
                        ],
                    },
                    "environments": {},
                    "tools": [
                        {
                            "id": "sequentialthinking",
                            "name": "Sequential Thinking",
                            "description": "Helps organize thoughts and break down complex problems through a structured workflow",
                            "tags": ["thinking", "analysis", "problem-solving"],
                            "examples": [
                                "Help me analyze this problem",
                                "Guide me through this decision making process",
                            ],
                            "inputModes": ["text"],
                            "outputModes": ["text"],
                        }
                    ],
                    "type": "community",
                    "id": "4519dd69-9343-4792-af51-dc4d322fb0c9",
                    "created_at": "2025-04-28T15:14:16.901236Z",
                    "updated_at": "2025-04-28T15:43:42.755205Z",
                },
                {
                    "name": "CloudFlare",
                    "description": "Model Context Protocol (MCP) is a new, standardized protocol for managing context between large language models (LLMs) and external systems. In this repository, we provide an installer as well as an MCP Server for Cloudflare's API.\r\n\r\nThis lets you use Claude Desktop, or any MCP Client, to use natural language to accomplish things on your Cloudflare account, e.g.:\r\n\r\nList all the Cloudflare workers on my <some-email>@gmail.com account.\r\nCan you tell me about any potential issues on this particular worker '...'?",
                    "config_type": "sse",
                    "config_json": {
                        "url": "https://observability.mcp.cloudflare.com/sse"
                    },
                    "environments": {},
                    "tools": [
                        {
                            "id": "worker_list",
                            "name": "List Workers",
                            "description": "List all Cloudflare Workers in your account",
                            "tags": ["workers", "cloudflare"],
                            "examples": [
                                "List all my workers",
                                "Show me my Cloudflare workers",
                            ],
                            "inputModes": ["text"],
                            "outputModes": ["application/json"],
                        },
                        {
                            "id": "worker_get",
                            "name": "Get Worker",
                            "description": "Get details of a specific Cloudflare Worker",
                            "tags": ["workers", "cloudflare"],
                            "examples": [
                                "Show me details of worker X",
                                "Get information about worker Y",
                            ],
                            "inputModes": ["text"],
                            "outputModes": ["application/json"],
                        },
                    ],
                    "type": "official",
                    "id": "9138d1a2-24e6-4a75-87b0-bfa4932273e8",
                    "created_at": "2025-04-28T15:16:53.350824Z",
                    "updated_at": "2025-04-28T15:48:04.821766Z",
                },
                {
                    "name": "Brave Search",
                    "description": "Brave Search allows you to seamlessly integrate Brave Search functionality into AI assistants like Claude. By implementing a Model Context Protocol (MCP) server, it enables the AI to leverage Brave Search's web search and local business search capabilities. It provides tools for both general web searches and specific local searches, enhancing the AI assistant's ability to provide relevant and up-to-date information.",
                    "config_type": "studio",
                    "config_json": {
                        "command": "npx",
                        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
                        "env": {"BRAVE_API_KEY": "env@@BRAVE_API_KEY"},
                    },
                    "environments": {"BRAVE_API_KEY": "env@@BRAVE_API_KEY"},
                    "tools": [
                        {
                            "id": "brave_web_search",
                            "name": "Web Search",
                            "description": "Perform web searches using Brave Search",
                            "tags": ["search", "web"],
                            "examples": [
                                "Search for Python documentation",
                                "Find information about AI",
                            ],
                            "inputModes": ["text"],
                            "outputModes": ["application/json"],
                        },
                        {
                            "id": "brave_local_search",
                            "name": "Local Search",
                            "description": "Search for local businesses and places",
                            "tags": ["search", "local"],
                            "examples": [
                                "Find restaurants near me",
                                "Search for hotels in New York",
                            ],
                            "inputModes": ["text"],
                            "outputModes": ["application/json"],
                        },
                    ],
                    "type": "official",
                    "id": "416c94d7-77f5-43f4-8181-aeb87934ecbf",
                    "created_at": "2025-04-28T15:20:07.647225Z",
                    "updated_at": "2025-04-28T15:49:17.434428Z",
                },
            ]

            # Create the MCP servers
            for server_data in mcp_servers:
                server = MCPServer(
                    name=server_data["name"],
                    description=server_data["description"],
                    config_type=server_data["config_type"],
                    config_json=server_data["config_json"],
                    environments=server_data["environments"],
                    tools=server_data["tools"],
                    type=server_data["type"],
                )

                session.add(server)
                logger.info(f"MCP server '{server_data['name']}' created successfully")

            session.commit()
            logger.info("All MCP servers were created successfully")
            return True

        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error when creating MCP servers: {str(e)}")
            return False

    except Exception as e:
        logger.error(f"Error when creating MCP servers: {str(e)}")
        return False
    finally:
        session.close()


if __name__ == "__main__":
    success = create_mcp_servers()
    sys.exit(0 if success else 1)
