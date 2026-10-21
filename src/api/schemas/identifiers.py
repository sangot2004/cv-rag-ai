"""Conversation IDs include UUIDs and IDs retained from earlier chat versions."""
from typing import Annotated

from fastapi import Path


# Matches the CHAR(36) metadata key. Treat IDs as opaque strings so legacy
# checkpoint keys are preserved; ownership is checked by conversation_store.
ConversationId = Annotated[str, Path(
    min_length=1,
    max_length=36,
    pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
)]
