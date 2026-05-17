import socket
import threading
import json

HOST = '0.0.0.0'
PORT = 5000


files_index = {}

def handle_client(conn, addr):
    print(f"[NOVA CONEXÃO] {addr}")

    while True:
        try:
            data = conn.recv(4096).decode()

            if not data:
                break

            request = json.loads(data)

            action = request["action"]

            # REGISTRAR ARQUIVO
            if action == "register":

                filename = request["filename"]
                peer_ip = request["peer_ip"]
                peer_port = request["peer_port"]

                if filename not in files_index:
                    files_index[filename] = []

                peer_info = (peer_ip, peer_port)

                if peer_info not in files_index[filename]:
                    files_index[filename].append(peer_info)

                response = {
                    "status": "success",
                    "message": f"{filename} registrado."
                }

                conn.send(json.dumps(response).encode())

            # BUSCAR ARQUIVO
            elif action == "search":

                filename = request["filename"]

                peers = files_index.get(filename, [])

                response = {
                    "status": "success",
                    "peers": peers
                }

                conn.send(json.dumps(response).encode())

        except:
            break

    conn.close()

def start_tracker():

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()

    print(f"[TRACKER ONLINE] Porta {PORT}")

    while True:

        conn, addr = server.accept()

        thread = threading.Thread(
            target=handle_client,
            args=(conn, addr)
        )

        thread.start()

start_tracker()