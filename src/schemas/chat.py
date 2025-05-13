"""
┌──────────────────────────────────────────────────────────────────────────────┐
│ @author: Davidson Gomes                                                      │
│ @file: run_seeders.py                                                        │
│ Developed by: Davidson Gomes                                                 │
│ Creation date: May 13, 2025                                                  │
│ Contact: contato@evolution-api.com                                           │
├──────────────────────────────────────────────────────────────────────────────┤
│ @copyright © Evolution API 2025. All rights reserved.                        │
│ Licensed under the Apache License, Version 2.0                               │
│                                                                              │
│ You may not use this file except in compliance with the License.             │
│ You may obtain a copy of the License at                                      │
│                                                                              │
│    http://www.apache.org/licenses/LICENSE-2.0                                │
│                                                                              │
│ Unless required by applicable law or agreed to in writing, software          │
│ distributed under the License is distributed on an "AS IS" BASIS,            │
│ WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.     │
│ See the License for the specific language governing permissions and          │
│ limitations under the License.                                               │
├──────────────────────────────────────────────────────────────────────────────┤
│ @important                                                                   │
│ For any future changes to the code in this file, it is recommended to        │
│ include, together with the modification, the information of the developer    │
│ who changed it and the date of modification.                                 │
└──────────────────────────────────────────────────────────────────────────────┘
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


class ChatRequest(BaseModel):
    """Schema for chat requests"""

    agent_id: str = Field(
        ..., description="ID of the agent that will process the message"
    )
    external_id: str = Field(
        ..., description="ID of the external_id that will process the message"
    )
    message: str = Field(..., description="User message")


class ChatResponse(BaseModel):
    """Schema for chat responses"""

    response: str = Field(..., description="Agent response")
    status: str = Field(..., description="Operation status")
    error: Optional[str] = Field(None, description="Error message, if there is one")
    timestamp: str = Field(..., description="Timestamp of the response")


class ErrorResponse(BaseModel):
    """Schema for error responses"""

    error: str = Field(..., description="Error message")
    status_code: int = Field(..., description="HTTP status code of the error")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error details"
    )
