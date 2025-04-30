"""
A2A (Agent-to-Agent) protocol exception definitions.

This module contains error types and exceptions for the A2A protocol.
"""

from src.schemas.a2a.types import JSONRPCError


class JSONParseError(JSONRPCError):
    """
    Error raised when JSON parsing fails.
    """

    code: int = -32700
    message: str = "Invalid JSON payload"
    data: object | None = None


class InvalidRequestError(JSONRPCError):
    """
    Error raised when request validation fails.
    """

    code: int = -32600
    message: str = "Request payload validation error"
    data: object | None = None


class MethodNotFoundError(JSONRPCError):
    """
    Error raised when the requested method is not found.
    """

    code: int = -32601
    message: str = "Method not found"
    data: None = None


class InvalidParamsError(JSONRPCError):
    """
    Error raised when the parameters are invalid.
    """

    code: int = -32602
    message: str = "Invalid parameters"
    data: object | None = None


class InternalError(JSONRPCError):
    """
    Error raised when an internal error occurs.
    """

    code: int = -32603
    message: str = "Internal error"
    data: object | None = None


class TaskNotFoundError(JSONRPCError):
    """
    Error raised when the requested task is not found.
    """

    code: int = -32001
    message: str = "Task not found"
    data: None = None


class TaskNotCancelableError(JSONRPCError):
    """
    Error raised when a task cannot be canceled.
    """

    code: int = -32002
    message: str = "Task cannot be canceled"
    data: None = None


class PushNotificationNotSupportedError(JSONRPCError):
    """
    Error raised when push notifications are not supported.
    """

    code: int = -32003
    message: str = "Push Notification is not supported"
    data: None = None


class UnsupportedOperationError(JSONRPCError):
    """
    Error raised when an operation is not supported.
    """

    code: int = -32004
    message: str = "This operation is not supported"
    data: None = None


class ContentTypeNotSupportedError(JSONRPCError):
    """
    Error raised when content types are incompatible.
    """

    code: int = -32005
    message: str = "Incompatible content types"
    data: None = None


# Client exceptions


class A2AClientError(Exception):
    """
    Base exception for A2A client errors.
    """

    pass


class A2AClientHTTPError(A2AClientError):
    """
    Exception for HTTP errors in A2A client.
    """

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"HTTP Error {status_code}: {message}")


class A2AClientJSONError(A2AClientError):
    """
    Exception for JSON errors in A2A client.
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(f"JSON Error: {message}")


class MissingAPIKeyError(Exception):
    """
    Exception for missing API key.
    """

    pass
