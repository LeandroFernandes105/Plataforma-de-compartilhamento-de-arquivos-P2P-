import json
import socket
from typing import Any, Dict, BinaryIO


def send_json(sock: socket.socket, payload: Dict[str, Any]) -> None:
    """Envia uma mensagem JSON terminada por newline.

    O newline resolve um problema comum em TCP: um recv(4096) nao garante que
    a mensagem inteira chegou. Com linha, o receptor sabe onde o JSON termina.
    """
    data = json.dumps(payload).encode("utf-8") + b"\n"
    sock.sendall(data)


def read_json_line(fileobj: BinaryIO) -> Dict[str, Any]:
    line = fileobj.readline()
    if not line:
        raise ConnectionError("Conexao encerrada antes de receber JSON.")
    return json.loads(line.decode("utf-8"))


def request_json(host: str, port: int, payload: Dict[str, Any], timeout: float = 10.0) -> Dict[str, Any]:
    """Abre uma conexao curta, envia um JSON e recebe um JSON de resposta."""
    with socket.create_connection((host, int(port)), timeout=timeout) as sock:
        send_json(sock, payload)
        with sock.makefile("rb") as fileobj:
            return read_json_line(fileobj)
