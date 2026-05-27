from constants import TRACKER_HOST, TRACKER_PORT, SHARED_FOLDER, DOWNLOAD_FOLDER, PEER_HOST
import threading
import socket
import errno
import json
import sys
import os


os.makedirs(SHARED_FOLDER, exist_ok=True)
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)


def upload_server(peer_port):
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((PEER_HOST, peer_port))
        server.listen()

    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            print("A porta selecionada já está em uso")
            return

        print(f"Erro ao iniciar servidor do peer: {e}")
        return

    print(f"[PEER ONLINE] Porta {peer_port}")

    while True:
        conn, addr = server.accept()

        thread = threading.Thread(
            target=send_file,
            args=(conn,),
            daemon=True
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

                conn.sendall(bytes_read)

    conn.close()


def register_file(filename, peer_port):
    filepath = os.path.join(SHARED_FOLDER, filename)

    if not os.path.exists(filepath):
        message = f"O arquivo '{filename}' não existe na pasta shared."
        print(message)
        return False, message

    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((TRACKER_HOST, TRACKER_PORT))

        request = {
            "action": "register",
            "filename": filename,
            "peer_ip": PEER_HOST,
            "peer_port": peer_port
        }

        client.send(json.dumps(request).encode())

        response = json.loads(client.recv(4096).decode())

        client.close()

        print(response)
        return True, response

    except ConnectionRefusedError:
        message = "Não foi possível conectar ao tracker. Verifique se ele está rodando."
        print(message)
        return False, message

    except Exception as error:
        message = f"Erro ao registrar arquivo: {error}"
        print(message)
        return False, message


def search_file(filename):
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((TRACKER_HOST, TRACKER_PORT))

        request = {
            "action": "search",
            "filename": filename
        }

        client.send(json.dumps(request).encode())

        response = json.loads(client.recv(4096).decode())

        client.close()

        peers = response.get("peers", [])

        return True, peers

    except ConnectionRefusedError:
        message = "Não foi possível conectar ao tracker. Verifique se ele está rodando."
        print(message)
        return False, message

    except Exception as error:
        message = f"Erro ao buscar arquivo: {error}"
        print(message)
        return False, message


def download_file(filename):
    success, result = search_file(filename)

    if not success:
        print(result)
        return False, result

    peers = result

    if not peers:
        message = "Arquivo não encontrado."
        print(message)
        return False, message

    peer_ip, peer_port = peers[0]

    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((peer_ip, int(peer_port)))

        client.send(filename.encode())

        filepath = os.path.join(DOWNLOAD_FOLDER, filename)

        with open(filepath, "wb") as file:
            while True:
                bytes_read = client.recv(4096)

                if not bytes_read:
                    break

                file.write(bytes_read)

        client.close()

        if os.path.getsize(filepath) == 0:
            message = "Download finalizado, mas o arquivo veio vazio."
            print(message)
            return False, message

        message = f"[DOWNLOAD FINALIZADO] {filename}"
        print(message)
        return True, message

    except Exception as error:
        message = f"Erro ao baixar arquivo: {error}"
        print(message)
        return False, message


def cli_main():
    try:
        peer_port = int(sys.argv[1])

    except IndexError:
        print("Uso correto: python peer.py <porta>")
        return

    except ValueError:
        print("Parâmetro informado é inválido. Informe uma porta numérica.")
        return

    threading.Thread(
        target=upload_server,
        args=(peer_port,),
        daemon=True
    ).start()

    while True:
        print("\n1 - Registrar arquivo")
        print("2 - Buscar arquivo")
        print("3 - Download arquivo")
        print("4 - Sair")

        option = input("Escolha: ")

        if option == "1":
            filename = input("Nome do arquivo: ")
            success, message = register_file(filename, peer_port)
            print(message)

        elif option == "2":
            filename = input("Nome do arquivo: ")

            success, result = search_file(filename)

            if success:
                print("Peers encontrados:")
                print(result)
            else:
                print(result)

        elif option == "3":
            filename = input("Nome do arquivo: ")
            success, message = download_file(filename)
            print(message)

        elif option == "4":
            print("Encerrando peer...")
            break

        else:
            print("Opção inválida.")


if __name__ == "__main__":
    cli_main()