import argparse
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Any, List, Tuple
from urllib.parse import unquote, urlparse

from constants import TRACKER_PORT, PEER_TIMEOUT
from protocol import send_json, read_json_line

files_index: Dict[str, Dict[str, Any]] = {}
peers_last_seen: Dict[str, Dict[str, Any]] = {}
lock = threading.Lock()


def peer_ref(peer_id: str, host: str, port: int) -> Dict[str, Any]:
    return {"peer_id": peer_id, "host": host, "port": int(port)}


def same_peer(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return a.get("peer_id") == b.get("peer_id")


def add_peer_to_chunk(file_entry: Dict[str, Any], chunk_index: str, peer: Dict[str, Any]) -> None:
    chunks = file_entry.setdefault("chunks", {})
    peers = chunks.setdefault(chunk_index, [])

    # Remove versoes antigas do mesmo peer para atualizar host/porta caso mudem.
    peers[:] = [p for p in peers if not same_peer(p, peer)]
    peers.append(peer)


def remove_peer_everywhere(peer_id: str) -> None:
    for filename in list(files_index.keys()):
        file_entry = files_index[filename]
        chunks = file_entry.get("chunks", {})

        for chunk_index in list(chunks.keys()):
            chunks[chunk_index] = [p for p in chunks[chunk_index] if p.get("peer_id") != peer_id]
            if not chunks[chunk_index]:
                del chunks[chunk_index]

        if not chunks:
            del files_index[filename]


def compute_availability(file_entry: Dict[str, Any]) -> Dict[str, Any]:
    total_chunks = int(file_entry.get("total_chunks", 0))
    chunk_map = file_entry.get("chunks", {})
    peer_chunks: Dict[str, set] = {}

    for chunk_index, peers in chunk_map.items():
        for peer in peers:
            peer_chunks.setdefault(peer["peer_id"], set()).add(str(chunk_index))

    seeders = []
    leechers = []

    for peer_id, chunks in peer_chunks.items():
        peer_info = peers_last_seen.get(peer_id, {})
        ref = {
            "peer_id": peer_id,
            "host": peer_info.get("host"),
            "port": peer_info.get("port"),
            "chunks": sorted(chunks, key=lambda x: int(x)),
            "chunk_count": len(chunks),
        }

        if total_chunks > 0 and len(chunks) == total_chunks:
            seeders.append(ref)
        else:
            leechers.append(ref)

    return {
        "seed_count": len(seeders),
        "leecher_count": len(leechers),
        "seeders": seeders,
        "leechers": leechers,
    }


def handle_register_chunk(request: Dict[str, Any]) -> Dict[str, Any]:
    required = [
        "filename",
        "chunk_index",
        "chunk_hash",
        "file_hash",
        "file_size",
        "chunk_size",
        "total_chunks",
        "peer_id",
        "peer_host",
        "peer_port",
    ]
    missing = [key for key in required if key not in request]
    if missing:
        return {"status": "error", "message": f"Campos ausentes: {missing}"}

    filename = request["filename"]
    chunk_index = str(request["chunk_index"])
    total_chunks = int(request["total_chunks"])

    if int(chunk_index) < 0 or int(chunk_index) >= total_chunks:
        return {"status": "error", "message": "Indice de chunk invalido."}

    peer_id = request["peer_id"]
    peer = peer_ref(peer_id, request["peer_host"], int(request["peer_port"]))

    with lock:
        peers_last_seen[peer_id] = {
            "host": request["peer_host"],
            "port": int(request["peer_port"]),
            "last_seen": time.time(),
        }

        if filename not in files_index:
            files_index[filename] = {
                "filename": filename,
                "file_hash": request["file_hash"],
                "file_size": int(request["file_size"]),
                "chunk_size": int(request["chunk_size"]),
                "total_chunks": total_chunks,
                "chunk_hashes": {},
                "chunks": {},
            }

        file_entry = files_index[filename]

        # Evita misturar arquivos diferentes com o mesmo nome.
        if file_entry.get("file_hash") != request["file_hash"]:
            return {
                "status": "error",
                "message": "Ja existe um arquivo com esse nome, mas com hash diferente.",
            }

        file_entry["chunk_hashes"][chunk_index] = request["chunk_hash"]
        add_peer_to_chunk(file_entry, chunk_index, peer)
        availability = compute_availability(file_entry)

    status_label = "seed" if any(s["peer_id"] == peer_id for s in availability["seeders"]) else "leecher"
    return {
        "status": "success",
        "message": f"Chunk {chunk_index} de '{filename}' registrado para {peer_id} ({status_label}).",
        "availability": availability,
    }


def handle_search(request: Dict[str, Any]) -> Dict[str, Any]:
    filename = request.get("filename")
    with lock:
        file_entry = files_index.get(filename)
        if not file_entry:
            return {"status": "success", "found": False, "message": "Arquivo nao encontrado.", "file": None}

        # Copia por JSON para evitar entregar referencias internas mutaveis.
        data = json.loads(json.dumps(file_entry))
        data.update(compute_availability(file_entry))
        return {"status": "success", "found": True, "file": data}


def handle_heartbeat(request: Dict[str, Any]) -> Dict[str, Any]:
    required = ["peer_id", "peer_host", "peer_port"]
    missing = [key for key in required if key not in request]
    if missing:
        return {"status": "error", "message": f"Campos ausentes: {missing}"}

    with lock:
        peers_last_seen[request["peer_id"]] = {
            "host": request["peer_host"],
            "port": int(request["peer_port"]),
            "last_seen": time.time(),
        }
    return {"status": "success", "message": "Heartbeat recebido."}


def handle_status() -> Dict[str, Any]:
    with lock:
        files = []
        for filename, entry in files_index.items():
            availability = compute_availability(entry)
            files.append({
                "filename": filename,
                "file_size": entry.get("file_size"),
                "total_chunks": entry.get("total_chunks"),
                "seed_count": availability["seed_count"],
                "leecher_count": availability["leecher_count"],
                "seeders": availability["seeders"],
                "leechers": availability["leechers"],
            })

        peers = []
        now = time.time()
        for peer_id, info in peers_last_seen.items():
            peers.append({
                "peer_id": peer_id,
                "host": info["host"],
                "port": info["port"],
                "seconds_since_seen": round(now - info["last_seen"], 2),
            })

    return {"status": "success", "files": files, "peers": peers}



#  API HTTP 

class TrackerApiHandler(BaseHTTPRequestHandler):

    def _send_json_response(self, status_code: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self._send_json_response(200, {"status": "success"})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path in ["/", "/api", "/api/health"]:
            self._send_json_response(200, {
                "status": "success",
                "service": "tracker-api",
                "message": "API do tracker online. Use /api/status, /api/files ou /api/peers.",
            })
            return

        if path == "/api/status":
            self._send_json_response(200, handle_status())
            return

        if path == "/api/files":
            status = handle_status()
            self._send_json_response(200, {"status": "success", "files": status.get("files", [])})
            return

        if path == "/api/peers":
            status = handle_status()
            self._send_json_response(200, {"status": "success", "peers": status.get("peers", [])})
            return

        if path.startswith("/api/files/"):
            filename = unquote(path[len("/api/files/"):])
            response = handle_search({"filename": filename})
            self._send_json_response(200, response)
            return

        if path.startswith("/api/swarm/"):
            filename = unquote(path[len("/api/swarm/"):])
            response = handle_search({"filename": filename})
            self._send_json_response(200, response)
            return

        self._send_json_response(404, {
            "status": "error",
            "message": "Endpoint nao encontrado.",
            "available_endpoints": [
                "GET /api/health",
                "GET /api/status",
                "GET /api/files",
                "GET /api/files/<filename>",
                "GET /api/peers",
                "GET /api/swarm/<filename>",
            ],
        })

    def log_message(self, format: str, *args: Any) -> None:
        # Evita poluir o terminal do tracker a cada refresh do front.
        return


def start_tracker_api(host: str, port: int) -> None:
    api_server = ThreadingHTTPServer((host, int(port)), TrackerApiHandler)
    print(f"[TRACKER API ONLINE] HTTP em http://{host}:{port}/api/status")
    api_server.serve_forever()

def handle_client(conn: socket.socket, addr: Tuple[str, int]) -> None:
    try:
        with conn.makefile("rb") as fileobj:
            request = read_json_line(fileobj)

        action = request.get("action")
        if action == "heartbeat":
            response = handle_heartbeat(request)
        elif action == "register_chunk":
            response = handle_register_chunk(request)
        elif action == "search":
            response = handle_search(request)
        elif action == "status":
            response = handle_status()
        else:
            response = {"status": "error", "message": f"Acao desconhecida: {action}"}

        send_json(conn, response)
    except Exception as error:
        try:
            send_json(conn, {"status": "error", "message": str(error)})
        except Exception:
            pass
    finally:
        conn.close()


def monitor_timeouts(timeout: int) -> None:
    print(f"[TRACKER] Monitor de heartbeat ativo. Timeout: {timeout}s")
    while True:
        time.sleep(5)
        now = time.time()
        expired: List[str] = []

        with lock:
            for peer_id, info in list(peers_last_seen.items()):
                if now - info["last_seen"] > timeout:
                    expired.append(peer_id)

            for peer_id in expired:
                print(f"[TRACKER] Peer offline por timeout: {peer_id}. Removendo chunks da rede.")
                del peers_last_seen[peer_id]
                remove_peer_everywhere(peer_id)


def start_tracker(host: str, port: int, timeout: int, api_host: str, api_port: int, enable_api: bool) -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, int(port)))
    server.listen()

    print(f"[TRACKER ONLINE] Escutando peers em {host}:{port}")
    threading.Thread(target=monitor_timeouts, args=(timeout,), daemon=True).start()
    if enable_api:
        threading.Thread(target=start_tracker_api, args=(api_host, api_port), daemon=True).start()

    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tracker P2P - cataloga arquivos, chunks e peers online.")
    parser.add_argument("--host", default="0.0.0.0", help="Endereco em que o tracker escuta. Padrao: 0.0.0.0")
    parser.add_argument("--port", type=int, default=TRACKER_PORT, help="Porta do tracker. Padrao: 5000")
    parser.add_argument("--timeout", type=int, default=PEER_TIMEOUT, help="Timeout em segundos para remover peer offline.")
    parser.add_argument("--api-host", default="0.0.0.0", help="Endereco da API HTTP do tracker. Padrao: 0.0.0.0")
    parser.add_argument("--api-port", type=int, default=8000, help="Porta da API HTTP do tracker. Padrao: 8000")
    parser.add_argument("--no-api", action="store_true", help="Desativa a API HTTP do tracker.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    start_tracker(args.host, args.port, args.timeout, args.api_host, args.api_port, not args.no_api)
