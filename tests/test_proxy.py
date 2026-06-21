"""Tests for proxy detection module."""
import os
from unittest.mock import MagicMock, patch

import pytest

from key_manager.proxy import COMMON_PORTS, check_port, detect_system_proxy, get_proxy


class TestCheckPort:
    """Tests for check_port function."""

    def test_check_port_open(self):
        """Returns True when port is open."""
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 0
        with patch("key_manager.proxy.socket.socket", return_value=mock_socket):
            assert check_port("127.0.0.1", 7890) is True
            mock_socket.connect_ex.assert_called_once_with(("127.0.0.1", 7890))
            mock_socket.close.assert_called_once()

    def test_check_port_closed(self):
        """Returns False when port is closed."""
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 1
        with patch("key_manager.proxy.socket.socket", return_value=mock_socket):
            assert check_port("127.0.0.1", 9999) is False

    def test_check_port_exception(self):
        """Returns False when socket raises exception."""
        mock_socket = MagicMock()
        mock_socket.connect_ex.side_effect = OSError("Connection failed")
        with patch("key_manager.proxy.socket.socket", return_value=mock_socket):
            assert check_port("127.0.0.1", 7890) is False

    def test_check_port_custom_timeout(self):
        """Uses custom timeout value."""
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 0
        with patch("key_manager.proxy.socket.socket", return_value=mock_socket):
            check_port("127.0.0.1", 7890, timeout=1.0)
            mock_socket.settimeout.assert_called_once_with(1.0)


class TestDetectSystemProxy:
    """Tests for detect_system_proxy function."""

    @pytest.mark.parametrize("env_var", [
        "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"
    ])
    def test_detect_from_env_vars(self, env_var, monkeypatch):
        """Detects proxy from environment variables."""
        monkeypatch.setenv(env_var, "http://proxy.example.com:8080")
        result = detect_system_proxy()
        assert result == "http://proxy.example.com:8080"

    def test_detect_no_env_no_ports(self, monkeypatch):
        """Returns empty when no env vars and no ports open."""
        for var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
            monkeypatch.delenv(var, raising=False)
        with patch("key_manager.proxy.check_port", return_value=False):
            assert detect_system_proxy() == ""

    def test_detect_from_common_port(self, monkeypatch):
        """Detects proxy from common port when no env vars."""
        for var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
            monkeypatch.delenv(var, raising=False)

        def mock_check_port(host, port):
            return port == 7890  # Only Clash port is open

        with patch("key_manager.proxy.check_port", side_effect=mock_check_port):
            result = detect_system_proxy()
            assert result == "http://127.0.0.1:7890"

    def test_detect_env_var_takes_priority(self, monkeypatch):
        """Env var takes priority over port detection."""
        monkeypatch.setenv("HTTP_PROXY", "http://env-proxy:3128")
        with patch("key_manager.proxy.check_port", return_value=True):
            result = detect_system_proxy()
            assert result == "http://env-proxy:3128"


class TestGetProxy:
    """Tests for get_proxy function."""

    def test_get_proxy_none_auto_detect(self):
        """None means auto-detect."""
        with patch("key_manager.proxy.detect_system_proxy", return_value="http://auto:8080"):
            result = get_proxy(None)
            assert result == "http://auto:8080"

    def test_get_proxy_empty_string_disabled(self):
        """Empty string means explicitly disabled."""
        assert get_proxy("") == ""

    def test_get_proxy_custom_value(self):
        """Custom value is returned as-is."""
        assert get_proxy("http://custom:3128") == "http://custom:3128"

    def test_get_proxy_socks5(self):
        """SOCKS5 proxy is returned as-is."""
        assert get_proxy("socks5://localhost:1080") == "socks5://localhost:1080"


class TestCommonPorts:
    """Tests for COMMON_PORTS constant."""

    def test_common_ports_is_list(self):
        """COMMON_PORTS is a list of tuples."""
        assert isinstance(COMMON_PORTS, list)
        for item in COMMON_PORTS:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert isinstance(item[0], int)
            assert isinstance(item[1], str)

    def test_common_ports_has_clash(self):
        """COMMON_PORTS includes Clash ports."""
        port_numbers = [p[0] for p in COMMON_PORTS]
        assert 7890 in port_numbers
        assert 7891 in port_numbers
