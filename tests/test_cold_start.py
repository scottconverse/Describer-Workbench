"""F10 (DW-1): a server that accepts and then drops is not 'unreachable'."""
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from describer import models


class Stub(BaseHTTPRequestHandler):
    calls = []
    drop_chat = 1

    def log_message(self, *args):pass

    def do_GET(self):
        Stub.calls.append(self.path)
        self.reply({'models': []})

    def do_POST(self):
        Stub.calls.append(self.path)
        self.rfile.read(int(self.headers.get('Content-Length', 0)))
        if self.path == '/api/chat' and Stub.calls.count('/api/chat') <= Stub.drop_chat:
            # Accept the request, then drop it, like a model that is still loading.
            self.close_connection = True
            self.connection.shutdown(socket.SHUT_RDWR)
            return
        if self.path == '/api/chat':
            self.reply({'message': {'content': '{"ok":true}'}, 'done': True, 'done_reason': 'stop'})
        else:
            self.reply({'response': '', 'done': True})

    def reply(self, value):
        body = (json.dumps(value) + '\n').encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def stub():
    Stub.calls = []
    server = ThreadingHTTPServer(('127.0.0.1', 0), Stub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def settings(port):
    return {'ollama_url': f'http://127.0.0.1:{port}', 'ollama_model': 'gemma4:12b', '_ollama_info': {}}


def ask(port):
    return models.chat(settings(port), [{'role': 'user', 'content': 'hi'}], threading.Event(), lambda _: None)


def test_dropped_request_is_retried_once_after_a_warm_up(stub):
    Stub.drop_chat = 1
    assert ask(stub.server_port) == '{"ok":true}'
    assert Stub.calls.count('/api/chat') == 2
    assert Stub.calls.index('/api/generate') < len(Stub.calls) - 1


def test_dropped_twice_reports_unfinished_not_unreachable(stub):
    Stub.drop_chat = 9
    with pytest.raises(RuntimeError) as error:
        ask(stub.server_port)
    message = str(error.value)
    assert 'accepted the request but did not finish it' in message
    assert 'Could not reach' not in message
    assert Stub.calls.count('/api/chat') == 2


def test_no_server_reports_the_address_and_no_gui_menu():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    with pytest.raises(RuntimeError) as error:
        ask(port)
    message = str(error.value)
    assert f'Could not reach Ollama at http://127.0.0.1:{port}' in message
    assert 'describer models' in message
