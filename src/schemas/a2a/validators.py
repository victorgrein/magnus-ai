"""
A2A (Agent-to-Agent) protocol validators.

This module contains validators for the A2A protocol data.
"""

from typing import List
import base64
import re
from pydantic import ValidationError
import logging
from src.schemas.a2a.types import Part, TextPart, FilePart, DataPart, FileContent

logger = logging.getLogger(__name__)


def validate_base64(value: str) -> bool:
    """
    Validates if a string is valid base64.

    Args:
        value: String to validate

    Returns:
        True if valid base64, False otherwise
    """
    try:
        if not value:
            return False

        # Check if the string has base64 characters only
        pattern = r"^[A-Za-z0-9+/]+={0,2}$"
        if not re.match(pattern, value):
            return False

        # Try to decode
        base64.b64decode(value)
        return True
    except Exception as e:
        logger.warning(f"Invalid base64 string: {e}")
        return False


def validate_file_content(file_content: FileContent) -> bool:
    """
    Validates file content.

    Args:
        file_content: FileContent to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        if file_content.bytes is not None:
            return validate_base64(file_content.bytes)
        elif file_content.uri is not None:
            # Basic URL validation
            pattern = r"^https?://.+"
            return bool(re.match(pattern, file_content.uri))
        return False
    except Exception as e:
        logger.warning(f"Invalid file content: {e}")
        return False


def validate_message_parts(parts: List[Part]) -> bool:
    """
    Validates all parts in a message.

    Args:
        parts: List of parts to validate

    Returns:
        True if all parts are valid, False otherwise
    """
    try:
        for part in parts:
            if isinstance(part, TextPart):
                if not part.text or not isinstance(part.text, str):
                    return False
            elif isinstance(part, FilePart):
                if not validate_file_content(part.file):
                    return False
            elif isinstance(part, DataPart):
                if not part.data or not isinstance(part.data, dict):
                    return False
            else:
                return False
        return True
    except (ValidationError, Exception) as e:
        logger.warning(f"Invalid message parts: {e}")
        return False


def text_to_parts(text: str) -> List[Part]:
    """
    Converts a plain text to a list of message parts.

    Args:
        text: Plain text to convert

    Returns:
        List containing a single TextPart
    """
    return [TextPart(text=text)]


def parts_to_text(parts: List[Part]) -> str:
    """
    Extracts text from a list of message parts.

    Args:
        parts: List of parts to extract text from

    Returns:
        Concatenated text from all text parts
    """
    text = ""
    for part in parts:
        if isinstance(part, TextPart):
            text += part.text
        # Could add handling for other part types here
    return text
