from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
from typing import Dict, List, Optional

from src.domain.draft_action import EmailDraftAction
from src.schemas.draft_schemas import ProposalStatus


@dataclass
class EmailDraftProposalEntity:
    id: str
    source_message_id: str
    subject: str
    from_address: str
    to_address: str
    body: str
    raw_rfc822: bytes
    status: ProposalStatus = ProposalStatus.NOT_REVIEWED
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    current_action_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class DraftRepository:
    """Repositorio transaccional en memoria para propuestas y acciones de borrador."""

    def __init__(self) -> None:
        self._proposals: Dict[str, EmailDraftProposalEntity] = {}
        self._actions: Dict[str, EmailDraftAction] = {}

    def save_proposal(self, proposal: EmailDraftProposalEntity) -> EmailDraftProposalEntity:
        self._proposals[proposal.id] = proposal
        return proposal

    def get_proposal(self, proposal_id: str) -> Optional[EmailDraftProposalEntity]:
        return self._proposals.get(proposal_id)

    def list_proposals(self, status: Optional[ProposalStatus] = None) -> List[EmailDraftProposalEntity]:
        all_proposals = list(self._proposals.values())
        if status:
            return [p for p in all_proposals if p.status == status]
        return all_proposals

    def save_action(self, action: EmailDraftAction) -> EmailDraftAction:
        self._actions[action.id] = action
        return action

    def get_action(self, action_id: str) -> Optional[EmailDraftAction]:
        return self._actions.get(action_id)

    def get_action_for_proposal(self, proposal_id: str) -> Optional[EmailDraftAction]:
        for act in self._actions.values():
            if act.proposal_id == proposal_id:
                return act
        return None
