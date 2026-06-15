from constants import TRACKER_HOST, TRACKER_PORT, SHARED_FOLDER, DOWNLOAD_FOLDER, PEER_HOST
import threading
import socket
import errno
import json
import sys
import os
import time  # Controla o tempo do loop do Heartbeat

os.makedirs(SHARED_FOLDER, exist_ok=True)
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# TAMANHO PADRÃO DO CHUNK: 512 KB em bytes
CHUNK_SIZE = 512 * 1024  


def start_heartbeat(peer_port):
    """Loop em segundo plano que avisa o Tracker que este Peer continua online."""
    time.sleep(1)
    while True:
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((TRACKER_HOST, TRACKER_PORT))

            request = {
                "action": "heartbeat",
                "peer_ip": PEER_HOST,
                "peer_port": peer_port
            }

            client.send(json.dumps(request).encode())
            client.recv(1024)
            client.close()
        except Exception as error:
            print(f"\n[HEARTBEAT ERRO] Tracker indisponível: {error}")
        
        time.sleep(5)


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

    threading.Thread(
        target=start_heartbeat,
        args=(peer_port,),
        daemon=True
    ).start()

    while True:
        conn, addr = server.accept()
        thread = threading.Thread(
            target=send_file,
            args=(conn,),
            daemon=True
        )
        thread.start()


# --- MODIFICADO: ENVIA APENAS O CHUNK SOLICITADO ---
def send_file(conn):
    try:
        data = conn.recv(1024).decode()
        if not data:
            conn.close()
            return

        # Espera um pedido em JSON contendo o filename e o chunk_index
        request = json.loads(data)
        filename = request["filename"]
        chunk_index = int(request["chunk_index"])

        filepath = os.path.join(SHARED_FOLDER, filename)

        if os.path.exists(filepath):
            with open(filepath, "rb") as file:
                # Move o ponteiro do arquivo para o início do bloco pedido
                file.seek(chunk_index * CHUNK_SIZE)
                
                # Lê exatamente a quantidade estipulada para um pedaço
                bytes_to_send = file.read(CHUNK_SIZE)
                
                # Descarrega o pedaço na conexão TCP
                conn.sendall(bytes_to_send)
    except Exception as e:
        print(f"[UPLOAD ERRO] Falha ao enviar chunk: {e}")
        
    conn.close()


# --- MODIFICADO: QUEBRA O ARQUIVO EM PARTES E REGISTRA CADA UMA DELAS NO TRACKER ---
def register_file(filename, peer_port):
    filepath = os.path.join(SHARED_FOLDER, filename)

    if not os.path.exists(filepath):
        message = f"O arquivo '{filename}' não existe na pasta shared."
        print(message)
        return False, message

    try:
        file_size = os.path.getsize(filepath)
        
        # Calcula a quantidade de partes (Se sobrar resto na divisão, ganha mais um chunk)
        total_chunks = (file_size // CHUNK_SIZE) + (1 if file_size % CHUNK_SIZE > 0 else 0)
        if total_chunks == 0: 
            total_chunks = 1

        print(f"[REGISTRO] Arquivo de {file_size} bytes detectado. Dividindo em {total_chunks} chunk(s)...")

        # Cadastra cada pedaço sequencialmente no catálogo do Tracker
        for chunk_index in range(total_chunks):
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((TRACKER_HOST, TRACKER_PORT))

            request = {
                "action": "register",
                "filename": filename,
                "chunk_index": chunk_index,
                "peer_ip": PEER_HOST,
                "peer_port": peer_port
            }

            client.send(json.dumps(request).encode())
            client.recv(4096)  # Aguarda a resposta de sucesso do chunk
            client.close()

        message = f"Sucesso: Todos os {total_chunks} chunks de '{filename}' foram registrados."
        return True, message

    except ConnectionRefusedError:
        message = "Não foi possível conectar ao tracker. Verifique se ele está rodando."
        print(message)
        return False, message
    except Exception as error:
        message = f"Erro ao registrar arquivo: {error}"
        print(message)
        return False, message


# --- MODIFICADO: SOLICITA A LISTA DE CHUNKS AO TRACKER ---
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

        # O Tracker atualizado agora devolve a chave "chunks" contendo o mapeamento das partes
        chunks = response.get("chunks", {})
        return True, chunks

    except ConnectionRefusedError:
        message = "Não foi possível conectar ao tracker. Verifique se ele está rodando."
        print(message)
        return False, message
    except Exception as error:
        message = f"Erro ao buscar arquivo: {error}"
        print(message)
        return False, message


# --- MODIFICADO: BAIXA CADA PEDAÇO INDIVIDUALMENTE E MONTA O ARQUIVO FINAL ---
def download_file(filename):
    success, result = search_file(filename)

    if not success:
        return False, result

    chunks_disponiveis = result

    if not chunks_disponiveis:
        message = "Arquivo não encontrado ou sem fontes ativas na rede."
        print(message)
        return False, message

    filepath = os.path.join(DOWNLOAD_FOLDER, filename)
    
    # Organiza os índices numéricos para garantir que vamos montar na sequência correta (0, 1, 2...)
    indices_ordenados = sorted([int(k) for k in chunks_disponiveis.keys()])

    print(f"[DOWNLOAD] Baixando {len(indices_ordenados)} partes de '{filename}'...")

    try:
        # Abre o arquivo de destino final em modo de escrita binária ("wb")
        with open(filepath, "wb") as file_destino:
            for chunk_index in indices_ordenados:
                # Recupera os peers que possuem o pedaço atual
                peers_do_chunk = chunks_disponiveis[str(chunk_index)]
                if not peers_do_chunk:
                    return False, f"Erro: A parte {chunk_index} perdeu as fontes durante a transmissão."

                # Escolhe o primeiro peer mapeado para fornecer o pedaço
                peer_ip, peer_port = peers_do_chunk[0]
                
                # Conecta diretamente no peer doador
                peer_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                peer_sock.connect((peer_ip, int(peer_port)))

                # Envia a requisição contendo o dicionário com o chunk desejado
                pedido = {"filename": filename, "chunk_index": chunk_index}
                peer_sock.send(json.dumps(pedido).encode())

                # Loop de recepção robusto para extrair o chunk completo
                bytes_do_chunk = b""
                while len(bytes_do_chunk) < CHUNK_SIZE:
                    dados = peer_sock.recv(4096)
                    if not dados:
                        break
                    bytes_do_chunk += dados

                # Grava o bloco recebido direto no arquivo final
                file_destino.write(bytes_do_chunk)
                peer_sock.close()
                print(f"[DOWNLOAD] Parte {chunk_index} unida com sucesso.")

        if os.path.getsize(filepath) == 0:
            message = "Download finalizado, mas o arquivo veio vazio."
            print(message)
            return False, message

        message = f"[DOWNLOAD FINALIZADO] '{filename}' reconstruído perfeitamente!"
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
                print("Chunks e fontes mapeadas encontrados:")
                print(json.dumps(result, indent=2))
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