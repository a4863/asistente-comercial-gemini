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


def test_e2e_full_commercial_pipeline(clean_environment: MockIMAPClient) -> None:
    r"""Flujo E2E Completo:

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

    # ---------------------------------------------------------------------
    # PASO 1: Ingesta simulada de correo entrante (IMAP read-only)
    # ---------------------------------------------------------------------
    incoming_source_message_id = "<msg-2026-comercial-456@cliente-industrial.es>"
    incoming_subject = "Peticion oferta bomba de calor VRF para oficinas"
    incoming_from = "compras@cliente-industrial.es"
    incoming_body = "Estimados senores de ACLIMAR,\nSolicitamos oferta para instalacion de bomba de calor."

    # ---------------------------------------------------------------------
    # PASO 2: Extractor / Pipeline IA genera propuesta RFC 822 determinista
    # ---------------------------------------------------------------------
    # Construcción determinista del snapshot RFC 822 con prefijo Re: único y referencia In-Reply-To
    msg = email.message.EmailMessage(policy=email.policy.default)
    msg["Message-ID"] = email.utils.make_msgid(domain="aclimar.es")
    msg["In-Reply-To"] = incoming_source_message_id
    msg["References"] = incoming_source_message_id
    msg["Subject"] = f"Re: {incoming_subject}"
    msg["From"] = "comercial@aclimar.es"
    msg["To"] = incoming_from
    msg["Date"] = email.utils.format_datetime(datetime.now(timezone.utc))
    msg.set_content(
        "Estimados señores,\n\n"
        "Acusamos recibo de su solicitud para la instalación de bomba de calor VRF.\n"
        "Adjuntamos el presupuesto comercial detallado.\n\n"
        "Atentamente,\nACLIMAR Climatización"
    )
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

    # Verificar que el cockpit puede listar la propuesta en estado not_reviewed
    list_resp = client.get("/api/drafts/proposals?status=not_reviewed")
    assert list_resp.status_code == 200
    proposals = list_resp.json()
    assert len(proposals) == 1
    assert proposals[0]["id"] == "prop-pipeline-2026"
    assert proposals[0]["status"] == "not_reviewed"

    # ---------------------------------------------------------------------
    # PASO 3: Intento de submit prematuro sin revisión humana (debe fallar)
    # ---------------------------------------------------------------------
    pre_review_submit = client.post("/api/drafts/proposals/prop-pipeline-2026/submit")
    assert pre_review_submit.status_code == 400
    assert "Solo se pueden materializar borradores de propuestas aceptadas" in pre_review_submit.json()["detail"]
    assert len(mock_imap.append_calls) == 0

    # ---------------------------------------------------------------------
    # PASO 4: Revisión humana: Aprobación expresa (accepted)
    # ---------------------------------------------------------------------
    review_resp = client.post(
        "/api/drafts/proposals/prop-pipeline-2026/review",
        json={"decision": "accepted", "reviewer": "Alex Comercial"},
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["status"] == "accepted"

    # ---------------------------------------------------------------------
    # PASO 5: Materialización y ejecución de borrador vía IMAP APPEND
    # ---------------------------------------------------------------------
    mock_imap.append_response = ("OK", [b"[APPENDUID 20260408 8844] Append completed."])

    submit_resp = client.post("/api/drafts/proposals/prop-pipeline-2026/submit")
    assert submit_resp.status_code == 200
    action_dto = submit_resp.json()

    assert action_dto["state"] == DraftActionState.CREATED.value
    assert action_dto["imap_uid"] == "8844"
    assert action_dto["mailbox_folder"] == DRAFTS_FOLDER_TARGET
    assert action_dto["is_terminal"] is True
    assert action_dto["can_retry"] is False

    # ---------------------------------------------------------------------
    # PASO 6: Verificación de invariantes en el comando IMAP APPEND
    # ---------------------------------------------------------------------
    assert len(mock_imap.append_calls) == 1
    append_call = mock_imap.append_calls[0]
    assert append_call["mailbox"] == f'"{DRAFTS_FOLDER_TARGET}"'
    assert append_call["flags"] == r"(\Draft)"

    # Verificar que el mensaje enviado contiene la cabecera de idempotencia y trazabilidad
    appended_email = email.message_from_bytes(append_call["message"], policy=email.policy.default)
    assert IDEMPOTENCY_HEADER in appended_email
    assert appended_email["In-Reply-To"] == incoming_source_message_id
    assert appended_email["Subject"] == "Re: Peticion oferta bomba de calor VRF para oficinas"

    # ---------------------------------------------------------------------
    # PASO 7: Verificación de consulta y trazabilidad
    # ---------------------------------------------------------------------
    action_id = action_dto["id"]
    query_action = client.get(f"/api/drafts/actions/{action_id}")
    assert query_action.status_code == 200
    assert query_action.json()["state"] == "created"
    assert query_action.json()["imap_uid"] == "8844"


def test_e2e_pipeline_uncertainty_and_reconciliation(clean_environment: MockIMAPClient) -> None:
    """Flujo E2E de Incertidumbre y Reconciliación:

    1. Propuesta aceptada se envía con timeout de red durante APPEND -> UNCERTAIN.
    2. Intento de reintento ciego -> bloqueado con 409 Conflict.
    3. Reconciliación read-only positiva -> CREATED.
    """
    mock_imap = clean_environment
    repo = get_draft_repository()

    proposal = EmailDraftProposalEntity(
        id="prop-uncertain-flow",
        source_message_id="<msg-timeout-test@empresa.com>",
        subject="Re: Presupuesto climatización",
        from_address="comercial@aclimar.es",
        to_address="contacto@empresa.com",
        body="Adjunto presupuesto.",
        raw_rfc822=b"Subject: Re: Presupuesto\n\nCuerpo",
        status=ProposalStatus.ACCEPTED,
    )
    repo.save_proposal(proposal)

    # Simular caída de socket en APPEND
    mock_imap.append_side_effect = socket.timeout("Socket timeout esperando respuesta")

    submit_resp = client.post("/api/drafts/proposals/prop-uncertain-flow/submit")
    assert submit_resp.status_code == 200
    action_data = submit_resp.json()
    assert action_data["state"] == DraftActionState.UNCERTAIN.value
    assert action_data["is_uncertain"] is True
    action_id = action_data["id"]

    # Reintento ciego bloqueado
    blind_retry = client.post("/api/drafts/proposals/prop-uncertain-flow/submit")
    assert blind_retry.status_code == 409
    assert "estado UNCERTAIN" in blind_retry.json()["detail"]

    # Reconciliación en modo solo lectura
    mock_imap.search_response = ("OK", [b"9911"])
    recon_resp = client.post(f"/api/drafts/actions/{action_id}/reconcile")
    assert recon_resp.status_code == 200
    assert recon_resp.json()["state"] == DraftActionState.CREATED.value
    assert recon_resp.json()["imap_uid"] == "9911"
    assert mock_imap.select_calls[-1]["readonly"] is True
