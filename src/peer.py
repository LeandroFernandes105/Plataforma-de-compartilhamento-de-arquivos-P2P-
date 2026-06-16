import argparse
import hashlib
import json
import os
import random
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

from constants import (
    TRACKER_HOST,
    TRACKER_PORT,
    PEER_LISTEN_HOST,
    PEER_PUBLIC_HOST,
    SHARED_FOLDER,
    DOWNLOAD_FOLDER,
    STATE_FOLDER,
    PARTIAL_FOLDER,
    CHUNK_SIZE,
    HEARTBEAT_INTERVAL,
)
from protocol import send_json, read_json_line, request_json


# ----------------------------- utilitarios -----------------------------

def ensure_dirs(*paths: str) -> None:
    for path in paths:
        os.makedirs(path, exist_ok=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as fileobj:
        for block in iter(lambda: fileobj.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def chunk_count(file_size: int, chunk_size: int) -> int:
    if file_size == 0:
        return 1
    return (file_size // chunk_size) + (1 if file_size % chunk_size else 0)


def chunk_file_path(partial_dir: str, filename: str, file_hash: str, chunk_index: int) -> str:
    safe_hash = hashlib.sha256(filename.encode("utf-8")).hexdigest()[:12]
    return os.path.join(partial_dir, f"{safe_hash}_{file_hash[:12]}_{chunk_index}.chunk")


def pretty_json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


# ----------------------------- catalogo local -----------------------------

class LocalCatalog:
    """Estado local do peer.

    O arquivo baixado nao grava que e seed. Quem grava o estado e este catalogo.
    Ele diz quais arquivos/chunks este peer possui e de onde pode servi-los.
    """

    def __init__(self, state_dir: str, peer_id: str):
        ensure_dirs(state_dir)
        safe_peer = hashlib.sha256(peer_id.encode("utf-8")).hexdigest()[:12]
        self.path = os.path.join(state_dir, f"catalog_{safe_peer}.json")
        self.data: Dict[str, Any] = {"files": {}}
        self._lock = threading.Lock()
        self.load()

    def load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as fileobj:
                    self.data = json.load(fileobj)
            except Exception:
                self.data = {"files": {}}
        self.data.setdefault("files", {})

    def save(self) -> None:
        with self._lock:
            with open(self.path, "w", encoding="utf-8") as fileobj:
                json.dump(self.data, fileobj, indent=2, ensure_ascii=False)

    def get(self, filename: str) -> Optional[Dict[str, Any]]:
        return self.data["files"].get(filename)

    def all_files(self) -> Dict[str, Any]:
        return self.data["files"]

    def upsert_completed_file(
        self,
        *,
        filename: str,
        path: str,
        file_size: int,
        chunk_size: int,
        total_chunks: int,
        file_hash: str,
        chunk_hashes: Dict[str, str],
    ) -> None:
        self.data["files"][filename] = {
            "filename": filename,
            "path": os.path.abspath(path),
            "file_size": int(file_size),
            "chunk_size": int(chunk_size),
            "total_chunks": int(total_chunks),
            "file_hash": file_hash,
            "chunk_hashes": {str(k): v for k, v in chunk_hashes.items()},
            "completed": True,
            "chunks": {str(i): {"source": "completed_file"} for i in range(int(total_chunks))},
        }
        self.save()

    def upsert_partial_chunk(
        self,
        *,
        filename: str,
        chunk_index: int,
        chunk_path: str,
        chunk_hash: str,
        metadata: Dict[str, Any],
    ) -> None:
        with self._lock:
            filename = metadata["filename"]
            entry = self.data["files"].setdefault(filename, {
                "filename": filename,
                "path": None,
                "file_size": int(metadata["file_size"]),
                "chunk_size": int(metadata["chunk_size"]),
                "total_chunks": int(metadata["total_chunks"]),
                "file_hash": metadata["file_hash"],
                "chunk_hashes": metadata.get("chunk_hashes", {}),
                "completed": False,
                "chunks": {},
            })

            entry["file_size"] = int(metadata["file_size"])
            entry["chunk_size"] = int(metadata["chunk_size"])
            entry["total_chunks"] = int(metadata["total_chunks"])
            entry["file_hash"] = metadata["file_hash"]
            entry["chunk_hashes"] = metadata.get("chunk_hashes", entry.get("chunk_hashes", {}))
            entry["chunks"][str(chunk_index)] = {
                "source": "partial_chunk",
                "path": os.path.abspath(chunk_path),
                "hash": chunk_hash,
            }
            with open(self.path, "w", encoding="utf-8") as fileobj:
                json.dump(self.data, fileobj, indent=2, ensure_ascii=False)

    def has_valid_chunk(self, filename: str, chunk_index: int) -> bool:
        entry = self.get(filename)
        if not entry:
            return False
        if entry.get("completed") and entry.get("path") and os.path.exists(entry["path"]):
            return str(chunk_index) in entry.get("chunks", {})
        chunk_info = entry.get("chunks", {}).get(str(chunk_index))
        return bool(chunk_info and chunk_info.get("path") and os.path.exists(chunk_info["path"]))

    def available_chunk_indices(self, filename: str) -> List[int]:
        entry = self.get(filename)
        if not entry:
            return []
        return sorted([int(i) for i in entry.get("chunks", {}).keys()])

    def read_chunk(self, filename: str, chunk_index: int) -> Tuple[bytes, Dict[str, Any]]:
        entry = self.get(filename)
        if not entry:
            raise FileNotFoundError("Arquivo nao existe no catalogo local deste peer.")

        chunk_index_str = str(chunk_index)
        if chunk_index_str not in entry.get("chunks", {}):
            raise FileNotFoundError("Este peer nao possui o chunk solicitado.")

        chunk_size = int(entry["chunk_size"])
        expected_size = min(chunk_size, int(entry["file_size"]) - chunk_index * chunk_size)
        if expected_size < 0:
            raise ValueError("Indice de chunk fora do tamanho do arquivo.")

        if entry.get("completed"):
            path = entry.get("path")
            if not path or not os.path.exists(path):
                raise FileNotFoundError("Arquivo completo nao encontrado no disco.")
            with open(path, "rb") as fileobj:
                fileobj.seek(chunk_index * chunk_size)
                data = fileobj.read(expected_size)
        else:
            chunk_path = entry["chunks"][chunk_index_str].get("path")
            if not chunk_path or not os.path.exists(chunk_path):
                raise FileNotFoundError("Chunk parcial nao encontrado no disco.")
            with open(chunk_path, "rb") as fileobj:
                data = fileobj.read()

        return data, entry


# ----------------------------- peer -----------------------------

class PeerNode:
    def __init__(
        self,
        *,
        peer_id: str,
        listen_host: str,
        public_host: str,
        peer_port: int,
        tracker_host: str,
        tracker_port: int,
        shared_dir: str,
        downloads_dir: str,
        state_dir: str,
        partial_dir: str,
        chunk_size: int,
    ):
        self.peer_id = peer_id
        self.listen_host = listen_host
        self.public_host = public_host
        self.peer_port = int(peer_port)
        self.tracker_host = tracker_host
        self.tracker_port = int(tracker_port)
        self.shared_dir = shared_dir
        self.downloads_dir = downloads_dir
        self.state_dir = state_dir
        self.partial_dir = partial_dir
        self.chunk_size = int(chunk_size)
        self.catalog = LocalCatalog(state_dir, peer_id)
        self.stop_event = threading.Event()

        ensure_dirs(self.shared_dir, self.downloads_dir, self.state_dir, self.partial_dir)

    # ------------------------- comunicacao com tracker -------------------------

    def tracker_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return request_json(self.tracker_host, self.tracker_port, payload)

    def heartbeat_loop(self) -> None:
        time.sleep(1)
        while not self.stop_event.is_set():
            try:
                self.tracker_request({
                    "action": "heartbeat",
                    "peer_id": self.peer_id,
                    "peer_host": self.public_host,
                    "peer_port": self.peer_port,
                })
            except Exception as error:
                print(f"[HEARTBEAT] Tracker indisponivel: {error}")
            time.sleep(HEARTBEAT_INTERVAL)

    def register_chunk(self, filename: str, chunk_index: int, entry: Dict[str, Any]) -> Dict[str, Any]:
        chunk_hash = entry["chunk_hashes"][str(chunk_index)]
        request = {
            "action": "register_chunk",
            "filename": filename,
            "chunk_index": int(chunk_index),
            "chunk_hash": chunk_hash,
            "file_hash": entry["file_hash"],
            "file_size": int(entry["file_size"]),
            "chunk_size": int(entry["chunk_size"]),
            "total_chunks": int(entry["total_chunks"]),
            "peer_id": self.peer_id,
            "peer_host": self.public_host,
            "peer_port": self.peer_port,
        }
        return self.tracker_request(request)

    def announce_known_chunks(self, filename: Optional[str] = None) -> None:
        files = self.catalog.all_files()
        targets = [filename] if filename else list(files.keys())

        for name in targets:
            entry = files.get(name)
            if not entry:
                continue

            for chunk_index in self.catalog.available_chunk_indices(name):
                try:
                    response = self.register_chunk(name, chunk_index, entry)
                    if response.get("status") != "success":
                        print(f"[ANUNCIO] Falha ao anunciar {name} chunk {chunk_index}: {response.get('message')}")
                except Exception as error:
                    print(f"[ANUNCIO] Tracker indisponivel ao anunciar {name}: {error}")
                    return

    def search_file(self, filename: str) -> Tuple[bool, Any]:
        try:
            response = self.tracker_request({"action": "search", "filename": filename})
            if response.get("status") != "success":
                return False, response.get("message", "Erro ao buscar arquivo.")
            if not response.get("found"):
                return False, "Arquivo nao encontrado no tracker."
            return True, response["file"]
        except ConnectionRefusedError:
            return False, "Nao foi possivel conectar ao tracker."
        except Exception as error:
            return False, f"Erro ao buscar arquivo: {error}"

    def tracker_status(self) -> Tuple[bool, Any]:
        try:
            response = self.tracker_request({"action": "status"})
            return response.get("status") == "success", response
        except Exception as error:
            return False, f"Erro ao consultar tracker: {error}"

    # ------------------------- servidor de upload -------------------------

    def start(self) -> None:
        threading.Thread(target=self.upload_server, daemon=True).start()
        threading.Thread(target=self.heartbeat_loop, daemon=True).start()
        self.announce_known_chunks()

    def upload_server(self) -> None:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.listen_host, self.peer_port))
        server.listen()

        print(f"[PEER ONLINE] {self.peer_id} escutando em {self.listen_host}:{self.peer_port}")
        print(f"[PEER ONLINE] Anunciando ao tracker como {self.public_host}:{self.peer_port}")

        while not self.stop_event.is_set():
            try:
                conn, addr = server.accept()
                threading.Thread(target=self.handle_peer_connection, args=(conn, addr), daemon=True).start()
            except OSError:
                break

    def handle_peer_connection(self, conn: socket.socket, addr: Tuple[str, int]) -> None:
        try:
            with conn.makefile("rb") as fileobj:
                request = read_json_line(fileobj)

            action = request.get("action")
            if action != "get_chunk":
                send_json(conn, {"status": "error", "message": "Acao invalida para peer."})
                return

            filename = request["filename"]
            chunk_index = int(request["chunk_index"])
            data, entry = self.catalog.read_chunk(filename, chunk_index)
            expected_hash = entry["chunk_hashes"].get(str(chunk_index))
            actual_hash = sha256_bytes(data)

            if expected_hash and actual_hash != expected_hash:
                send_json(conn, {"status": "error", "message": "Chunk local falhou na validacao de hash."})
                return

            send_json(conn, {
                "status": "success",
                "filename": filename,
                "chunk_index": chunk_index,
                "size": len(data),
                "chunk_hash": actual_hash,
            })
            conn.sendall(data)
            print(f"[UPLOAD] Enviei {filename} chunk {chunk_index} para {addr[0]}:{addr[1]}")
        except Exception as error:
            try:
                send_json(conn, {"status": "error", "message": str(error)})
            except Exception:
                pass
        finally:
            conn.close()

    # ------------------------- compartilhamento local -------------------------

    def build_file_metadata(self, path: str) -> Dict[str, Any]:
        file_size = os.path.getsize(path)
        total_chunks = chunk_count(file_size, self.chunk_size)
        chunk_hashes: Dict[str, str] = {}

        with open(path, "rb") as fileobj:
            for index in range(total_chunks):
                data = fileobj.read(self.chunk_size)
                chunk_hashes[str(index)] = sha256_bytes(data)

        return {
            "filename": os.path.basename(path),
            "path": os.path.abspath(path),
            "file_size": file_size,
            "chunk_size": self.chunk_size,
            "total_chunks": total_chunks,
            "file_hash": sha256_file(path),
            "chunk_hashes": chunk_hashes,
        }

    def share_file(self, user_path: str) -> Tuple[bool, str]:
        path = user_path
        if not os.path.isabs(path):
            path = os.path.join(self.shared_dir, user_path)

        if not os.path.exists(path) or not os.path.isfile(path):
            return False, f"Arquivo nao encontrado: {path}"

        metadata = self.build_file_metadata(path)
        filename = metadata["filename"]

        self.catalog.upsert_completed_file(**metadata)
        entry = self.catalog.get(filename)
        assert entry is not None

        print(f"[SHARE] '{filename}' possui {entry['total_chunks']} chunk(s). Anunciando ao tracker...")

        for index in range(int(entry["total_chunks"])):
            response = self.register_chunk(filename, index, entry)
            if response.get("status") != "success":
                return False, response.get("message", "Erro ao registrar chunk.")

        return True, f"'{filename}' compartilhado. Este peer agora e seed desse arquivo."

    # ------------------------- download -------------------------

    def choose_peer_for_chunk(self, peers: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        candidates = [p for p in peers if p.get("peer_id") != self.peer_id]
        if not candidates:
            return None
        return random.choice(candidates)

    def request_chunk(self, peer: Dict[str, Any], filename: str, chunk_index: int) -> bytes:
        host = peer["host"]
        port = int(peer["port"])
        with socket.create_connection((host, port), timeout=20) as sock:
            send_json(sock, {"action": "get_chunk", "filename": filename, "chunk_index": chunk_index})
            with sock.makefile("rb") as fileobj:
                header = read_json_line(fileobj)
                if header.get("status") != "success":
                    raise RuntimeError(header.get("message", "Peer nao enviou o chunk."))
                size = int(header["size"])
                data = fileobj.read(size)
                if len(data) != size:
                    raise RuntimeError("Chunk recebido incompleto.")
                return data

    def save_partial_chunk(self, metadata: Dict[str, Any], chunk_index: int, data: bytes) -> str:
        # Cada chunk eh salvo em um arquivo, o que permite que multiplas threads escrevam no disco ao mesmo tempo sem conflito,
        # pois cada uma opera em um caminho de arquivo distinto.
        path = chunk_file_path(self.partial_dir, metadata["filename"], metadata["file_hash"], chunk_index)
        with open(path, "wb") as fileobj:
            fileobj.write(data)
        return path

    def assemble_completed_file(self, metadata: Dict[str, Any]) -> str:
        filename = metadata["filename"]
        temp_path = os.path.join(self.downloads_dir, filename + ".part")
        final_path = os.path.join(self.downloads_dir, filename)

        with open(temp_path, "wb") as output:
            for index in range(int(metadata["total_chunks"])):
                data, _ = self.catalog.read_chunk(filename, index)
                output.write(data)

        final_hash = sha256_file(temp_path)
        if final_hash != metadata["file_hash"]:
            raise RuntimeError("Hash final do arquivo nao confere. Download descartado.")

        os.replace(temp_path, final_path)
        return final_path

    def _download_single_chunk(
        self,
        filename: str,
        index: int,
        metadata: Dict[str, Any],
    ) -> Tuple[int, bool, str]:
        """Baixa, valida, salva no disco e anuncia ao tracker um unico chunk.
        Este metodo eh executado em paralelo por multiplas threads (uma por chunk).
        Cada thread opera sobre um indice de chunk diferente, portanto nao ha
        conflito de escrita em disco.
        """
        chunk_hashes = metadata.get("chunk_hashes", {})
        chunks = metadata.get("chunks", {})

        # Se este peer ja possui o chunk (de um download anterior interrompido), pula sem baixar novamente.
        if self.catalog.has_valid_chunk(filename, index):
            print(f"[DOWNLOAD] Chunk {index} ja existe localmente. Pulando.")
            return index, True, ""

        # Escolhe um peer da swarm que possui este chunk (excluindo a si mesmo)
        peers = chunks.get(str(index), [])
        peer = self.choose_peer_for_chunk(peers)
        if not peer:
            return index, False, f"Nao ha outro peer disponivel para o chunk {index}."

        print(f"[DOWNLOAD] Baixando chunk {index} de {peer['peer_id']} ({peer['host']}:{peer['port']})...")
        try:
            data = self.request_chunk(peer, filename, index)
        except Exception as error:
            return index, False, f"Falha ao baixar chunk {index}: {error}"
        expected_hash = chunk_hashes.get(str(index))
        actual_hash = sha256_bytes(data)
        if expected_hash and actual_hash != expected_hash:
            return index, False, f"Chunk {index} veio corrompido. Hash nao confere."

        chunk_path = self.save_partial_chunk(metadata, index, data)

        self.catalog.upsert_partial_chunk(
            filename=filename,
            chunk_index=index,
            chunk_path=chunk_path,
            chunk_hash=actual_hash,
            metadata=metadata,
        )

            # Aqui o leecher ja ajuda a swarm: assim que tem um chunk valido,
            # anuncia esse chunk ao tracker e pode servir esse pedaco para outros.
        entry = self.catalog.get(filename)
        assert entry is not None
        response = self.register_chunk(filename, index, entry)
        if response.get("status") == "success":
            print(f"[LEECHER] Chunk {index} anunciado. Este peer ja pode enviar esse pedaco.")
        else:
            print(f"[LEECHER] Nao consegui anunciar chunk {index}: {response.get('message')}")

        return index, True, ""

    def download_file(self, filename: str, max_workers: int = 4) -> Tuple[bool, str]:
        """Baixa um arquivo em paralelo, distribuindo os chunks entre multiplos peers.
        Fluxo:
          1. Consulta o tracker para obter metadados e lista de peers por chunk.
          2. Identifica quais chunks ainda faltam (permite retomar downloads).
          3. Dispara uma thread por chunk pendente (ate max_workers simultaneas).
          4. Aguarda conclusao; na primeira falha, cancela as demais e retorna erro.
          5. Monta o arquivo final a partir dos chunks e valida o hash global.
          6. Reanuncia todos os chunks ao tracker: este peer passa a ser seed.
        """
        success, result = self.search_file(filename)
        if not success:
            return False, result

        metadata = result
        total_chunks = int(metadata["total_chunks"])
        chunk_hashes = metadata.get("chunk_hashes", {})
        chunks = metadata.get("chunks", {})

        if not chunks:
            return False, "Arquivo encontrado, mas nao ha chunks disponiveis. Sem fonte ativa."

        print(
            f"[DOWNLOAD] Arquivo '{filename}': {total_chunks} chunk(s) | "
            f"Seeds: {metadata.get('seed_count', 0)} | Workers paralelos: {max_workers}"
        )

        pending = [i for i in range(total_chunks) if not self.catalog.has_valid_chunk(filename, i)]
        print(f"[DOWNLOAD] {len(pending)} chunk(s) precisam ser baixados.")

        # max_workers define o limite de downloads simultaneos; aumentar demais pode saturar a rede ou ser bloqueado pelos peers remotos.
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._download_single_chunk, filename, index, metadata): index
                for index in pending
            }
            for future in as_completed(futures):
                index, ok, message = future.result()
                if not ok:
                    executor.shutdown(wait=False, cancel_futures=True)
                    return False, message

        try:
            final_path = self.assemble_completed_file(metadata)
        except Exception as error:
            return False, f"Erro ao montar arquivo final: {error}"

        self.catalog.upsert_completed_file(
            filename=filename,
            path=final_path,
            file_size=int(metadata["file_size"]),
            chunk_size=int(metadata["chunk_size"]),
            total_chunks=total_chunks,
            file_hash=metadata["file_hash"],
            chunk_hashes=chunk_hashes,
        )

        # Reanuncia todos os chunks. Agora o tracker vai contar este peer como seed.
        self.announce_known_chunks(filename)
        return True, f"Download finalizado em '{final_path}'. Este peer agora e seed de '{filename}'."

    # ------------------------- exibicao CLI -------------------------

    def show_local_catalog(self) -> None:
        files = self.catalog.all_files()
        if not files:
            print("Catalogo local vazio.")
            return

        for filename, entry in files.items():
            status = "SEED" if entry.get("completed") else "LEECHER/PARCIAL"
            chunks = self.catalog.available_chunk_indices(filename)
            print(f"\nArquivo: {filename}")
            print(f"Status local: {status}")
            print(f"Chunks locais: {chunks} ({len(chunks)}/{entry.get('total_chunks')})")
            print(f"Hash: {entry.get('file_hash')}")
            print(f"Caminho: {entry.get('path')}")

    def show_tracker_status(self) -> None:
        success, status = self.tracker_status()
        if not success:
            print(status)
            return
        print(pretty_json(status))


