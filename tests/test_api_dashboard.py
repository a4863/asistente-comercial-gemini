from __future__ import annotations

import socket
import pytest
from fastapi.testclient import TestClient

from src.api.drafts_router import get_draft_repository, set_imap_client_override
from src.domain.draft_action import DraftActionState, EmailDraftAction
from src.main import app
from src.repositories.draft_repository import EmailDraftProposalEntity
from src.schemas.draft_schemas import ProposalStatus, VisualBadgeColor
from tests.test_imap_draft_service import MockIMAPClient, SAMPLE_RAW_RFC822

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_repo():
    repo = get_draft_repository()
    repo._proposals.clear()
    repo._actions.clear()

    mock_client = MockIMAPClient()
    set_imap_client_override(mock_client)
    yield mock_client
    set_imap_client_override(None)


def test_dashboard_summary_empty() -> None:
    resp = client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()

    assert data["unreviewed_proposals_count"] == 0
    assert data["accepted_proposals_count"] == 0
    assert data["drafts_created_count"] == 0
    assert data["uncertain_actions_count"] == 0
    assert data["alerts"] == []


def test_dashboard_summary_with_unreviewed_proposals() -> None:
    repo = get_draft_repository()
    prop = EmailDraftProposalEntity(
        id="prop-dash-1",
        source_message_id="<msg-1@empresa.com>",
        subject="Peticion oferta",
        from_address="comercial@aclimar.es",
        to_address="cliente@empresa.com",
        body="Cuerpo",
        raw_rfc822=SAMPLE_RAW_RFC822,
        status=ProposalStatus.NOT_REVIEWED,
    )
    repo.save_proposal(prop)

    resp = client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()

    assert data["unreviewed_proposals_count"] == 1
    assert len(data["alerts"]) == 1
    alert = data["alerts"][0]
    assert alert["alert_type"] == "pending_review"
    assert alert["visual_badge"]["color"] == VisualBadgeColor.AMBER.value


def test_dashboard_summary_uncertain_warning_alert(clean_repo: MockIMAPClient) -> None:
    """Verifica que el dashboard renderice de forma prominente la alerta visual de UNCERTAIN."""
    mock_imap = clean_repo
    repo = get_draft_repository()

    prop = EmailDraftProposalEntity(
        id="prop-timeout-dash",
        source_message_id="<msg-timeout@empresa.com>",
        subject="Re: Oferta",
        from_address="comercial@aclimar.es",
        to_address="cliente@empresa.com",
        body="Cuerpo",
        raw_rfc822=SAMPLE_RAW_RFC822,
        status=ProposalStatus.ACCEPTED,
    )
    repo.save_proposal(prop)

    # Forzar timeout para generar acción en UNCERTAIN
    mock_imap.append_side_effect = socket.timeout("Socket timeout durante APPEND")
    client.post("/api/drafts/proposals/prop-timeout-dash/submit")

    # Consultar dashboard
    resp = client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()

    assert data["uncertain_actions_count"] == 1
    assert len(data["alerts"]) >= 1

    uncertain_alert = next((a for a in data["alerts"] if a["alert_type"] == "uncertain_draft"), None)
    assert uncertain_alert is not None
    assert uncertain_alert["visual_badge"]["color"] == VisualBadgeColor.WARNING.value
    assert uncertain_alert["visual_badge"]["icon"] == "alert-triangle"
    assert "reconcile" in uncertain_alert["action_endpoint"]
    assert uncertain_alert["action_label"] == "Verificar en Servidor"


def test_proposal_and_action_visual_badge_rendering() -> None:
    """Verifica que los endpoints de propuestas y acciones incluyan sus badges visuales."""
    repo = get_draft_repository()
    prop = EmailDraftProposalEntity(
        id="prop-badge-test",
        source_message_id="<msg-badge@empresa.com>",
        subject="Oferta bombas",
        from_address="comercial@aclimar.es",
        to_address="cliente@empresa.com",
        body="Cuerpo",
        raw_rfc822=SAMPLE_RAW_RFC822,
        status=ProposalStatus.NOT_REVIEWED,
    )
    repo.save_proposal(prop)

    # Detalle de propuesta
    resp = client.get("/api/drafts/proposals/prop-badge-test")
    assert resp.status_code == 200
    prop_data = resp.json()
    assert prop_data["visual_badge"]["color"] == "amber"
    assert prop_data["visual_badge"]["label"] == "Pendiente de Revisión"

    # Revisar y aceptar
    client.post(
        "/api/drafts/proposals/prop-badge-test/review",
        json={"decision": "accepted", "reviewer": "Alex Comercial"},
    )
    resp_accepted = client.get("/api/drafts/proposals/prop-badge-test")
    assert resp_accepted.json()["visual_badge"]["color"] == "green"
    assert resp_accepted.json()["visual_badge"]["label"] == "Propuesta Aceptada"
