import socket
import threading
import json
import os

TRACKER_HOST = '127.0.0.1'
TRACKER_PORT = 5000

PEER_HOST = '127.0.0.1'
PEER_PORT = 6001

SHARED_FOLDER = "shared"
DOWNLOAD_FOLDER = "../downloads"

os.makedirs(SHARED_FOLDER, exist_ok=True)
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)



def upload_server():

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((PEER_HOST, PEER_PORT))
    server.listen()

    print(f"[PEER ONLINE] Porta {PEER_PORT}")

    while True:

        conn, addr = server.accept()

        thread = threading.Thread(
            target=send_file,
            args=(conn,)
        )

        thread.start()

def send_file(conn):

    filename = conn.recv(1024).decode()

    filepath = os.path.join(SHARED_FOLDER, filename)

    if os.path.exists(filepath):

        with open(filepath, "rb") as file:

            while True:

                bytes_read = file.read(4096)

                if not bytes_read:
                    break

                conn.send(bytes_read)

    conn.close()



def register_file(filename):

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((TRACKER_HOST, TRACKER_PORT))

    request = {
        "action": "register",
        "filename": filename,
        "peer_ip": PEER_HOST,
        "peer_port": PEER_PORT
    }

    client.send(json.dumps(request).encode())

    response = json.loads(client.recv(4096).decode())

    print(response)

    client.close()



def search_file(filename):

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((TRACKER_HOST, TRACKER_PORT))

    request = {
        "action": "search",
        "filename": filename
    }

    client.send(json.dumps(request).encode())

    response = json.loads(client.recv(4096).decode())

    client.close()

    return response["peers"]



def download_file(filename):

    peers = search_file(filename)

    if not peers:
        print("Arquivo não encontrado.")
        return

    peer_ip, peer_port = peers[0]

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((peer_ip, peer_port))

    client.send(filename.encode())

    filepath = os.path.join(DOWNLOAD_FOLDER, filename)

    with open(filepath, "wb") as file:

        while True:

            bytes_read = client.recv(4096)

            if not bytes_read:
                break

            file.write(bytes_read)

    client.close()

    print(f"[DOWNLOAD FINALIZADO] {filename}")



threading.Thread(target=upload_server, daemon=True).start()

while True:

    print("\n1 - Registrar arquivo")
    print("2 - Buscar arquivo")
    print("3 - Download arquivo")

    option = input("Escolha: ")

    if option == "1":

        filename = input("Nome do arquivo: ")
        register_file(filename)

    elif option == "2":

        filename = input("Nome do arquivo: ")

        peers = search_file(filename)

        print("Peers encontrados:")
        print(peers)

    elif option == "3":

        filename = input("Nome do arquivo: ")
        download_file(filename)