# ----------------------------- CLI -----------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Peer P2P por linha de comando.")
    parser.add_argument("--peer-id", default=None, help="Identificador do peer. Padrao: <public-host>:<port>")
    parser.add_argument("--listen-host", default=PEER_LISTEN_HOST, help="Host local para escutar conexoes. Use 0.0.0.0 em rede local.")
    parser.add_argument("--public-host", default=PEER_PUBLIC_HOST, help="IP/host anunciado ao tracker. Em dois PCs, use o IP real da maquina.")
    parser.add_argument("--port", type=int, required=True, help="Porta TCP do servidor de upload deste peer.")
    parser.add_argument("--tracker-host", default=TRACKER_HOST, help="IP/host do tracker.")
    parser.add_argument("--tracker-port", type=int, default=TRACKER_PORT, help="Porta do tracker.")
    parser.add_argument("--shared-dir", default=SHARED_FOLDER, help="Pasta com arquivos locais para compartilhar.")
    parser.add_argument("--downloads-dir", default=DOWNLOAD_FOLDER, help="Pasta onde downloads completos serao salvos.")
    parser.add_argument("--state-dir", default=STATE_FOLDER, help="Pasta do catalogo local do peer.")
    parser.add_argument("--partial-dir", default=PARTIAL_FOLDER, help="Pasta para chunks parciais.")
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE, help="Tamanho dos chunks em bytes.")
    return parser.parse_args()


