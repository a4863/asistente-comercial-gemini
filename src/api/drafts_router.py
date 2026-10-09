from __future__ import annotations

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.domain.draft_action import DraftActionState, EmailDraftAction
from src.repositories.draft_repository import DraftRepository
from src.schemas.draft_schemas import (
    DraftActionRead,
    DraftProposalRead,
    DraftReviewRequest,
    ProposalStatus,
    StatusVisualBadge,
    VisualBadgeColor,
)
from src.services.imap_draft_service import IMAPClientProtocol, ImapDraftAppender

router = APIRouter(prefix="/api/drafts", tags=["Drafts"])

# Instancias compartidas por defecto para el backend local
_repo = DraftRepository()
_appender = ImapDraftAppender()
_imap_client: Optional[IMAPClientProtocol] = None


def get_draft_repository() -> DraftRepository:
    return _repo


def get_imap_appender() -> ImapDraftAppender:
    return _appender


def get_imap_client() -> IMAPClientProtocol:
    if _imap_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cliente IMAP no inicializado en el entorno local.",
        )
    return _imap_client


def set_imap_client_override(client: IMAPClientProtocol | None) -> None:
    global _imap_client
    _imap_client = client


def build_proposal_visual_badge(status: ProposalStatus) -> StatusVisualBadge:
    if status == ProposalStatus.NOT_REVIEWED:
        return StatusVisualBadge(
            label="Pendiente de Revisión",
            color=VisualBadgeColor.AMBER,
            icon="clock",
            description="La propuesta de borrador requiere aprobación humana del comercial.",
        )
    if status == ProposalStatus.ACCEPTED:
        return StatusVisualBadge(
            label="Propuesta Aceptada",
            color=VisualBadgeColor.GREEN,
            icon="check-circle",
            description="Revisada y aceptada. Lista para materializar en buzón de Outlook.",
        )
    return StatusVisualBadge(
        label="Propuesta Rechazada",
        color=VisualBadgeColor.RED,
        icon="x-circle",
        description="Descartada por el usuario comercial. No se ejecutará.",
    )


def build_action_visual_badge(state: DraftActionState) -> StatusVisualBadge:
    if state == DraftActionState.CREATED:
        return StatusVisualBadge(
            label="Borrador en Outlook",
            color=VisualBadgeColor.GREEN,
            icon="mail-check",
            description="Borrador depositado en 'Borradores Asistente'. Listo para revisión final y envío en Outlook.",
        )
    if state == DraftActionState.UNCERTAIN:
        return StatusVisualBadge(
            label="Advertencia: Incierto",
            color=VisualBadgeColor.WARNING,
            icon="alert-triangle",
            description="Interrupción de red durante el guardado. Prohibido reintentar sin reconciliación previa.",
        )
    if state == DraftActionState.SUBMITTING:
        return StatusVisualBadge(
            label="Guardando en Buzón...",
            color=VisualBadgeColor.BLUE,
            icon="loader",
            description="Transmitiendo mensaje mediante IMAP APPEND seguro.",
        )
    if state == DraftActionState.FAILED_RETRYABLE:
        return StatusVisualBadge(
            label="Fallo Temporal",
            color=VisualBadgeColor.AMBER,
            icon="refresh-cw",
            description="Error de conexión temporal. El reintento seguro está habilitado.",
        )
    return StatusVisualBadge(
        label="Error Terminal",
        color=VisualBadgeColor.RED,
        icon="alert-octagon",
        description="Error no recuperable del servidor IMAP o buzón inexistente.",
    )


def _map_proposal_to_dto(proposal, action: Optional[EmailDraftAction]) -> DraftProposalRead:
    badge = build_proposal_visual_badge(proposal.status)
    return DraftProposalRead(
        id=proposal.id,
        source_message_id=proposal.source_message_id,
        subject=proposal.subject,
        from_address=proposal.from_address,
        to_address=proposal.to_address,
        body=proposal.body,
        status=proposal.status,
        created_at=proposal.created_at,
        current_action_id=action.id if action else None,
        current_action_state=action.state if action else None,
        visual_badge=badge,
    )


def _map_action_to_dto(action: EmailDraftAction) -> DraftActionRead:
    badge = build_action_visual_badge(action.state)
    return DraftActionRead(
        id=action.id,
        proposal_id=action.proposal_id,
        state=action.state,
        mailbox_folder=action.mailbox_folder,
        imap_uid=action.imap_uid,
        error_message=action.error_message,
        retry_count=action.retry_count,
        created_at=action.created_at,
        updated_at=action.updated_at,
        can_retry=action.can_retry,
        is_uncertain=action.is_uncertain,
        is_terminal=action.is_terminal,
        visual_badge=badge,
    )


