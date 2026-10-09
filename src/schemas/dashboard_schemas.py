from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel

from src.schemas.draft_schemas import StatusVisualBadge


class DashboardAlertItem(BaseModel):
    id: str
    alert_type: Literal["uncertain_draft", "pending_review", "system_notice"]
    title: str
    message: str
    visual_badge: StatusVisualBadge
    action_label: Optional[str] = None
    action_endpoint: Optional[str] = None
    entity_id: Optional[str] = None


class DashboardSummaryRead(BaseModel):
    unreviewed_proposals_count: int
    accepted_proposals_count: int
    drafts_created_count: int
    uncertain_actions_count: int
    failed_actions_count: int
    alerts: List[DashboardAlertItem]
