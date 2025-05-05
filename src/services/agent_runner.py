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
from typing import Optional, AsyncGenerator
import asyncio

logger = setup_logger(__name__)


async def run_agent(
    agent_id: str,
    contact_id: str,
    message: str,
    session_service: DatabaseSessionService,
    artifacts_service: InMemoryArtifactService,
    memory_service: InMemoryMemoryService,
    db: Session,
    session_id: Optional[str] = None,
    timeout: float = 60.0,
):
    exit_stack = None
    try:
        logger.info(f"Starting execution of agent {agent_id} for contact {contact_id}")
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
        adk_session_id = contact_id + "_" + agent_id
        if session_id is None:
            session_id = adk_session_id

        logger.info(f"Searching session for contact {contact_id}")
        session = session_service.get_session(
            app_name=agent_id,
            user_id=contact_id,
            session_id=adk_session_id,
        )

        if session is None:
            logger.info(f"Creating new session for contact {contact_id}")
            session = session_service.create_session(
                app_name=agent_id,
                user_id=contact_id,
                session_id=adk_session_id,
            )

        content = Content(role="user", parts=[Part(text=message)])
        logger.info("Starting agent execution")

        final_response_text = None
        try:
            response_queue = asyncio.Queue()
            execution_completed = asyncio.Event()

            async def process_events():
                try:
                    events_async = agent_runner.run_async(
                        user_id=contact_id,
                        session_id=adk_session_id,
                        new_message=content,
                    )

                    last_response = None
                    all_responses = []

                    async for event in events_async:
                        if (
                            event.content
                            and event.content.parts
                            and event.content.parts[0].text
                        ):
                            current_text = event.content.parts[0].text
                            last_response = current_text
                            all_responses.append(current_text)

                        if event.actions and event.actions.escalate:
                            escalate_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
                            await response_queue.put(escalate_text)
                            execution_completed.set()
                            return

                    if last_response:
                        await response_queue.put(last_response)
                    else:
                        await response_queue.put("Finished without specific response")

                    execution_completed.set()
                except Exception as e:
                    logger.error(f"Error in process_events: {str(e)}")
                    await response_queue.put(f"Error: {str(e)}")
                    execution_completed.set()

            task = asyncio.create_task(process_events())

            try:
                wait_task = asyncio.create_task(execution_completed.wait())
                done, pending = await asyncio.wait({wait_task}, timeout=timeout)

                for p in pending:
                    p.cancel()

                if not execution_completed.is_set():
                    logger.warning(f"Agent execution timed out after {timeout} seconds")
                    await response_queue.put(
                        "The response took too long and was interrupted."
                    )

                final_response_text = await response_queue.get()

            except Exception as e:
                logger.error(f"Error waiting for response: {str(e)}")
                final_response_text = f"Error processing response: {str(e)}"

            # Add the session to memory after completion
            completed_session = session_service.get_session(
                app_name=agent_id,
                user_id=contact_id,
                session_id=adk_session_id,
            )

            memory_service.add_session_to_memory(completed_session)

            # Cancel the processing task if it is still running
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.info("Task cancelled successfully")
                except Exception as e:
                    logger.error(f"Error cancelling task: {str(e)}")

        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            raise e

        logger.info("Agent execution completed successfully")
        return final_response_text
    except AgentNotFoundError as e:
        logger.error(f"Error processing request: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"Internal error processing request: {str(e)}", exc_info=True)
        raise InternalServerError(str(e))
    finally:
        # Clean up MCP connection - MUST be executed in the same task
        if exit_stack:
            logger.info("Closing MCP server connection...")
            try:
                await exit_stack.aclose()
            except Exception as e:
                logger.error(f"Error closing MCP connection: {e}")
                # Do not raise the exception to not obscure the original error


async def run_agent_stream(
    agent_id: str,
    contact_id: str,
    message: str,
    session_service: DatabaseSessionService,
    artifacts_service: InMemoryArtifactService,
    memory_service: InMemoryMemoryService,
    db: Session,
    session_id: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    try:
        logger.info(
            f"Starting streaming execution of agent {agent_id} for contact {contact_id}"
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
        adk_session_id = contact_id + "_" + agent_id
        if session_id is None:
            session_id = adk_session_id

        logger.info(f"Searching session for contact {contact_id}")
        session = session_service.get_session(
            app_name=agent_id,
            user_id=contact_id,
            session_id=adk_session_id,
        )

        if session is None:
            logger.info(f"Creating new session for contact {contact_id}")
            session = session_service.create_session(
                app_name=agent_id,
                user_id=contact_id,
                session_id=adk_session_id,
            )

        content = Content(role="user", parts=[Part(text=message)])
        logger.info("Starting agent streaming execution")

        try:
            events_async = agent_runner.run_async(
                user_id=contact_id,
                session_id=adk_session_id,
                new_message=content,
            )

            async for event in events_async:
                if event.content and event.content.parts:
                    text = event.content.parts[0].text
                    if text:
                        yield text
                        await asyncio.sleep(0)  # Allow other tasks to run

            completed_session = session_service.get_session(
                app_name=agent_id,
                user_id=contact_id,
                session_id=adk_session_id,
            )

            memory_service.add_session_to_memory(completed_session)
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            raise e
        finally:
            # Clean up MCP connection
            if exit_stack:
                logger.info("Closing MCP server connection...")
                try:
                    await exit_stack.aclose()
                except Exception as e:
                    logger.error(f"Error closing MCP connection: {e}")

        logger.info("Agent streaming execution completed successfully")
    except AgentNotFoundError as e:
        logger.error(f"Error processing request: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"Internal error processing request: {str(e)}", exc_info=True)
        raise InternalServerError(str(e))
