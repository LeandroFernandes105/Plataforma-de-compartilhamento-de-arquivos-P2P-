default:
    just --list

build:
    docker compose up --build -d

clear:
    docker compose down -v

add-peer id port:
    python backend/peer.py --peer-id {{id}} --listen-host 127.0.0.1 --public-host 127.0.0.1 --port {{port}} --tracker-host 127.0.0.1 --tracker-port 5000