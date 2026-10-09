from __future__ import annotations

import email
import email.policy
import email.utils
import imaplib
import re
import socket
from datetime import datetime, timezone
from typing import Any, Protocol

from src.domain.draft_action import DraftActionState, EmailDraftAction, InvalidStateTransitionError

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
    Previene de forma estricta los reintentos ciegos tras timeouts o ambigüedades.
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
        """Ejecuta el APPEND en el servidor IMAP y gestiona las transiciones de estado.

        Prohíbe reintentos si la acción está en estado UNCERTAIN.
        """
        # Validación de guarda: no se permite APPEND ciego si está en UNCERTAIN o terminal
        action.assert_can_submit()

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

        except (socket.timeout, TimeoutError, ConnectionResetError, BrokenPipeError) as err:
            # Ambigüedad / Timeout tras iniciar transmisión: pasa obligatoriamente a UNCERTAIN
            action.transition_to(
                DraftActionState.UNCERTAIN,
                error_message=f"Interrupción de red durante APPEND (incertidumbre de creación): {type(err).__name__} - {err}",
            )
        except (socket.gaierror, ConnectionRefusedError) as err:
            # Fallo previo de resolución de host o socket no alcanzado: error recuperable
            action.transition_to(
                DraftActionState.FAILED_RETRYABLE,
                error_message=f"Error transitorio de conexión previo a transmisión: {type(err).__name__} - {err}",
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
        """Reconcilia una acción en estado UNCERTAIN consultando el buzón en modo read-only.

        - Si encuentra el mensaje con el token de idempotencia -> CREATED.
        - Si confirma con certeza que no existe en el buzón -> FAILED_RETRYABLE.
        - Si falla la consulta o hay error de conexión -> Permanece estrictamente en UNCERTAIN.
        """
        if action.state != DraftActionState.UNCERTAIN:
            return action

        folder_cmd = format_mailbox_for_command(self.target_folder)

        try:
            status, _ = imap_client.select(folder_cmd, readonly=True)
            if status != "OK":
                action.error_message = (
                    f"{action.error_message or ''} | Reconciliación: no se pudo seleccionar carpeta en readonly (estado {status})."
                ).strip(" |")
                return action

            search_criteria = f'HEADER {IDEMPOTENCY_HEADER} "{action.idempotency_token}"'
            search_status, search_data = imap_client.search(None, search_criteria)

            if search_status == "OK":
                if search_data and search_data[0].strip():
                    uids = search_data[0].decode("ascii", errors="replace").split()
                    found_uid = uids[-1] if uids else None
                    action.transition_to(
                        DraftActionState.CREATED,
                        imap_uid=found_uid,
                    )
                else:
                    # Búsqueda OK y sin resultados: se confirma positivamente que no se creó
                    action.transition_to(
                        DraftActionState.FAILED_RETRYABLE,
                        error_message="Reconciliación exitosa: se confirmó ausencia remota del borrador tras incertidumbre.",
                    )
            else:
                action.error_message = (
                    f"{action.error_message or ''} | Reconciliación SEARCH falló con estado {search_status}."
                ).strip(" |")

        except Exception as err:
            # En caso de fallo de red durante reconciliación, permanece estrictamente en UNCERTAIN
            action.error_message = (
                f"{action.error_message or ''} | Fallo durante intento de reconciliación: {type(err).__name__} - {err}"
            ).strip(" |")

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
