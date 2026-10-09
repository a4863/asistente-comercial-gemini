from __future__ import annotations

import email
import email.policy
import imaplib
import re
import socket
from typing import Protocol

from src.domain.draft_action import DraftActionState, EmailDraftAction

DRAFTS_FOLDER_TARGET = "INBOX.Drafts.Borradores Asistente"
IDEMPOTENCY_HEADER = "X-Assistant-Draft-Id"
APPENDUID_PATTERN = re.compile(r"\