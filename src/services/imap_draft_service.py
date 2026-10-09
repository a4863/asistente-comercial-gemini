from __future__ import annotations

import email
import email.policy
import email.utils
import imaplib
import re
import socket
from datetime import datetime, timezone
from typing import Any, Protocol

from src.domain.draft_action import DraftActionState, EmailDraftAction

DRAFTS_FOLDER_TARGET = "INBOX.Drafts.Borradores Asistente"
IDEMPOTENCY_HEADER = "X-Assistant-Draft-Id"
APPENDUID_PATTERN = re.compile(r"\[APPENDUID\s+(\d+)\s+(\d+)\]", re.IGNORECASE)


def format_mailbox_for_command(folder: str) -> str:
    """Formatea y entrecomilla el nombre de la carpeta para comandos IMAP con espacios."""
    sanitized = folder.strip('"')
    return f'"{sanitized}"'


class IMAPClientProtocol(Protocol):
    def append(
        self,
        mailbox: str,
        flags: Any,
        date_time: Any,
        message: bytes,
    ) -> tuple[str, list[bytes | tuple[Any, ...]]]: ...

    def select(self, mailbox: str = ..., readonly: bool = ...) -> tuple[str, list[bytes]]: ...

    def search(self, charset: str | None, *criteria: str) -> tuple[str, list[bytes]]: ...


class ImapDraftAppender:
    """Servicio para ejecutar IMAP APPEND idempotente a la carpeta de borradores.

    Invariante: Cero SMTP. Solo interacción local/IMAP en modo append y búsqueda de reconciliación.
    """

    def __init__(self, target_folder: str = DRAFTS_FOLDER_TARGET) -> None:
        self.target_folder = target_folder

    def prepare_payload_with_idempotency(self, action: EmailDraftAction) -> bytes:
        """Asegura que el payload RFC 822 contenga la cabecera X-Assistant-Draft-Id y Date."""
        msg = email.message_from_bytes(action.rfc822_payload, policy=email.policy.default)
        if IDEMPOTENCY_HEADER not in msg:
            msg[IDEMPOTENCY_HEADER] = action.idempotency_token

        if "Date" not in msg:
            msg["Date"] = email.utils.format_datetime(datetime.now(timezone.utc))

        return msg.as_bytes()

    def append_draft(
        self,
        action: EmailDraftAction,
        imap_client: IMAPClientProtocol,
    ) -> EmailDraftAction:
        """Ejecuta el APPEND en el servidor IMAP y gestiona las transiciones de estado."""
        if action.state not in (DraftActionState.SUBMITTING, DraftActionState.FAILED_RETRYABLE):
            raise ValueError(
                f"No se puede ejecutar append_draft para una acción en estado {action.state.value}"
            )

        if action.state != DraftActionState.SUBMITTING:
            action.transition_to(DraftActionState.SUBMITTING)

        prepared_payload = self.prepare_payload_with_idempotency(action)
        folder_cmd = format_mailbox_for_command(self.target_folder)

        try:
            # Flags obligatorios: \Draft (RFC 3501)
            # En imaplib se pasa como cadena delimitada por paréntesis
            status, responses = imap_client.append(
                folder_cmd,
                r"(\Draft)",
                imaplib.Time2Internaldate(datetime.now(timezone.utc).timestamp()),
                prepared_payload,
            )

            if status == "OK":
                extracted_uid = self._extract_appenduid(responses)
                action.transition_to(
                    DraftActionState.CREATED,
                    imap_uid=extracted_uid,
                )
            else:
                resp_text = b" ".join(
                    r if isinstance(r, bytes) else str(r).encode() for r in responses
                ).decode("utf-8", errors="replace")
                action.transition_to(
                    DraftActionState.FAILED_TERMINAL,
                    error_message=f"Servidor IMAP devolvió estado no OK: {status}. Respuesta: {resp_text}",
                )

        except (socket.timeout, TimeoutError, ConnectionResetError) as err:
            action.transition_to(
                DraftActionState.UNCERTAIN,
                error_message=f"Interrupción de red durante APPEND: {type(err).__name__} - {err}",
            )
        except (socket.gaierror, ConnectionRefusedError, OSError) as err:
            action.transition_to(
                DraftActionState.FAILED_RETRYABLE,
                error_message=f"Error transitorio de conexión previo/durante socket: {type(err).__name__} - {err}",
            )
        except imaplib.IMAP4.error as err:
            action.transition_to(
                DraftActionState.FAILED_TERMINAL,
                error_message=f"Error de protocolo IMAP no recuperable: {err}",
            )
        except Exception as err:
            action.transition_to(
                DraftActionState.FAILED_TERMINAL,
                error_message=f"Error inesperado durante APPEND: {type(err).__name__} - {err}",
            )

        return action

    def reconcile_uncertain(
        self,
        action: EmailDraftAction,
        imap_client: IMAPClientProtocol,
    ) -> EmailDraftAction:
        """Reconcilia una acción en estado UNCERTAIN consultando el buzón en modo read-only."""
        if action.state != DraftActionState.UNCERTAIN:
            return action

        folder_cmd = format_mailbox_for_command(self.target_folder)

        try:
            status, _ = imap_client.select(folder_cmd, readonly=True)
            if status != "OK":
                return action

            search_criteria = f'HEADER {IDEMPOTENCY_HEADER} "{action.idempotency_token}"'
            search_status, search_data = imap_client.search(None, search_criteria)

            if search_status == "OK" and search_data and search_data[0].strip():
                uids = search_data[0].decode("ascii", errors="replace").split()
                found_uid = uids[-1] if uids else None
                action.transition_to(
                    DraftActionState.CREATED,
                    imap_uid=found_uid,
                )
            else:
                action.transition_to(
                    DraftActionState.FAILED_RETRYABLE,
                    error_message="Reconciliación: no se encontró borrador remoto tras incertidumbre.",
                )
        except Exception as err:
            # Si falla la búsqueda de reconciliación, permanece en UNCERTAIN
            action.error_message = (
                f"{action.error_message or ''} | Fallo durante reconciliación: {err}".strip(" |")
            )

        return action

    @staticmethod
    def _extract_appenduid(responses: list[bytes | tuple[Any, ...]]) -> str | None:
        """Intenta extraer el UID asignado desde la respuesta APPENDUID."""
        for item in responses:
            raw = item if isinstance(item, bytes) else str(item).encode("utf-8")
            match = APPENDUID_PATTERN.search(raw.decode("ascii", errors="replace"))
            if match:
                return match.group(2)
        return None
