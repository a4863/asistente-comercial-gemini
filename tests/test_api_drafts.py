from __future__ import annotations

import socket
import pytest
from fastapi.testclient import TestClient

from src.api.drafts_router import get_draft_repository, set_imap_client_override
from src.domain.draft_action import DraftActionState
from src.main import app
from src.repositories.draft_repository import DraftRepository, EmailDraftProposalEntity
from src.schemas.draft_schemas import ProposalStatus
from tests.test_imap_draft_service import MockIMAPClient, SAMPLE_RAW_RFC822

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Configura el entorno de pruebas reseteando el repositorio e inyectando mock IMAP."""
    repo = get_draft_repository()
    repo._proposals.clear()
    repo._actions.clear()

    mock_client = MockIMAPClient()
    set_imap_client_override(mock_client)
    yield mock_client
    set_imap_client_override(None)


def _create_sample_proposal(
    prop_id: str = "prop-1",
    status: ProposalStatus = ProposalStatus.NOT_REVIEWED,
) -> EmailDraftProposalEntity:
    repo = get_draft_repository()
    entity = EmailDraftProposalEntity(
        id=prop_id,
        source_message_id="<msg-001@cliente.com>",
        subject="Re: Oferta bomba de calor",
        from_address="comercial@aclimar.es",
        to_address="cliente@empresa.com",
        body="Adjunto presupuesto solicitado.",
        raw_rfc822=SAMPLE_RAW_RFC822,
        status=status,
    )
    return repo.save_proposal(entity)


def test_health_check() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "bind": "127.0.0.1"}


def test_list_and_get_proposals() -> None:
    _create_sample_proposal("prop-1", ProposalStatus.NOT_REVIEWED)
    _create_sample_proposal("prop-2", ProposalStatus.ACCEPTED)

    # Listar todos
    resp = client.get("/api/drafts/proposals")
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    # Filtrar por status
    resp_filtered = client.get("/api/drafts/proposals?status=accepted")
    assert resp_filtered.status_code == 200
    assert len(resp_filtered.json()) == 1
    assert resp_filtered.json()[0]["id"] == "prop-2"

    # Obtener detalle y comprobar allowed_ui_actions
    resp_detail = client.get("/api/drafts/proposals/prop-1")
    assert resp_detail.status_code == 200
    assert resp_detail.json()["id"] == "prop-1"
    assert resp_detail.json()["status"] == "not_reviewed"
    assert "accept" in resp_detail.json()["allowed_ui_actions"]
    assert "reject" in resp_detail.json()["allowed_ui_actions"]
    assert "edit" in resp_detail.json()["allowed_ui_actions"]


def test_review_proposal_workflow() -> None:
    _create_sample_proposal("prop-rev", ProposalStatus.NOT_REVIEWED)

    # Aceptar propuesta
    resp = client.post(
        "/api/drafts/proposals/prop-rev/review",
        json={"decision": "accepted", "reviewer": "Alex Comercial"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"
    assert "submit_to_mailbox" in resp.json()["allowed_ui_actions"]

    # Intento de re-revisión debe fallar con 400
    resp_dup = client.post(
        "/api/drafts/proposals/prop-rev/review",
        json={"decision": "rejected", "reviewer": "Alex Comercial"},
    )
    assert resp_dup.status_code == 400


def test_edit_proposal_creates_new_revision_and_resets_review() -> None:
    """Verifica que 'Editar' cree una nueva revisión append-only y regrese a not_reviewed."""
    _create_sample_proposal("prop-edit-test", ProposalStatus.NOT_REVIEWED)

    # El comercial edita la propuesta
    resp_edit = client.post(
        "/api/drafts/proposals/prop-edit-test/edit",
        json={
            "subject": "Oferta bomba de calor VRF con descuento 10%",
            "body": "Adjunto presupuesto actualizado con descuento especial del 10%.",
            "editor": "Alex Comercial",
        },
    )
    assert resp_edit.status_code == 200
    data = resp_edit.json()
    assert data["current_version"] == 2
    assert len(data["revisions"]) == 2
    assert data["status"] == "not_reviewed"
    assert data["subject"] == "Oferta bomba de calor VRF con descuento 10%"
    assert data["revisions"][0]["version"] == 1
    assert data["revisions"][1]["version"] == 2
    assert data["revisions"][1]["author"] == "Alex Comercial"

    # La propuesta puede aceptarse ahora con su nueva versión
    resp_accept = client.post(
        "/api/drafts/proposals/prop-edit-test/review",
        json={"decision": "accepted", "reviewer": "Alex Comercial"},
    )
    assert resp_accept.status_code == 200
    assert resp_accept.json()["status"] == "accepted"


def test_submit_draft_action_requires_accepted_status(setup_test_environment) -> None:
    _create_sample_proposal("prop-unreviewed", ProposalStatus.NOT_REVIEWED)

    # Intento de submit sin aceptar primero
    resp = client.post("/api/drafts/proposals/prop-unreviewed/submit")
    assert resp.status_code == 400
    assert "Solo se pueden materializar borradores de propuestas aceptadas" in resp.json()["detail"]


def test_submit_draft_action_success_and_idempotency(setup_test_environment) -> None:
    mock_imap = setup_test_environment
    mock_imap.append_response = ("OK", [b"[APPENDUID 8888 9999] Draft created."])

    _create_sample_proposal("prop-ok", ProposalStatus.ACCEPTED)

    # Primer submit
    resp = client.post("/api/drafts/proposals/prop-ok/submit")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "created"
    assert data["imap_uid"] == "9999"
    assert len(mock_imap.append_calls) == 1

    action_id = data["id"]

    # Segundo submit (idempotencia)
    resp_repeat = client.post("/api/drafts/proposals/prop-ok/submit")
    assert resp_repeat.status_code == 200
    assert resp_repeat.json()["id"] == action_id
    assert resp_repeat.json()["state"] == "created"
    # No debe haber hecho una segunda llamada APPEND
    assert len(mock_imap.append_calls) == 1


def test_submit_draft_action_uncertain_and_reject_blind_retry(setup_test_environment) -> None:
    mock_imap = setup_test_environment
    mock_imap.append_side_effect = socket.timeout("Socket timeout durante APPEND")

    _create_sample_proposal("prop-timeout", ProposalStatus.ACCEPTED)

    # Iniciar submit que termina en UNCERTAIN
    resp = client.post("/api/drafts/proposals/prop-timeout/submit")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "uncertain"
    assert data["is_uncertain"] is True
    assert "reconcile" in data["allowed_ui_actions"]
    action_id = data["id"]

    # Intento de submit repetido directo a ciegas debe retornar 409 Conflict
    resp_conflict = client.post("/api/drafts/proposals/prop-timeout/submit")
    assert resp_conflict.status_code == 409
    assert "estado UNCERTAIN" in resp_conflict.json()["detail"]

    # Ejecutar reconciliación positiva
    mock_imap.search_response = ("OK", [b"4321"])
    resp_recon = client.post(f"/api/drafts/actions/{action_id}/reconcile")
    assert resp_recon.status_code == 200
    recon_data = resp_recon.json()
    assert recon_data["state"] == "created"
    assert recon_data["imap_uid"] == "4321"


def test_reconcile_when_not_uncertain_returns_400(setup_test_environment) -> None:
    mock_imap = setup_test_environment
    mock_imap.append_response = ("OK", [b"[APPENDUID 111 222]"])

    _create_sample_proposal("prop-ready", ProposalStatus.ACCEPTED)
    resp_submit = client.post("/api/drafts/proposals/prop-ready/submit")
    action_id = resp_submit.json()["id"]

    # Reconciliar una acción en estado CREATED debe fallar con 400
    resp_recon = client.post(f"/api/drafts/actions/{action_id}/reconcile")
    assert resp_recon.status_code == 400
    assert "Solo se pueden reconciliar acciones en estado UNCERTAIN" in resp_recon.json()["detail"]


def test_submit_blocked_on_uncertain_until_reconciled(setup_test_environment) -> None:
    """Verifica que no se puede reintentar submit mientras la acción esté en UNCERTAIN."""
    mock_imap = setup_test_environment
    mock_imap.append_side_effect = socket.timeout("Fallo socket")

    _create_sample_proposal("prop-block-test", ProposalStatus.ACCEPTED)

    # Submit falla a UNCERTAIN
    resp1 = client.post("/api/drafts/proposals/prop-block-test/submit")
    assert resp1.status_code == 200
    action_id = resp1.json()["id"]
    assert resp1.json()["state"] == "uncertain"

    # Submit subsiguiente bloqueado con 409
    resp_blocked = client.post("/api/drafts/proposals/prop-block-test/submit")
    assert resp_blocked.status_code == 409

    # Reconciliación confirma ausencia -> FAILED_RETRYABLE
    mock_imap.search_response = ("OK", [b""])
    resp_recon = client.post(f"/api/drafts/actions/{action_id}/reconcile")
    assert resp_recon.status_code == 200
    assert resp_recon.json()["state"] == "failed_retryable"
    assert resp_recon.json()["can_retry"] is True

    # Ahora el submit sí está permitido como reintento
    mock_imap.append_side_effect = None
    mock_imap.append_response = ("OK", [b"[APPENDUID 1000 2000] OK"])
    resp_retry = client.post("/api/drafts/proposals/prop-block-test/submit")
    assert resp_retry.status_code == 200
    assert resp_retry.json()["state"] == "created"
    assert resp_retry.json()["imap_uid"] == "2000"
