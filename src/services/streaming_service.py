import uuid
import json
from typing import AsyncGenerator, Dict, Any
from fastapi import HTTPException
from datetime import datetime
from src.schemas.streaming import (
    JSONRPCRequest,
    TaskStatusUpdateEvent,
)
from src.services.agent_runner import run_agent
from src.services.service_providers import (
    session_service,
    artifacts_service,
    memory_service,
)
from sqlalchemy.orm import Session


class StreamingService:
    def __init__(self):
        self.active_connections: Dict[str, Any] = {}

    async def send_task_streaming(
        self,
        agent_id: str,
        api_key: str,
        message: str,
        contact_id: str = None,
        session_id: str = None,
        db: Session = None,
    ) -> AsyncGenerator[str, None]:
        """
        Starts the SSE event streaming for a task.

        Args:
            agent_id: Agent ID
            api_key: API key for authentication
            message: Initial message
            contact_id: Contact ID (optional)
            session_id: Session ID (optional)
            db: Database session

        Yields:
            Formatted SSE events
        """
        # Basic API key validation
        if not api_key:
            raise HTTPException(status_code=401, detail="API key is required")

        # Generate unique IDs
        task_id = contact_id or str(uuid.uuid4())
        request_id = str(uuid.uuid4())

        # Build JSON-RPC payload
        payload = JSONRPCRequest(
            id=request_id,
            params={
                "id": task_id,
                "sessionId": session_id,
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": message}],
                },
            },
        )

        # Register connection
        self.active_connections[task_id] = {
            "agent_id": agent_id,
            "api_key": api_key,
            "session_id": session_id,
        }

        try:
            # Send start event
            yield self._format_sse_event(
                "status",
                TaskStatusUpdateEvent(
                    state="working",
                    timestamp=datetime.now().isoformat(),
                    message=payload.params["message"],
                ).model_dump_json(),
            )

            # Execute the agent
            result = await run_agent(
                str(agent_id),
                contact_id or task_id,
                message,
                session_service,
                artifacts_service,
                memory_service,
                db,
                session_id,
            )

            # Send the agent's response as a separate event
            yield self._format_sse_event(
                "message",
                json.dumps(
                    {
                        "role": "agent",
                        "content": result,
                        "timestamp": datetime.now().isoformat(),
                    }
                ),
            )

            # Completion event
            yield self._format_sse_event(
                "status",
                TaskStatusUpdateEvent(
                    state="completed",
                    timestamp=datetime.now().isoformat(),
                ).model_dump_json(),
            )

        except Exception as e:
            # Error event
            yield self._format_sse_event(
                "status",
                TaskStatusUpdateEvent(
                    state="failed",
                    timestamp=datetime.now().isoformat(),
                    error={"message": str(e)},
                ).model_dump_json(),
            )
            raise

        finally:
            # Clean connection
            self.active_connections.pop(task_id, None)

    def _format_sse_event(self, event_type: str, data: str) -> str:
        """Format an SSE event."""
        return f"event: {event_type}\ndata: {data}\n\n"

    async def close_connection(self, task_id: str):
        """Close a streaming connection."""
        if task_id in self.active_connections:
            self.active_connections.pop(task_id)
