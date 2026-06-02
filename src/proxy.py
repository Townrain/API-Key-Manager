import os
import socket

# Common proxy ports to check
COMMON_PORTS = [
    (7890, "Clash"),
    (7891, "Clash"),
    (1080, "SOCKS"),
    (10808, "V2Ray"),
    (10809, "V2Ray"),
    (1081, "SOCKS"),
    (8080, "HTTP"),
    (8118, "Privoxy"),
    (9090, "Proxy"),
]


def check_port(host: str, port: int, timeout: float = 0.3) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def detect_system_proxy() -> str:
    # Check environment variables
    for var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
        proxy = os.environ.get(var, "")
        if proxy:
            return proxy

    # Check common proxy ports
    for port, name in COMMON_PORTS:
        if check_port("127.0.0.1", port):
            return f"http://127.0.0.1:{port}"

    return ""


def get_proxy(config_proxy: str = "") -> str:
    """Get proxy from config or auto-detect."""
    if config_proxy:
        return config_proxy
    return detect_system_proxy()
