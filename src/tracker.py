from constants import TRACKER_PORT
import socket
import threading
import json
import time  

HOST = '0.0.0.0'


files_index = {}


peers_last_seen = {}

TIMEOUT_LIMIT = 15  

def monitor_timeouts():
    """Thread que roda em segundo plano verificando quem ficou inativo."""
    print("[HEARTBEAT MONITOR] Iniciado com sucesso.")
    while True:
        time.sleep(5)  
        agora = time.time()
        peers_para_remover = []

        
        for peer_info, last_seen in list(peers_last_seen.items()):
            if agora - last_seen > TIMEOUT_LIMIT:
                peers_para_remover.append(peer_info)

        
        for peer_info in peers_para_remover:
            peer_str = f"{peer_info[0]}:{peer_info[1]}"
            print(f"[TIMEOUT] Peer {peer_str} ficou offline. Removendo da rede...")
            
            
            if peer_info in peers_last_seen:
                del peers_last_seen[peer_info]
            
            
            for filename, chunks in list(files_index.items()):
                for chunk_index, peers_list in list(chunks.items()):
                    if peer_info in peers_list:
                        peers_list.remove(peer_info)
                        print(f"[LIMPEZA] Removido {peer_str} do chunk {chunk_index} de '{filename}'")
                    
                    
                    if not peers_list:
                        del files_index[filename][chunk_index]
                
                
                if not files_index[filename]:
                    del files_index[filename]


def handle_client(conn, addr):
    while True:
        try:
            data = conn.recv(4096).decode()

            if not data:
                break

            request = json.loads(data)
            action = request["action"]

            
            if action == "heartbeat":
                peer_ip = request["peer_ip"]
                peer_port = int(request["peer_port"])
                peer_info = (peer_ip, peer_port)
                
                
                peers_last_seen[peer_info] = time.time()
                
                response = {"status": "success", "message": "Heartbeat recebido."}
                conn.send(json.dumps(response).encode())

            
            elif action == "register":
                filename = request["filename"]
                chunk_index = str(request["chunk_index"]) 
                peer_ip = request["peer_ip"]
                peer_port = int(request["peer_port"])
                peer_info = (peer_ip, peer_port)

                
                if filename not in files_index:
                    files_index[filename] = {}

                
                if chunk_index not in files_index[filename]:
                    files_index[filename][chunk_index] = []

                
                if peer_info not in files_index[filename][chunk_index]:
                    files_index[filename][chunk_index].append(peer_info)

                
                peers_last_seen[peer_info] = time.time()

                response = {
                    "status": "success",
                    "message": f"Chunk {chunk_index} de {filename} registrado."
                }
                conn.send(json.dumps(response).encode())

            
            elif action == "search":
                filename = request["filename"]
                
                
                chunks_disponiveis = files_index.get(filename, {})

                response = {
                    "status": "success",
                    "chunks": chunks_disponiveis
                }
                conn.send(json.dumps(response).encode())

        except:
            break

    conn.close()


def start_tracker():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, TRACKER_PORT))
    server.listen()

    print(f"[TRACKER ONLINE] Porta {TRACKER_PORT}")

    
    thread_monitor = threading.Thread(target=monitor_timeouts, daemon=True)
    thread_monitor.start()

    while True:
        conn, addr = server.accept()

        thread = threading.Thread(
            target=handle_client,
            args=(conn, addr)
        )
        thread.start()

if __name__ == "__main__":
    start_tracker()