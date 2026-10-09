from __future__ import annotations

import email.message
import email.policy
import email.utils
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.domain.draft_action import EmailDraftAction
from src.schemas.draft_schemas import ProposalStatus


@dataclass
class EmailDraftRevisionEntity:
    version: int
    subject: str
    body: str
    author: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


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
    revisions: List[EmailDraftRevisionEntity] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.revisions:
            self.revisions.append(
                EmailDraftRevisionEntity(
                    version=1,
                    subject=self.subject,
                    body=self.body,
                    author="AI Extractor",
                    created_at=self.created_at,
                )
            )

    @property
    def current_version(self) -> int:
        return len(self.revisions)

    def add_revision(self, subject: str, body: str, author: str) -> EmailDraftRevisionEntity:
        new_version_num = len(self.revisions) + 1
        new_rev = EmailDraftRevisionEntity(
            version=new_version_num,
            subject=subject,
            body=body,
            author=author,
            created_at=datetime.now(timezone.utc),
        )
        self.revisions.append(new_rev)
        self.subject = subject
        self.body = body

        # Reconstruir raw_rfc822 inmutable para la nueva revisión
        msg = email.message.EmailMessage(policy=email.policy.default)
        msg["Message-ID"] = email.utils.make_msgid(domain="aclimar.es")
        msg["In-Reply-To"] = self.source_message_id
        msg["References"] = self.source_message_id
        # Garantizar prefijo Re: sin duplicar
        clean_subj = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        msg["Subject"] = clean_subj
        msg["From"] = self.from_address
        msg["To"] = self.to_address
        msg["Date"] = email.utils.format_datetime(datetime.now(timezone.utc))
        msg.set_content(body)
        self.raw_rfc822 = msg.as_bytes()

        # Al editar, se restablece el estado para requerir nueva aprobación de la revisión
        self.status = ProposalStatus.NOT_REVIEWED
        self.reviewed_by = None
        self.reviewed_at = None
        return new_rev


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
