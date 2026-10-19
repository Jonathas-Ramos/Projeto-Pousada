"""Inicialização do serviço web e compatibilidade com provisionamento antigo."""
import os
import sys

from backend.database import initialize, transaction
from manage import create_admin


def main():
    self_register = os.getenv("COLONIA_SELF_REGISTER") == "1"
    demo = os.getenv("COLONIA_DEMO_MODE") == "1"
    setup_code = os.getenv("COLONIA_SETUP_CODE", "").strip()
    if not self_register and not demo and setup_code and not 16 <= len(setup_code) <= 200:
        raise SystemExit("COLONIA_SETUP_CODE deve conter de 16 a 200 caracteres.")
    if not self_register and not demo and not setup_code:
        # Mantém o acesso existente até o responsável configurar o novo código no Render.
        password = os.getenv("COLONIA_ADMIN_PASSWORD")
        if os.getenv("RENDER_EXTERNAL_URL") and not password:
            raise SystemExit("Configure COLONIA_SETUP_CODE nas variáveis secretas do Render.")
        if password:
            login = (os.getenv("COLONIA_ADMIN_LOGIN") or "").strip().lower()
            if not login or not os.getenv("COLONIA_ADMIN_NAME"):
                raise SystemExit("Configure COLONIA_ADMIN_LOGIN e COLONIA_ADMIN_NAME junto com a senha antiga.")
            initialize()
            with transaction() as db:
                existing = db.execute("SELECT ativo FROM usuarios WHERE login=?", (login,)).fetchone()
            if existing and not existing["ativo"]:
                raise SystemExit("A conta configurada existe, mas está inativa. Reative-a antes de iniciar.")
            if not existing:
                create_admin()

    port = os.getenv("PORT", "8000")
    if not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise SystemExit("PORT deve ser um número entre 1 e 65535.")
    os.execv(sys.executable, [sys.executable, "-m", "uvicorn", "backend.main:app",
                              "--host", "0.0.0.0", "--port", port, "--workers", "1"])


if __name__ == "__main__":
    main()
