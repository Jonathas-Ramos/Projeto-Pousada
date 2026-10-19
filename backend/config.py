"""Configuração de endereços públicos e hosts aceitos."""
import os


def allowed_hosts():
    configured = os.getenv("COLONIA_HOSTS")
    if configured:
        return [host.strip() for host in configured.split(",") if host.strip()]
    render_host = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    if render_host:
        return [render_host]
    return ["localhost", "127.0.0.1", "testserver"]


def expected_origin(base_url):
    return (os.getenv("COLONIA_PUBLIC_URL") or os.getenv("RENDER_EXTERNAL_URL") or base_url).rstrip("/")
