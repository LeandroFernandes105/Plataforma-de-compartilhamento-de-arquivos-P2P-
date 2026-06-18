import os

# Configuracoes padrao. Todas podem ser sobrescritas por argumentos de linha de comando.
TRACKER_HOST = os.getenv("TRACKER_HOST", "127.0.0.1")
TRACKER_PORT = int(os.getenv("TRACKER_PORT", "5000"))

# Endereco em que o servidor do peer escuta conexoes.
# Em rede local, use 0.0.0.0 para aceitar conexoes vindas de outros computadores.
PEER_LISTEN_HOST = os.getenv("PEER_LISTEN_HOST", "0.0.0.0")

# Endereco que o peer anuncia ao tracker.
# Em dois PCs, este valor deve ser o IP da maquina na rede local, ex.: 192.168.0.20.
PEER_PUBLIC_HOST = os.getenv("PEER_PUBLIC_HOST", "127.0.0.1")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

SHARED_FOLDER = os.path.join(BASE_DIR, "shared")
DOWNLOAD_FOLDER = os.path.join(PROJECT_DIR, "downloads")
STATE_FOLDER = os.path.join(PROJECT_DIR, "peer_state")
PARTIAL_FOLDER = os.path.join(PROJECT_DIR, "partial_chunks")

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", str(512 * 1024)))
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "5"))
PEER_TIMEOUT = int(os.getenv("PEER_TIMEOUT", "20"))
