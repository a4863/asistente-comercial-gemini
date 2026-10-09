from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


class DraftActionState(str, enum.Enum):
    SUBMITTING = "submitting"
    CREATED = "created"
    UNCERTAIN = "uncertain"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_TERMINAL = "failed_terminal"


class InvalidStateTransitionError(Exception):
    """Excepción lanzada cuando se intenta una transición de estado ilegal."""
    pass


_ALLOWED_TRANSITIONS: dict[DraftActionState, set[DraftActionState]] = {
    DraftActionState.SUBMITTING: {
        DraftActionState.CREATED,
        DraftActionState.UNCERTAIN,
        DraftActionState.FAILED_RETRYABLE,
        DraftActionState.FAILED_TERMINAL,
    },
    DraftActionState.UNCERTAIN: {
        DraftActionState.CREATED,
        DraftActionState.FAILED_RETRYABLE,
    },
    DraftActionState.FAILED_RETRYABLE: {
        DraftActionState.SUBMITTING,
    },
    DraftActionState.CREATED: set(),
    DraftActionState.FAILED_TERMINAL: set(),
}


@dataclass
class EmailDraftAction:
    proposal_id: str
    rfc822_payload: bytes
    mailbox_folder: str = "INBOX.Drafts.Borradores Asistente"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    idempotency_token: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: DraftActionState = DraftActionState.SUBMITTING
    imap_uid: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def transition_to(
        self,
        new_state: DraftActionState,
        *,
        imap_uid: str | None = None,
        error_message: str | None = None,
    ) -> None:
        allowed = _ALLOWED_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise InvalidStateTransitionError(
                f"Transición ilegal de estado: {self.state.value} -> {new_state.value}"
            )

        self.state = new_state
        self.updated_at = datetime.now(timezone.utc)

        if imap_uid is not None:
            self.imap_uid = imap_uid

        if error_message is not None:
            self.error_message = error_message

        if new_state == DraftActionState.SUBMITTING:
            self.retry_count += 1
