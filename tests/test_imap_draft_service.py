from __future__ import annotations

import email
import email.policy
import imaplib
import socket
import pytest

from src.domain.draft_action import (
    DraftActionState,
    EmailDraftAction,
    InvalidStateTransitionError,
)
from src.services.imap_draft_service import (
    DRAFTS_FOLDER_TARGET,
    IDEMPOTENCY_HEADER,
    ImapDraftAppender,
    format_mailbox_for_command,
)


class MockIMAPClient:
    """Doble de prueba seguro para simular el protocolo IMAP sin conexión externa."""

    def __init__(self) -> None:
        self.append_calls: list[dict] = []
        self.select_calls: list[dict] = []
        self.search_calls: list[dict] = []

        self.append_response: tuple[str, list[bytes]] = ("OK", [b"[APPENDUID 1234567890 9876] Append completed."])
        self.append_side_effect: Exception | None = None

        self.select_response: tuple[str, list[bytes]] = ("OK", [b"10"])
        self.select_side_effect: Exception | None = None

        self.search_response: tuple[str, list[bytes]] = ("OK", [b"9876"])
        self.search_side_effect: Exception | None = None

    def append(self, mailbox: str, flags: str, date_time: str, message: bytes) -> tuple[str, list[bytes]]:
        self.append_calls.append({
            "mailbox": mailbox,
            "flags": flags,
            "date_time": date_time,
            "message": message,
        })
        if self.append_side_effect:
            raise self.append_side_effect
        return self.append_response

    def select(self, mailbox: str = "INBOX", readonly: bool = False) -> tuple[str, list[bytes]]:
        self.select_calls.append({"mailbox": mailbox, "readonly": readonly})
        if self.select_side_effect:
            raise self.select_side_effect
        return self.select_response

    def search(self, charset: str | None, *criteria: str) -> tuple[str, list[bytes]]:
        self.search_calls.append({"charset": charset, "criteria": criteria})
        if self.search_side_effect:
            raise self.search_side_effect
        return self.search_response


SAMPLE_RAW_RFC822 = b"Subject: Presupuesto Climatizacion\nFrom: comercial@aclimar.es\nTo: cliente@empresa.com\n\nEstimado cliente,\nAdjunto presupuesto."


# =========================================================================
# 1. Pruebas de la Máquina de Estados y el Modelo EmailDraftAction
# =========================================================================

def test_email_draft_action_init_validation() -> None:
    action = EmailDraftAction(
        proposal_id="prop-123",
        rfc822_payload=SAMPLE_RAW_RFC822,
    )
    assert action.proposal_id == "prop-123"
    assert action.state == DraftActionState.SUBMITTING
    assert action.mailbox_folder == DRAFTS_FOLDER_TARGET
    assert not action.is_terminal
    assert not action.is_uncertain
    assert not action.can_retry


def test_email_draft_action_invalid_init_payload() -> None:
    with pytest.raises(ValueError, match="proposal_id no puede estar vacío"):
        EmailDraftAction(proposal_id="", rfc822_payload=SAMPLE_RAW_RFC822)

    with pytest.raises(ValueError, match="rfc822_payload debe ser una secuencia de bytes no vacía"):
        EmailDraftAction(proposal_id="prop-123", rfc822_payload=b"")


def test_illegal_state_transition_from_submitting() -> None:
    action = EmailDraftAction(proposal_id="prop-123", rfc822_payload=SAMPLE_RAW_RFC822)
    # Transición directa ilegal: no puede pasar de SUBMITTING a SUBMITTING sin pasar antes por FAILED_RETRYABLE
    with pytest.raises(InvalidStateTransitionError):
        action.transition_to(DraftActionState.SUBMITTING)


def test_uncertain_state_prohibits_blind_retry() -> None:
    action = EmailDraftAction(proposal_id="prop-123", rfc822_payload=SAMPLE_RAW_RFC822)
    action.transition_to(DraftActionState.UNCERTAIN)

    assert action.is_uncertain
    assert not action.can_retry

    # Intentar enviar directamente en UNCERTAIN debe ser rechazado
    with pytest.raises(InvalidStateTransitionError, match="No se permite reintento automático ciego"):
        action.assert_can_submit()

    # Transición ilegal directa de UNCERTAIN a SUBMITTING
    with pytest.raises(InvalidStateTransitionError):
        action.transition_to(DraftActionState.SUBMITTING)


# =========================================================================
# 2. Pruebas del Servicio ImapDraftAppender
# =========================================================================

def test_format_mailbox_for_command() -> None:
    formatted = format_mailbox_for_command(DRAFTS_FOLDER_TARGET)
    assert formatted == f'"{DRAFTS_FOLDER_TARGET}"'
    assert format_mailbox_for_command('"INBOX.Drafts"') == '"INBOX.Drafts"'


def test_prepare_payload_injects_idempotency_header_and_date() -> None:
    appender = ImapDraftAppender()
    action = EmailDraftAction(proposal_id="prop-001", rfc822_payload=SAMPLE_RAW_RFC822)

    prepared = appender.prepare_payload_with_idempotency(action)
    parsed = email.message_from_bytes(prepared, policy=email.policy.default)

    assert parsed[IDEMPOTENCY_HEADER] == action.idempotency_token
    assert parsed["Date"] is not None
    assert parsed["Subject"] == "Presupuesto Climatizacion"


