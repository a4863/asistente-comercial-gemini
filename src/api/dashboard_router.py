from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.drafts_router import get_draft_repository
from src.domain.draft_action import DraftActionState
from src.repositories.draft_repository import DraftRepository
from src.schemas.dashboard_schemas import DashboardAlertItem, DashboardSummaryRead
from src.schemas.draft_schemas import ProposalStatus, StatusVisualBadge, VisualBadgeColor

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummaryRead)
def get_dashboard_summary(
    repo: DraftRepository = Depends(get_draft_repository),
) -> DashboardSummaryRead:
    """Retorna el resumen consolidado del cockpit comercial y alertas activas."""
    all_proposals = repo.list_proposals()
    unreviewed = [p for p in all_proposals if p.status == ProposalStatus.NOT_REVIEWED]
    accepted = [p for p in all_proposals if p.status == ProposalStatus.ACCEPTED]

    actions = list(repo._actions.values())
    created_actions = [a for a in actions if a.state == DraftActionState.CREATED]
    uncertain_actions = [a for a in actions if a.state == DraftActionState.UNCERTAIN]
    failed_actions = [
        a for a in actions if a.state in (DraftActionState.FAILED_RETRYABLE, DraftActionState.FAILED_TERMINAL)
    ]

    alerts: list[DashboardAlertItem] = []

    # Alerta prioritaria para acciones en estado UNCERTAIN (Alerta visual prominente)
    for act in uncertain_actions:
        alerts.append(
            DashboardAlertItem(
                id=f"alert-uncertain-{act.id}",
                alert_type="uncertain_draft",
                title="Borrador en Estado Incierto",
                message=(
                    f"La acción para la propuesta '{act.proposal_id}' sufrió timeout de red durante APPEND. "
                    "Se requiere reconciliación de lectura antes de reintentar para no duplicar correos."
                ),
                visual_badge=StatusVisualBadge(
                    label="Requiere Reconciliación",
                    color=VisualBadgeColor.WARNING,
                    icon="alert-triangle",
                    description="Operación pendiente de verificación remota en modo read-only.",
                ),
                action_label="Verificar en Servidor",
                action_endpoint=f"/api/drafts/actions/{act.id}/reconcile",
                entity_id=act.id,
            )
        )

    # Alerta para propuestas pendientes de revisión
    if unreviewed:
        alerts.append(
            DashboardAlertItem(
                id="alert-proposals-pending",
                alert_type="pending_review",
                title="Propuestas Comerciales Pendientes",
                message=f"Hay {len(unreviewed)} propuesta(s) de borrador esperando revisión humana del comercial.",
                visual_badge=StatusVisualBadge(
                    label=f"{len(unreviewed)} Pendientes",
                    color=VisualBadgeColor.AMBER,
                    icon="clock",
                    description="Atención comercial requerida para aceptar o rechazar.",
                ),
                action_label="Revisar Propuestas",
                action_endpoint="/api/drafts/proposals?status=not_reviewed",
            )
        )

    return DashboardSummaryRead(
        unreviewed_proposals_count=len(unreviewed),
        accepted_proposals_count=len(accepted),
        drafts_created_count=len(created_actions),
        uncertain_actions_count=len(uncertain_actions),
        failed_actions_count=len(failed_actions),
        alerts=alerts,
    )
