"""Inicialização não interativa para hospedagens sem terminal, como o Render."""
import os
import sys

from manage import create_admin


def main():
    password = os.getenv("COLONIA_ADMIN_PASSWORD")
    if os.getenv("RENDER_EXTERNAL_URL") and not password:
        raise SystemExit("Configure COLONIA_ADMIN_PASSWORD nas variáveis secretas do Render.")
    if password:
        if not os.getenv("COLONIA_ADMIN_LOGIN") or not os.getenv("COLONIA_ADMIN_NAME"):
            raise SystemExit("Configure COLONIA_ADMIN_LOGIN e COLONIA_ADMIN_NAME junto com a senha.")
        create_admin(only_if_empty=True)

    port = os.getenv("PORT", "8000")
    if not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise SystemExit("PORT deve ser um número entre 1 e 65535.")
    os.execv(sys.executable, [sys.executable, "-m", "uvicorn", "backend.main:app",
                              "--host", "0.0.0.0", "--port", port, "--workers", "1"])


if __name__ == "__main__":
    main()