def menu_loop(peer: PeerNode) -> None:
    while True:
        print("\n================ PEER P2P ================")
        print(f"Peer: {peer.peer_id} | upload: {peer.public_host}:{peer.peer_port}")
        print("1 - Compartilhar arquivo local (vira seed)")
        print("2 - Buscar arquivo no tracker")
        print("3 - Baixar arquivo")
        print("4 - Ver catalogo local")
        print("5 - Ver status do tracker")
        print("6 - Reanunciar meus chunks/arquivos ao tracker")
        print("0 - Sair")

        option = input("Escolha: ").strip()

        if option == "1":
            path = input("Nome do arquivo em shared/ ou caminho completo: ").strip()
            success, message = peer.share_file(path)
            print(message)

        elif option == "2":
            filename = input("Nome do arquivo: ").strip()
            success, result = peer.search_file(filename)
            if success:
                print(pretty_json(result))
            else:
                print(result)

        elif option == "3":
            filename = input("Nome do arquivo: ").strip()
            workers_input = input("Numero de workers paralelos (Enter para padrao 4): ").strip()
            max_workers = int(workers_input) if workers_input.isdigit() and int(workers_input) > 0 else 4
            success, message = peer.download_file(filename, max_workers=max_workers)
            print(message)

        elif option == "4":
            peer.show_local_catalog()

        elif option == "5":
            peer.show_tracker_status()

        elif option == "6":
            peer.announce_known_chunks()
            print("Anuncio finalizado.")

        elif option == "0":
            print("Encerrando peer...")
            peer.stop_event.set()
            break

        else:
            print("Opcao invalida.")


def main() -> None:
    args = parse_args()
    peer_id = args.peer_id or f"{args.public_host}:{args.port}"

    peer = PeerNode(
        peer_id=peer_id,
        listen_host=args.listen_host,
        public_host=args.public_host,
        peer_port=args.port,
        tracker_host=args.tracker_host,
        tracker_port=args.tracker_port,
        shared_dir=args.shared_dir,
        downloads_dir=args.downloads_dir,
        state_dir=args.state_dir,
        partial_dir=args.partial_dir,
        chunk_size=args.chunk_size,
    )

    peer.start()
    menu_loop(peer)


if __name__ == "__main__":
    main()
