import socket

import pytest
import pytest_socket

import deep_research


def test_version():
    assert deep_research.__version__ == "0.1.0"


def test_sockets_disabled():
    with pytest.raises(pytest_socket.SocketBlockedError):
        socket.socket()