@router.get("/proposals", response_model=List[DraftProposalRead])
def list_proposals(
    status_filter: Optional[ProposalStatus] = Query(None, alias="status"),
    repo: DraftRepository = Depends(get_draft_repository),
) -> List[DraftProposalRead]:
    """Lista las propuestas de borrador con filtro opcional de estado y badges visuales."""
    proposals = repo.list_proposals(status_filter)
    result = []
    for prop in proposals:
        action = repo.get_action(prop.current_action_id) if prop.current_action_id else None
        result.append(_map_proposal_to_dto(prop, action))
    return result


@router.get("/proposals/{proposal_id}", response_model=DraftProposalRead)
def get_proposal(
    proposal_id: str,
    repo: DraftRepository = Depends(get_draft_repository),
) -> DraftProposalRead:
    """Obtiene el detalle de una propuesta específica con su badge visual."""
    proposal = repo.get_proposal(proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Propuesta '{proposal_id}' no encontrada.",
        )
    action = repo.get_action(proposal.current_action_id) if proposal.current_action_id else None
    return _map_proposal_to_dto(proposal, action)


@router.post("/proposals/{proposal_id}/review", response_model=DraftProposalRead)
def review_proposal(
    proposal_id: str,
    request: DraftReviewRequest,
    repo: DraftRepository = Depends(get_draft_repository),
) -> DraftProposalRead:
    """Registra la revisión humana (aceptar o rechazar) de una propuesta."""
    proposal = repo.get_proposal(proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Propuesta '{proposal_id}' no encontrada.",
        )

    if proposal.status != ProposalStatus.NOT_REVIEWED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La propuesta ya fue revisada con estado '{proposal.status.value}'.",
        )

    proposal.status = (
        ProposalStatus.ACCEPTED if request.decision == "accepted" else ProposalStatus.REJECTED
    )
    proposal.reviewed_by = request.reviewer
    from datetime import datetime, timezone
    proposal.reviewed_at = datetime.now(timezone.utc)
    repo.save_proposal(proposal)

    action = repo.get_action(proposal.current_action_id) if proposal.current_action_id else None
    return _map_proposal_to_dto(proposal, action)


@router.post("/proposals/{proposal_id}/submit", response_model=DraftActionRead)
def submit_draft_action(
    proposal_id: str,
    repo: DraftRepository = Depends(get_draft_repository),
    appender: ImapDraftAppender = Depends(get_imap_appender),
    imap_client: IMAPClientProtocol = Depends(get_imap_client),
) -> DraftActionRead:
    """Dispara la ejecución del depósito de borrador vía IMAP APPEND."""
    proposal = repo.get_proposal(proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Propuesta '{proposal_id}' no encontrada.",
        )

    if proposal.status != ProposalStatus.ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden materializar borradores de propuestas aceptadas.",
        )

    action: Optional[EmailDraftAction] = None
    if proposal.current_action_id:
        action = repo.get_action(proposal.current_action_id)

    if action:
        # Idempotencia: si ya está creado, retornamos sin duplicar en buzón
        if action.state == DraftActionState.CREATED:
            return _map_action_to_dto(action)

        # Si está en incertidumbre, prohibir reintento ciego
        if action.state == DraftActionState.UNCERTAIN:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La acción está en estado UNCERTAIN. Debe ejecutarse reconciliación antes de reintentar.",
            )

        if not action.can_retry:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La acción no puede ser ejecutada en su estado actual ({action.state.value}).",
            )
    else:
        action = EmailDraftAction(
            proposal_id=proposal.id,
            rfc822_payload=proposal.raw_rfc822,
        )
        repo.save_action(action)
        proposal.current_action_id = action.id
        repo.save_proposal(proposal)

    appender.append_draft(action, imap_client)
    repo.save_action(action)

    return _map_action_to_dto(action)


@router.get("/actions/{action_id}", response_model=DraftActionRead)
def get_action_status(
    action_id: str,
    repo: DraftRepository = Depends(get_draft_repository),
) -> DraftActionRead:
    """Consulta el estado técnico de una acción de borrador con metadatos visuales."""
    action = repo.get_action(action_id)
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Acción '{action_id}' no encontrada.",
        )
    return _map_action_to_dto(action)


@router.post("/actions/{action_id}/reconcile", response_model=DraftActionRead)
def reconcile_draft_action(
    action_id: str,
    repo: DraftRepository = Depends(get_draft_repository),
    appender: ImapDraftAppender = Depends(get_imap_appender),
    imap_client: IMAPClientProtocol = Depends(get_imap_client),
) -> DraftActionRead:
    """Reconcilia de forma segura en modo solo lectura una acción en estado UNCERTAIN."""
    action = repo.get_action(action_id)
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Acción '{action_id}' no encontrada.",
        )

    if action.state != DraftActionState.UNCERTAIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Solo se pueden reconciliar acciones en estado UNCERTAIN. Estado actual: {action.state.value}.",
        )

    appender.reconcile_uncertain(action, imap_client)
    repo.save_action(action)

    return _map_action_to_dto(action)
