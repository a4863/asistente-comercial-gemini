from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

from src.domain.draft_action import DraftActionState


class ProposalStatus(str, enum.Enum):
    NOT_REVIEWED = "not_reviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class VisualBadgeColor(str, enum.Enum):
    GREEN = "green"    # Acción completada / creada / aceptada
    BLUE = "blue"      # Preparada / planned / submitting
    AMBER = "amber"    # Pendiente de aprobación / atención comercial
    RED = "red"        # Error terminal / rechazada
    GRAY = "gray"      # Histórico / inactivo
    WARNING = "warning"# Estado incierto / requiere reconciliación


class StatusVisualBadge(BaseModel):
    """Metadatos para renderizado visual en la interfaz de Lovable."""
    label: str
    color: VisualBadgeColor
    icon: str
    description: str


class DraftRevisionRead(BaseModel):
    version: int
    subject: str
    body: str
    author: str
    created_at: datetime


class DraftProposalRead(BaseModel):
    id: str
    source_message_id: str
    subject: str
    from_address: str
    to_address: str
    body: str
    status: ProposalStatus
    current_version: int = 1
    revisions: List[DraftRevisionRead] = []
    created_at: datetime
    current_action_id: str | None = None
    current_action_state: DraftActionState | None = None
    visual_badge: StatusVisualBadge
    allowed_ui_actions: List[str] = Field(
        default_factory=list,
        description="Lista de acciones autorizadas por el backend para renderizar botones en la UI.",
    )


class DraftReviewRequest(BaseModel):
    decision: Literal["accepted", "rejected"]
    reviewer: str = Field(..., min_length=1)


class DraftEditRequest(BaseModel):
    subject: str = Field(..., min_length=1, description="Nuevo asunto modificado por el comercial.")
    body: str = Field(..., min_length=1, description="Nuevo cuerpo modificado por el comercial.")
    editor: str = Field(..., min_length=1, description="Identificador del usuario que realiza la edición.")


class DraftActionRead(BaseModel):
    id: str
    proposal_id: str
    state: DraftActionState
    mailbox_folder: str
    imap_uid: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    created_at: datetime
    updated_at: datetime
    can_retry: bool
    is_uncertain: bool
    is_terminal: bool
    visual_badge: StatusVisualBadge
    allowed_ui_actions: List[str] = Field(
        default_factory=list,
        description="Lista de acciones autorizadas por el backend para la acción IMAP.",
    )
