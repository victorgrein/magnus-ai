from fastapi import HTTPException
from typing import Optional, Dict, Any


class BaseAPIException(HTTPException):
    """Base class for API exceptions"""

    def __init__(
        self,
        status_code: int,
        message: str,
        error_code: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            status_code=status_code,
            detail={
                "error": message,
                "error_code": error_code,
                "details": details or {},
            },
        )


class AgentNotFoundError(BaseAPIException):
    """Exception when the agent is not found"""

    def __init__(self, agent_id: str):
        super().__init__(
            status_code=404,
            message=f"Agent with ID {agent_id} not found",
            error_code="AGENT_NOT_FOUND",
        )


class InvalidParameterError(BaseAPIException):
    """Exception for invalid parameters"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=400,
            message=message,
            error_code="INVALID_PARAMETER",
            details=details,
        )


class InvalidRequestError(BaseAPIException):
    """Exception for invalid requests"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=400,
            message=message,
            error_code="INVALID_REQUEST",
            details=details,
        )


class InternalServerError(BaseAPIException):
    """Exception for server errors"""

    def __init__(self, message: str = "Server error"):
        super().__init__(
            status_code=500, message=message, error_code="INTERNAL_SERVER_ERROR"
        )
