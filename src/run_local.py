from __future__ import annotations

import socket
import sys
import uvicorn

LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 8000
DRAFTS_FOLDER_TARGET = "INBOX.Drafts.Borradores Asistente"


def verify_security_invariants(host: str) -> None:
    """Verifica estrictamente que el host esté configurado únicamente en 127.0.0.1."""
    if host not in ("127.0.0.1", "localhost"):
        print(
            f"[ERROR DE SEGURIDAD CRITICO] Bind denegado en '{host}'. "
            f"ACLIMAR Assistant opera exclusivamente en modo Local-Only (127.0.0.1).",
            file=sys.stderr,
        )
        sys.exit(1)


def check_port_availability(host: str, port: int) -> bool:
    """Comprueba que el puerto esté disponible para bind local antes de iniciar Uvicorn."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        result = s.connect_ex((host, port))
        # Si connect_ex retorna 0, significa que el puerto ya está en uso
        return result != 0


def print_startup_banner() -> None:
    banner = f"""
======================================================================
 ACLIMAR Assistant - Cockpit Comercial Local (Windows Edition)
======================================================================
 - Host de Enlace:       http://{LOCAL_HOST}:{LOCAL_PORT}
 - Invariante de Red:    Local-Only estricto (Sin acceso externo)
 - Invariante de Correo: CERO SMTP (Prohibido envio automatico)
 - Carpeta de Borradores: {DRAFTS_FOLDER_TARGET}
 - Almacenamiento Claves: Windows Keyring (Cero texto plano)
 - Documentacion API:    http://{LOCAL_HOST}:{LOCAL_PORT}/docs
======================================================================
 Presione Ctrl+C en esta consola para detener el servidor.
======================================================================
"""
    print(banner)


def main() -> None:
    # 1. Comprobación de seguridad no negociable
    verify_security_invariants(LOCAL_HOST)

    # 2. Comprobación de disponibilidad de socket
    if not check_port_availability(LOCAL_HOST, LOCAL_PORT):
        print(
            f"[ERROR DE INICIO] El puerto {LOCAL_PORT} en {LOCAL_HOST} ya se encuentra ocupado.\n"
            f"Verifique si otra instancia de ACLIMAR Assistant ya esta en ejecucion.",
            file=sys.stderr,
        )
        sys.exit(1)

    print_startup_banner()

    # 3. Lanzamiento seguro del servidor ASGI
    uvicorn.run(
        "src.main:app",
        host=LOCAL_HOST,
        port=LOCAL_PORT,
        reload=False,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    main()
