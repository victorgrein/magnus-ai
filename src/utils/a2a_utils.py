"""
A2A protocol utilities.

This module contains utility functions for the A2A protocol implementation.
"""

import logging
from typing import List, Optional, Any, Dict
from src.schemas.a2a import (
    ContentTypeNotSupportedError,
    UnsupportedOperationError,
    JSONRPCResponse,
)

logger = logging.getLogger(__name__)


def are_modalities_compatible(
    server_output_modes: Optional[List[str]], client_output_modes: Optional[List[str]]
) -> bool:
    """
    Check if server and client modalities are compatible.

    Modalities are compatible if they are both non-empty
    and there is at least one common element.

    Args:
        server_output_modes: List of output modes supported by the server
        client_output_modes: List of output modes requested by the client

    Returns:
        True if compatible, False otherwise
    """
    # If client doesn't specify modes, assume all are accepted
    if client_output_modes is None or len(client_output_modes) == 0:
        return True

    # If server doesn't specify modes, assume all are supported
    if server_output_modes is None or len(server_output_modes) == 0:
        return True

    # Check if there's at least one common mode
    return any(mode in server_output_modes for mode in client_output_modes)


def new_incompatible_types_error(request_id: str) -> JSONRPCResponse:
    """
    Create a JSON-RPC response for incompatible content types error.

    Args:
        request_id: The ID of the request that caused the error

    Returns:
        JSON-RPC response with ContentTypeNotSupportedError
    """
    return JSONRPCResponse(id=request_id, error=ContentTypeNotSupportedError())


def new_not_implemented_error(request_id: str) -> JSONRPCResponse:
    """
    Create a JSON-RPC response for unimplemented operation error.

    Args:
        request_id: The ID of the request that caused the error

    Returns:
        JSON-RPC response with UnsupportedOperationError
    """
    return JSONRPCResponse(id=request_id, error=UnsupportedOperationError())


def create_task_id(agent_id: str, session_id: str, timestamp: str = None) -> str:
    """
    Create a unique task ID for an agent and session.

    Args:
        agent_id: The ID of the agent
        session_id: The ID of the session
        timestamp: Optional timestamp to include in the ID

    Returns:
        A unique task ID
    """
    import uuid
    import time

    timestamp = timestamp or str(int(time.time()))
    unique = uuid.uuid4().hex[:8]

    return f"{agent_id}_{session_id}_{timestamp}_{unique}"


def format_error_response(error: Exception, request_id: str = None) -> Dict[str, Any]:
    """
    Format an exception as a JSON-RPC error response.

    Args:
        error: The exception to format
        request_id: The ID of the request that caused the error

    Returns:
        JSON-RPC error response as dictionary
    """
    from src.schemas.a2a import InternalError, JSONRPCResponse

    error_response = JSONRPCResponse(
        id=request_id, error=InternalError(message=str(error))
    )

    return error_response.model_dump(exclude_none=True)
