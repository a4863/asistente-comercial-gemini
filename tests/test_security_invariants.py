from __future__ import annotations

import inspect
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.run_local import verify_security_invariants, LOCAL_HOST
from src.services import imap_draft_service

client = TestClient(app)


# =========================================================================
# 1. Regresión e Invariante: Cero SMTP (Prohibición Absoluta de Envío)
# =========================================================================

def test_invariant_zero_smtp_no_smtplib_imports() -> None:
    """Verifica que ningún módulo en src/ importe o dependa de smtplib ni aiosmtplib."""
    src_dir = Path(__file__).resolve().parent.parent / "src"
    py_files = list(src_dir.rglob("*.py"))

    forbidden_modules = ["smtplib", "aiosmtplib"]

    for py_file in py_files:
        content = py_file.read_text(encoding="utf-8")
        for forbidden in forbidden_modules:
            assert f"import {forbidden}" not in content, (
                f"Violación de invariante Cero SMTP: {py_file} importa {forbidden}."
            )
            assert f"from {forbidden}" not in content, (
                f"Violación de invariante Cero SMTP: {py_file} importa desde {forbidden}."
            )


def test_invariant_zero_smtp_no_smtp_ports_in_source() -> None:
    """Verifica que en el código de src/ no se configure conexión a puertos SMTP clásicos (25, 465, 587)."""
    src_dir = Path(__file__).resolve().parent.parent / "src"
    py_files = list(src_dir.rglob("*.py"))

    forbidden_ports = ["port=25", "port = 25", "port=587", "port = 587", "port=465", "port = 465"]

    for py_file in py_files:
        content = py_file.read_text(encoding="utf-8")
        for forbidden in forbidden_ports:
            assert forbidden not in content, (
                f"Violación de seguridad: Puerto SMTP detectado en {py_file.name}: {forbidden}."
            )


def test_invariant_zero_smtp_no_send_endpoints_in_api() -> None:
    """Verifica que la API no exponga endpoints ni rutas con semántica de envío de correo."""
    forbidden_terms = ["/send", "/send-email", "/enviar", "/mail/send"]

    for route in app.routes:
        path = getattr(route, "path", "")
        for term in forbidden_terms:
            assert term not in path.lower(), (
                f"Violación de invariante Cero SMTP: La ruta '{path}' sugiere envío directo de correo."
            )


def test_invariant_zero_smtp_destination_folder_and_draft_flag() -> None:
    """Verifica que la carpeta destino y los flags de IMAP correspondan exclusivamente a borradores."""
    assert imap_draft_service.DRAFTS_FOLDER_TARGET == "INBOX.Drafts.Borradores Asistente"
    source_code = inspect.getsource(imap_draft_service.ImapDraftAppender.append_draft)
    assert r'r"(\Draft)"' in source_code or r"'(\Draft)'" in source_code or r"(\Draft)" in source_code


# =========================================================================
# 2. Regresión e Invariante: Local-Only (127.0.0.1)
# =========================================================================

def test_invariant_local_only_binding_configuration() -> None:
    """Verifica que el host predeterminado sea estrictamente 127.0.0.1."""
    assert LOCAL_HOST == "127.0.0.1"


def test_invariant_local_only_rejects_non_local_hosts() -> None:
    """Verifica que verify_security_invariants rechace hosts públicos o abiertos a la red."""
    unsafe_hosts = ["0.0.0.0", "192.168.1.50", "10.0.0.1", "aclimar.es", "8.8.8.8"]

    for host in unsafe_hosts:
        with pytest.raises(SystemExit):
            verify_security_invariants(host)


def test_invariant_local_only_allows_127_0_0_1_and_localhost() -> None:
    """Verifica que solo se permita 127.0.0.1 o localhost."""
    verify_security_invariants("127.0.0.1")
    verify_security_invariants("localhost")


def test_invariant_local_only_cors_policy() -> None:
    """Verifica que la política CORS no permita orígenes comodín (*) ni dominios externos públicos."""
    cors_middlewares = [
        m for m in app.user_middleware if "CORSMiddleware" in str(m.cls)
    ]
    assert len(cors_middlewares) > 0, "Debe existir un middleware de CORS configurado."

    cors_config = cors_middlewares[0].options
    allowed_origins = cors_config.get("allow_origins", [])

    assert "*" not in allowed_origins, "Violación de seguridad: CORS allow_origins no debe permitir '*'."
    for origin in allowed_origins:
        assert ("127.0.0.1" in origin) or ("localhost" in origin), (
            f"Violación Local-Only: Origen CORS no local detectado: {origin}"
        )


def test_invariant_local_only_health_endpoint() -> None:
    """Verifica que el endpoint /health reporte el bind exclusivo a 127.0.0.1."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json().get("bind") == "127.0.0.1"


# =========================================================================
# 3. Regresión e Invariante: Credenciales y Sanitización de Secretos (Keyring)
# =========================================================================

def test_invariant_no_hardcoded_passwords_in_source() -> None:
    """Escanea el código fuente buscando posibles patrones de contraseñas o tokens en texto plano."""
    src_dir = Path(__file__).resolve().parent.parent / "src"
    py_files = list(src_dir.rglob("*.py"))

    forbidden_patterns = [
        "password =",
        "password=",
        "passwd =",
        "passwd=",
        "api_key =",
        "api_key=",
        "secret =",
        "secret=",
    ]

    for py_file in py_files:
        lines = py_file.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(lines, start=1):
            cleaned = line.strip().lower()
            if cleaned.startswith("#") or ":" in cleaned:
                continue
            for pattern in forbidden_patterns:
                if pattern in cleaned and "os.getenv" not in cleaned and "keyring" not in cleaned:
                    val = cleaned.split(pattern)[1].strip()
                    assert val in ('none', '""', "''", 'none,', '"" ,', "'' ,"), (
                        f"Posible credencial en texto plano en {py_file.name}:{idx}: {line.strip()}"
                    )


def test_invariant_error_sanitization_does_not_leak_secrets() -> None:
    """Verifica que los mensajes de error retornados por la API no incluyan tokens ni contraseñas."""
    resp = client.get("/api/drafts/proposals/id-inexistente")
    assert resp.status_code == 404
    detail = resp.json().get("detail", "")
    assert "password" not in detail.lower()
    assert "token" not in detail.lower()
