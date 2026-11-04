"""Conversation IDs include UUIDs and IDs retained from earlier chat versions."""
from typing import Annotated

from fastapi import Path


ConversationId = Annotated[str, Path(
    min_length=1,
    max_length=36,
    pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
)]
