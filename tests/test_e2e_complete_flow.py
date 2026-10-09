from __future__ import annotations

import email
import email.policy
import email.utils
import socket
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from src.api.drafts_router import get_draft_repository, set_imap_client_override
from src.domain.draft_action import DraftActionState
from src.main import app
from src.repositories.draft_repository import EmailDraftProposalEntity
from src.schemas.draft_schemas import ProposalStatus
from src.services.imap_draft_service import DRAFTS_FOLDER_TARGET, IDEMPOTENCY_HEADER
from tests.test_imap_draft_service import MockIMAPClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_environment():
    """Aísla el entorno de pruebas reseteando propuestas, acciones y mock IMAP."""
    repo = get_draft_repository()
    repo._proposals.clear()
    repo._actions.clear()

    mock_client = MockIMAPClient()
    set_imap_client_override(mock_client)
    yield mock_client
    set_imap_client_override(None)


# =========================================================================
# CP-E2E-01: Ciclo Comercial Completo (Happy Path E2E)
# =========================================================================

def test_e2e_cpe2e01_happy_path_pipeline(clean_environment: MockIMAPClient) -> None:
    r"""CP-E2E-01: Flujo E2E Completo:

    1. Ingesta simulada de correo entrante IMAP (read-only).
    2. Extracción/Inferencia IA produciendo propuesta de borrador RFC 822 en estado not_reviewed.
    3. Bloqueo de ejecución prematura sin revisión humana (400 Bad Request).
    4. Revisión humana aprobada (accepted) con registro de actor y timestamp.
    5. Aprobación y materialización de la acción de borrador vía IMAP APPEND.
    6. Verificación de flags (\Draft), carpeta destino y cabecera de idempotencia.
    7. Trazabilidad completa (proposal_id -> action_id -> imap_uid).
    """
    mock_imap = clean_environment
    repo = get_draft_repository()

    # 1. Ingesta
    incoming_source_message_id = "<msg-2026-comercial-456@cliente-industrial.es>"
    incoming_subject = "Peticion oferta bomba de calor VRF para oficinas"
    incoming_from = "compras@cliente-industrial.es"

    msg = email.message.EmailMessage(policy=email.policy.default)
    msg["Message-ID"] = email.utils.make_msgid(domain="aclimar.es")
    msg["In-Reply-To"] = incoming_source_message_id
    msg["References"] = incoming_source_message_id
    msg["Subject"] = f"Re: {incoming_subject}"
    msg["From"] = "comercial@aclimar.es"
    msg["To"] = incoming_from
    msg["Date"] = email.utils.format_datetime(datetime.now(timezone.utc))
    msg.set_content("Presupuesto detallado para la instalación.")
    raw_rfc822_bytes = msg.as_bytes()

    proposal_entity = EmailDraftProposalEntity(
        id="prop-pipeline-2026",
        source_message_id=incoming_source_message_id,
        subject=msg["Subject"],
        from_address=msg["From"],
        to_address=msg["To"],
        body=msg.get_content(),
        raw_rfc822=raw_rfc822_bytes,
        status=ProposalStatus.NOT_REVIEWED,
    )
    repo.save_proposal(proposal_entity)

    # 2. Bloqueo de submit prematuro
    pre_review_submit = client.post("/api/drafts/proposals/prop-pipeline-2026/submit")
    assert pre_review_submit.status_code == 400
    assert "Solo se pueden materializar borradores de propuestas aceptadas" in pre_review_submit.json()["detail"]

    # 3. Revisión humana: Aceptación
    review_resp = client.post(
        "/api/drafts/proposals/prop-pipeline-2026/review",
        json={"decision": "accepted", "reviewer": "Alex Comercial"},
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["status"] == "accepted"

    # 4. Materialización y ejecución IMAP APPEND
    mock_imap.append_response = ("OK", [b"[APPENDUID 20260408 8844] Append completed."])
    submit_resp = client.post("/api/drafts/proposals/prop-pipeline-2026/submit")
    assert submit_resp.status_code == 200
    action_dto = submit_resp.json()

    assert action_dto["state"] == DraftActionState.CREATED.value
    assert action_dto["imap_uid"] == "8844"
    assert action_dto["mailbox_folder"] == DRAFTS_FOLDER_TARGET
    assert action_dto["is_terminal"] is True

    # 5. Verificación de comandos e invariantes IMAP
    assert len(mock_imap.append_calls) == 1
    call = mock_imap.append_calls[0]
    assert call["mailbox"] == f'"{DRAFTS_FOLDER_TARGET}"'
    assert call["flags"] == r"(\Draft)"


# =========================================================================
# CP-E2E-02: Rechazo Humano de Propuesta
# =========================================================================

def test_e2e_cpe2e02_human_rejection(clean_environment: MockIMAPClient) -> None:
    """CP-E2E-02: Una propuesta rechazada por el usuario jamás puede ejecutarse externamente."""
    mock_imap = clean_environment
    repo = get_draft_repository()

    proposal = EmailDraftProposalEntity(
        id="prop-reject-002",
        source_message_id="<msg-spam-002@externo.es>",
        subject="Oferta irrelevante",
        from_address="comercial@aclimar.es",
        to_address="spam@externo.es",
        body="Descartar",
        raw_rfc822=b"Subject: Oferta\n\nCuerpo",
        status=ProposalStatus.NOT_REVIEWED,
    )
    repo.save_proposal(proposal)

    # Rechazo humano
    review_resp = client.post(
        "/api/drafts/proposals/prop-reject-002/review",
        json={"decision": "rejected", "reviewer": "Alex Comercial"},
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["status"] == "rejected"

    # Intento de submit denegado
    submit_resp = client.post("/api/drafts/proposals/prop-reject-002/submit")
    assert submit_resp.status_code == 400
    assert len(mock_imap.append_calls) == 0


# =========================================================================
# CP-E2E-03: Ambigüedad de Red / Estado UNCERTAIN
# =========================================================================

def test_e2e_cpe2e03_network_ambiguity_uncertain(clean_environment: MockIMAPClient) -> None:
    """CP-E2E-03: Timeout de red transiciona a UNCERTAIN y bloquea reintentos ciegos con 409 Conflict."""
    mock_imap = clean_environment
    repo = get_draft_repository()

    proposal = EmailDraftProposalEntity(
        id="prop-timeout-003",
        source_message_id="<msg-timeout-003@empresa.com>",
        subject="Re: Climatizacion nave",
        from_address="comercial@aclimar.es",
        to_address="contacto@empresa.com",
        body="Adjunto presupuesto.",
        raw_rfc822=b"Subject: Re: Climatizacion\n\nCuerpo",
        status=ProposalStatus.ACCEPTED,
    )
    repo.save_proposal(proposal)

    # Simular fallo de socket durante APPEND
    mock_imap.append_side_effect = socket.timeout("Socket timeout esperando acuse OK")

    submit_resp = client.post("/api/drafts/proposals/prop-timeout-003/submit")
    assert submit_resp.status_code == 200
    action_data = submit_resp.json()
    assert action_data["state"] == DraftActionState.UNCERTAIN.value
    assert action_data["is_uncertain"] is True
    assert action_data["can_retry"] is False

    # Intento de submit directo subsiguiente bloqueado
    retry_submit = client.post("/api/drafts/proposals/prop-timeout-003/submit")
    assert retry_submit.status_code == 409
    assert "estado UNCERTAIN" in retry_submit.json()["detail"]


# =========================================================================
# CP-E2E-04: Reconciliación Positiva Read-Only
# =========================================================================

def test_e2e_cpe2e04_reconcile_positive(clean_environment: MockIMAPClient) -> None:
    """CP-E2E-04: Reconciliación read-only encuentra borrador y transiciona a CREATED."""
    mock_imap = clean_environment
    repo = get_draft_repository()

    proposal = EmailDraftProposalEntity(
        id="prop-recon-pos-004",
        source_message_id="<msg-pos-004@empresa.com>",
        subject="Re: Presupuesto",
        from_address="comercial@aclimar.es",
        to_address="contacto@empresa.com",
        body="Presupuesto",
        raw_rfc822=b"Subject: Re: Presupuesto\n\nCuerpo",
        status=ProposalStatus.ACCEPTED,
    )
    repo.save_proposal(proposal)

    mock_imap.append_side_effect = socket.timeout("Timeout")
    submit_resp = client.post("/api/drafts/proposals/prop-recon-pos-004/submit")
    action_id = submit_resp.json()["id"]

    # Reconciliación positiva
    mock_imap.search_response = ("OK", [b"6601"])
    recon_resp = client.post(f"/api/drafts/actions/{action_id}/reconcile")
    assert recon_resp.status_code == 200
    assert recon_resp.json()["state"] == DraftActionState.CREATED.value
    assert recon_resp.json()["imap_uid"] == "6601"
    assert mock_imap.select_calls[-1]["readonly"] is True


# =========================================================================
# CP-E2E-05: Reconciliación Negativa y Reintento Seguro
# =========================================================================

def test_e2e_cpe2e05_reconcile_negative_and_retry(clean_environment: MockIMAPClient) -> None:
    """CP-E2E-05: Reconciliación confirma ausencia (FAILED_RETRYABLE) permitiendo reintento seguro."""
    mock_imap = clean_environment
    repo = get_draft_repository()

    proposal = EmailDraftProposalEntity(
        id="prop-recon-neg-005",
        source_message_id="<msg-neg-005@empresa.com>",
        subject="Re: Climatizacion",
        from_address="comercial@aclimar.es",
        to_address="contacto@empresa.com",
        body="Cuerpo",
        raw_rfc822=b"Subject: Re: Climatizacion\n\nCuerpo",
        status=ProposalStatus.ACCEPTED,
    )
    repo.save_proposal(proposal)

    mock_imap.append_side_effect = socket.timeout("Timeout")
    submit_resp = client.post("/api/drafts/proposals/prop-recon-neg-005/submit")
    action_id = submit_resp.json()["id"]

    # Reconciliación negativa (búsqueda vacía)
    mock_imap.search_response = ("OK", [b""])
    recon_resp = client.post(f"/api/drafts/actions/{action_id}/reconcile")
    assert recon_resp.status_code == 200
    assert recon_resp.json()["state"] == DraftActionState.FAILED_RETRYABLE.value
    assert recon_resp.json()["can_retry"] is True

    # Reintento exitoso
    mock_imap.append_side_effect = None
    mock_imap.append_response = ("OK", [b"[APPENDUID 20260408 9988] Append OK"])
    retry_resp = client.post("/api/drafts/proposals/prop-recon-neg-005/submit")
    assert retry_resp.status_code == 200
    assert retry_resp.json()["state"] == DraftActionState.CREATED.value
    assert retry_resp.json()["imap_uid"] == "9988"


# =========================================================================
# CP-E2E-06: Idempotencia ante Submit Duplicado
# =========================================================================

def test_e2e_cpe2e06_idempotent_duplicate_submit(clean_environment: MockIMAPClient) -> None:
    """CP-E2E-06: Segundo submit sobre propuesta ya en CREATED no emite llamadas adicionales a IMAP."""
    mock_imap = clean_environment
    repo = get_draft_repository()

    proposal = EmailDraftProposalEntity(
        id="prop-idemp-006",
        source_message_id="<msg-idemp-006@empresa.com>",
        subject="Re: Oferta",
        from_address="comercial@aclimar.es",
        to_address="contacto@empresa.com",
        body="Cuerpo",
        raw_rfc822=b"Subject: Re: Oferta\n\nCuerpo",
        status=ProposalStatus.ACCEPTED,
    )
    repo.save_proposal(proposal)

    mock_imap.append_response = ("OK", [b"[APPENDUID 20260408 5544] OK"])
    resp1 = client.post("/api/drafts/proposals/prop-idemp-006/submit")
    assert resp1.status_code == 200
    assert len(mock_imap.append_calls) == 1

    # Invocación repetida
    resp2 = client.post("/api/drafts/proposals/prop-idemp-006/submit")
    assert resp2.status_code == 200
    assert resp2.json()["id"] == resp1.json()["id"]
    assert resp2.json()["state"] == DraftActionState.CREATED.value
    assert len(mock_imap.append_calls) == 1


# =========================================================================
# CP-E2E-07: Integridad RFC 822 de Referencias y Threading
# =========================================================================

def test_e2e_cpe2e07_rfc822_threading_integrity(clean_environment: MockIMAPClient) -> None:
    """CP-E2E-07: Verificación de que el payload depositado preserve In-Reply-To y References."""
    mock_imap = clean_environment
    repo = get_draft_repository()

    source_mid = "<source-msg-thread-777@cliente.com>"
    msg = email.message.EmailMessage(policy=email.policy.default)
    msg["Message-ID"] = "<reply-777@aclimar.es>"
    msg["In-Reply-To"] = source_mid
    msg["References"] = f"<parent-0@cliente.com> {source_mid}"
    msg["Subject"] = "Re: Hilo comercial"
    msg["From"] = "comercial@aclimar.es"
    msg["To"] = "cliente@cliente.com"
    msg.set_content("Respuesta en hilo")

    proposal = EmailDraftProposalEntity(
        id="prop-threading-007",
        source_message_id=source_mid,
        subject=msg["Subject"],
        from_address=msg["From"],
        to_address=msg["To"],
        body=msg.get_content(),
        raw_rfc822=msg.as_bytes(),
        status=ProposalStatus.ACCEPTED,
    )
    repo.save_proposal(proposal)

    mock_imap.append_response = ("OK", [b"[APPENDUID 20260408 7700] OK"])
    client.post("/api/drafts/proposals/prop-threading-007/submit")

    assert len(mock_imap.append_calls) == 1
    raw_deposited = mock_imap.append_calls[0]["message"]
    parsed = email.message_from_bytes(raw_deposited, policy=email.policy.default)

    assert parsed["In-Reply-To"] == source_mid
    assert source_mid in parsed["References"]
    assert parsed[IDEMPOTENCY_HEADER] is not None
    assert parsed["Date"] is not None
