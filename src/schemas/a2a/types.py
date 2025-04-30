"""
A2A (Agent-to-Agent) protocol type definitions.

This module contains Pydantic schema definitions for the A2A protocol.
"""

from typing import Union, Any, List, Optional, Annotated, Literal
from pydantic import (
    BaseModel,
    Field,
    TypeAdapter,
    field_serializer,
    model_validator,
    ConfigDict,
)
from datetime import datetime
from uuid import uuid4
from enum import Enum
from typing_extensions import Self


class TaskState(str, Enum):
    """
    Enum for the state of a task in the A2A protocol.

    States follow the A2A protocol specification.
    """

    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    CANCELED = "canceled"
    FAILED = "failed"
    UNKNOWN = "unknown"


class TextPart(BaseModel):
    """
    Represents a text part in a message.
    """

    type: Literal["text"] = "text"
    text: str
    metadata: dict[str, Any] | None = None


class FileContent(BaseModel):
    """
    Represents file content in a file part.

    Either bytes or uri must be provided, but not both.
    """

    name: str | None = None
    mimeType: str | None = None
    bytes: str | None = None
    uri: str | None = None

    @model_validator(mode="after")
    def check_content(self) -> Self:
        """
        Validates that either bytes or uri is present, but not both.
        """
        if not (self.bytes or self.uri):
            raise ValueError("Either 'bytes' or 'uri' must be present in the file data")
        if self.bytes and self.uri:
            raise ValueError(
                "Only one of 'bytes' or 'uri' can be present in the file data"
            )
        return self


class FilePart(BaseModel):
    """
    Represents a file part in a message.
    """

    type: Literal["file"] = "file"
    file: FileContent
    metadata: dict[str, Any] | None = None


class DataPart(BaseModel):
    """
    Represents a data part in a message.
    """

    type: Literal["data"] = "data"
    data: dict[str, Any]
    metadata: dict[str, Any] | None = None


Part = Annotated[Union[TextPart, FilePart, DataPart], Field(discriminator="type")]


class Message(BaseModel):
    """
    Represents a message in the A2A protocol.

    A message consists of a role and one or more parts.
    """

    role: Literal["user", "agent"]
    parts: List[Part]
    metadata: dict[str, Any] | None = None


class TaskStatus(BaseModel):
    """
    Represents the status of a task.
    """

    state: TaskState
    message: Message | None = None
    timestamp: datetime = Field(default_factory=datetime.now)

    @field_serializer("timestamp")
    def serialize_dt(self, dt: datetime, _info):
        """
        Serializes datetime to ISO format.
        """
        return dt.isoformat()


class Artifact(BaseModel):
    """
    Represents an artifact produced by an agent.
    """

    name: str | None = None
    description: str | None = None
    parts: List[Part]
    metadata: dict[str, Any] | None = None
    index: int = 0
    append: bool | None = None
    lastChunk: bool | None = None


class Task(BaseModel):
    """
    Represents a task in the A2A protocol.
    """

    id: str
    sessionId: str | None = None
    status: TaskStatus
    artifacts: List[Artifact] | None = None
    history: List[Message] | None = None
    metadata: dict[str, Any] | None = None


class TaskStatusUpdateEvent(BaseModel):
    """
    Represents a task status update event.
    """

    id: str
    status: TaskStatus
    final: bool = False
    metadata: dict[str, Any] | None = None


class TaskArtifactUpdateEvent(BaseModel):
    """
    Represents a task artifact update event.
    """

    id: str
    artifact: Artifact
    metadata: dict[str, Any] | None = None


class AuthenticationInfo(BaseModel):
    """
    Represents authentication information for push notifications.
    """

    model_config = ConfigDict(extra="allow")

    schemes: List[str]
    credentials: str | None = None


class PushNotificationConfig(BaseModel):
    """
    Represents push notification configuration.
    """

    url: str
    token: str | None = None
    authentication: AuthenticationInfo | None = None


class TaskIdParams(BaseModel):
    """
    Represents parameters for identifying a task.
    """

    id: str
    metadata: dict[str, Any] | None = None


class TaskQueryParams(TaskIdParams):
    """
    Represents parameters for querying a task.
    """

    historyLength: int | None = None


class TaskSendParams(BaseModel):
    """
    Represents parameters for sending a task.
    """

    id: str
    sessionId: str = Field(default_factory=lambda: uuid4().hex)
    message: Message
    acceptedOutputModes: Optional[List[str]] = None
    pushNotification: PushNotificationConfig | None = None
    historyLength: int | None = None
    metadata: dict[str, Any] | None = None
    agentId: str = ""


class TaskPushNotificationConfig(BaseModel):
    """
    Represents push notification configuration for a task.
    """

    id: str
    pushNotificationConfig: PushNotificationConfig


# RPC Messages