def test_append_draft_success() -> None:
    appender = ImapDraftAppender()
    client = MockIMAPClient()
    action = EmailDraftAction(proposal_id="prop-001", rfc822_payload=SAMPLE_RAW_RFC822)

    result = appender.append_draft(action, client)

    assert result.state == DraftActionState.CREATED
    assert result.imap_uid == "9876"
    assert result.is_terminal
    assert len(client.append_calls) == 1

    call = client.append_calls[0]
    assert call["mailbox"] == f'"{DRAFTS_FOLDER_TARGET}"'
    assert call["flags"] == r"(\Draft)"
    assert IDEMPOTENCY_HEADER.encode() in call["message"]


def test_append_draft_network_timeout_transitions_to_uncertain() -> None:
    appender = ImapDraftAppender()
    client = MockIMAPClient()
    client.append_side_effect = socket.timeout("Conexión expirada esperando respuesta del servidor IMAP")

    action = EmailDraftAction(proposal_id="prop-001", rfc822_payload=SAMPLE_RAW_RFC822)
    result = appender.append_draft(action, client)

    assert result.state == DraftActionState.UNCERTAIN
    assert result.is_uncertain
    assert not result.can_retry
    assert "Interrupción de red durante APPEND" in (result.error_message or "")

    # Reintento directo debe estar prohibido
    with pytest.raises(InvalidStateTransitionError):
        appender.append_draft(result, client)


def test_append_draft_connection_reset_transitions_to_uncertain() -> None:
    appender = ImapDraftAppender()
    client = MockIMAPClient()
    client.append_side_effect = ConnectionResetError("Servidor cerró el socket abruptamente")

    action = EmailDraftAction(proposal_id="prop-001", rfc822_payload=SAMPLE_RAW_RFC822)
    result = appender.append_draft(action, client)

    assert result.state == DraftActionState.UNCERTAIN
    assert result.is_uncertain


def test_append_draft_pre_socket_error_transitions_to_failed_retryable() -> None:
    appender = ImapDraftAppender()
    client = MockIMAPClient()
    client.append_side_effect = ConnectionRefusedError("No se pudo contactar el host IMAP")

    action = EmailDraftAction(proposal_id="prop-001", rfc822_payload=SAMPLE_RAW_RFC822)
    result = appender.append_draft(action, client)

    assert result.state == DraftActionState.FAILED_RETRYABLE
    assert result.can_retry
    assert "Error transitorio de conexión" in (result.error_message or "")


def test_append_draft_imap_protocol_error_transitions_to_failed_terminal() -> None:
    appender = ImapDraftAppender()
    client = MockIMAPClient()
    client.append_side_effect = imaplib.IMAP4.error("Mailbox does not exist or permission denied")

    action = EmailDraftAction(proposal_id="prop-001", rfc822_payload=SAMPLE_RAW_RFC822)
    result = appender.append_draft(action, client)

    assert result.state == DraftActionState.FAILED_TERMINAL
    assert result.is_terminal
    assert not result.can_retry


# =========================================================================
# 3. Pruebas del Protocolo de Reconciliación de Estado UNCERTAIN
# =========================================================================

def test_reconcile_uncertain_found_remote_resolves_to_created() -> None:
    appender = ImapDraftAppender()
    client = MockIMAPClient()
    client.search_response = ("OK", [b"1001 1002"])

    action = EmailDraftAction(proposal_id="prop-001", rfc822_payload=SAMPLE_RAW_RFC822)
    action.transition_to(DraftActionState.UNCERTAIN)

    result = appender.reconcile_uncertain(action, client)

    assert result.state == DraftActionState.CREATED
    assert result.imap_uid == "1002"
    assert result.is_terminal

    # Verificar que select se ejecutó estrictamente en modo readonly
    assert len(client.select_calls) == 1
    assert client.select_calls[0]["readonly"] is True
    assert client.select_calls[0]["mailbox"] == f'"{DRAFTS_FOLDER_TARGET}"'


def test_reconcile_uncertain_not_found_remote_resolves_to_failed_retryable() -> None:
    appender = ImapDraftAppender()
    client = MockIMAPClient()
    # Búsqueda OK pero vacía: confirma positivamente que el borrador no existe remotamente
    client.search_response = ("OK", [b""])

    action = EmailDraftAction(proposal_id="prop-001", rfc822_payload=SAMPLE_RAW_RFC822)
    action.transition_to(DraftActionState.UNCERTAIN)

    result = appender.reconcile_uncertain(action, client)

    assert result.state == DraftActionState.FAILED_RETRYABLE
    assert result.can_retry
    assert result.imap_uid is None

    # Ahora sí se permite reintentar el append
    client.append_side_effect = None
    client.append_response = ("OK", [b"[APPENDUID 1234567890 5555] Append completed."])
    retry_result = appender.append_draft(result, client)

    assert retry_result.state == DraftActionState.CREATED
    assert retry_result.imap_uid == "5555"
    assert retry_result.retry_count == 1


def test_reconcile_uncertain_failure_during_search_remains_uncertain() -> None:
    appender = ImapDraftAppender()
    client = MockIMAPClient()
    client.search_side_effect = socket.timeout("Timeout durante búsqueda de reconciliación")

    action = EmailDraftAction(proposal_id="prop-001", rfc822_payload=SAMPLE_RAW_RFC822)
    action.transition_to(DraftActionState.UNCERTAIN)

    result = appender.reconcile_uncertain(action, client)

    # Debe permanecer estrictamente en UNCERTAIN para evitar reintentos ciegos
    assert result.state == DraftActionState.UNCERTAIN
    assert result.is_uncertain
    assert not result.can_retry
    assert "Fallo durante intento de reconciliación" in (result.error_message or "")
