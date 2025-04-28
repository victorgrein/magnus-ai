from google.adk.runners import Runner
from google.genai.types import Content, Part
from google.adk.sessions import DatabaseSessionService
from google.adk.memory import InMemoryMemoryService
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from src.utils.logger import setup_logger
from src.core.exceptions import AgentNotFoundError, InternalServerError
from src.services.agent_service import get_agent
from src.services.agent_builder import AgentBuilder
from sqlalchemy.orm import Session

logger = setup_logger(__name__)


async def run_agent(
    agent_id: str,
    contact_id: str,
    message: str,
    session_service: DatabaseSessionService,
    artifacts_service: InMemoryArtifactService,
    memory_service: InMemoryMemoryService,
    db: Session,
):
    try:
        logger.info(
            f"Starting execution of agent {agent_id} for contact {contact_id}"
        )
        logger.info(f"Received message: {message}")

        get_root_agent = get_agent(db, agent_id)
        logger.info(
            f"Root agent found: {get_root_agent.name} (type: {get_root_agent.type})"
        )

        if get_root_agent is None:
            raise AgentNotFoundError(f"Agent with ID {agent_id} not found")

        # Using the AgentBuilder to create the agent
        agent_builder = AgentBuilder(db)
        root_agent, exit_stack = await agent_builder.build_agent(get_root_agent)

        logger.info("Configuring Runner")
        agent_runner = Runner(
            agent=root_agent,
            app_name=agent_id,
            session_service=session_service,
            artifact_service=artifacts_service,
            memory_service=memory_service,
        )
        session_id = contact_id + "_" + agent_id

        logger.info(f"Searching session for contact {contact_id}")
        session = session_service.get_session(
            app_name=agent_id,
            user_id=contact_id,
            session_id=session_id,
        )

        if session is None:
            logger.info(f"Creating new session for contact {contact_id}")
            session = session_service.create_session(
                app_name=agent_id,
                user_id=contact_id,
                session_id=session_id,
            )

        content = Content(role="user", parts=[Part(text=message)])
        logger.info("Starting agent execution")

        final_response_text = None
        try:
            for event in agent_runner.run(
                user_id=contact_id,
                session_id=session_id,
                new_message=content,
            ):
                if event.is_final_response() and event.content and event.content.parts:
                    final_response_text = event.content.parts[0].text
                    logger.info(f"Final response received: {final_response_text}")
        
            completed_session = session_service.get_session(
                app_name=agent_id,
                user_id=contact_id,
                session_id=session_id,
            )
            
            memory_service.add_session_to_memory(completed_session)
        
        finally:
            # Ensure the exit_stack is closed correctly
            if exit_stack:
                await exit_stack.aclose()

        logger.info("Agent execution completed successfully")
        return final_response_text
    except AgentNotFoundError as e:
        logger.error(f"Error processing request: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"Internal error processing request: {str(e)}", exc_info=True)
        raise InternalServerError(str(e))