class JSONRPCMessage(BaseModel):
    """
    Base class for JSON-RPC messages.
    """

    jsonrpc: Literal["2.0"] = "2.0"
    id: int | str | None = Field(default_factory=lambda: uuid4().hex)


class JSONRPCRequest(JSONRPCMessage):
    """
    Represents a JSON-RPC request.
    """

    method: str
    params: dict[str, Any] | None = None


class JSONRPCError(BaseModel):
    """
    Represents a JSON-RPC error.
    """

    code: int
    message: str
    data: Any | None = None


class JSONRPCResponse(JSONRPCMessage):
    """
    Represents a JSON-RPC response.
    """

    result: Any | None = None
    error: JSONRPCError | None = None


class SendTaskRequest(JSONRPCRequest):
    """
    Represents a request to send a task.
    """

    method: Literal["tasks/send"] = "tasks/send"
    params: TaskSendParams


class SendTaskResponse(JSONRPCResponse):
    """
    Represents a response to a send task request.
    """

    result: Task | None = None


class SendTaskStreamingRequest(JSONRPCRequest):
    """
    Represents a request to send a task with streaming.
    """

    method: Literal["tasks/sendSubscribe"] = "tasks/sendSubscribe"
    params: TaskSendParams


class SendTaskStreamingResponse(JSONRPCResponse):
    """
    Represents a streaming response to a send task request.
    """

    result: TaskStatusUpdateEvent | TaskArtifactUpdateEvent | None = None


class GetTaskRequest(JSONRPCRequest):
    """
    Represents a request to get task information.
    """

    method: Literal["tasks/get"] = "tasks/get"
    params: TaskQueryParams


class GetTaskResponse(JSONRPCResponse):
    """
    Represents a response to a get task request.
    """

    result: Task | None = None


class CancelTaskRequest(JSONRPCRequest):
    """
    Represents a request to cancel a task.
    """

    method: Literal["tasks/cancel",] = "tasks/cancel"
    params: TaskIdParams


class CancelTaskResponse(JSONRPCResponse):
    """
    Represents a response to a cancel task request.
    """

    result: Task | None = None


class SetTaskPushNotificationRequest(JSONRPCRequest):
    """
    Represents a request to set push notification for a task.
    """

    method: Literal["tasks/pushNotification/set",] = "tasks/pushNotification/set"
    params: TaskPushNotificationConfig


class SetTaskPushNotificationResponse(JSONRPCResponse):
    """
    Represents a response to a set push notification request.
    """

    result: TaskPushNotificationConfig | None = None


class GetTaskPushNotificationRequest(JSONRPCRequest):
    """
    Represents a request to get push notification configuration for a task.
    """

    method: Literal["tasks/pushNotification/get",] = "tasks/pushNotification/get"
    params: TaskIdParams


class GetTaskPushNotificationResponse(JSONRPCResponse):
    """
    Represents a response to a get push notification request.
    """

    result: TaskPushNotificationConfig | None = None


class TaskResubscriptionRequest(JSONRPCRequest):
    """
    Represents a request to resubscribe to a task.
    """

    method: Literal["tasks/resubscribe",] = "tasks/resubscribe"
    params: TaskIdParams


# TypeAdapter for discriminating A2A requests by method
A2ARequest = TypeAdapter(
    Annotated[
        Union[
            SendTaskRequest,
            GetTaskRequest,
            CancelTaskRequest,
            SetTaskPushNotificationRequest,
            GetTaskPushNotificationRequest,
            TaskResubscriptionRequest,
            SendTaskStreamingRequest,
        ],
        Field(discriminator="method"),
    ]
)


# Agent Card schemas


class AgentProvider(BaseModel):
    """
    Represents the provider of an agent.
    """

    organization: str
    url: str | None = None


class AgentCapabilities(BaseModel):
    """
    Represents the capabilities of an agent.
    """

    streaming: bool = False
    pushNotifications: bool = False
    stateTransitionHistory: bool = False


class AgentAuthentication(BaseModel):
    """
    Represents the authentication requirements for an agent.
    """

    schemes: List[str]
    credentials: str | None = None


class AgentSkill(BaseModel):
    """
    Represents a skill of an agent.
    """

    id: str
    name: str
    description: str | None = None
    tags: List[str] | None = None
    examples: List[str] | None = None
    inputModes: List[str] | None = None
    outputModes: List[str] | None = None


class AgentCard(BaseModel):
    """
    Represents an agent card in the A2A protocol.
    """

    name: str
    description: str | None = None
    url: str
    provider: AgentProvider | None = None
    version: str
    documentationUrl: str | None = None
    capabilities: AgentCapabilities
    authentication: AgentAuthentication | None = None
    defaultInputModes: List[str] = ["text"]
    defaultOutputModes: List[str] = ["text"]
    skills: List[AgentSkill]
