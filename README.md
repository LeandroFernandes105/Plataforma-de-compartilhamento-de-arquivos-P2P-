# Plataforma de Compartilhamento de Arquivos P2P

Projeto em Python para simular uma rede P2P.

## Conceitos implementados

- Tracker como indice da rede;
- Peer com servidor de upload;
- Arquivo dividido em chunks;
- Hash do arquivo completo;
- Hash individual de cada chunk;
- Seed explicito: peer com 100% dos chunks;
- Leecher/parcial: peer com alguns chunks;
- Peer que baixa um chunk ja pode anunciar e enviar esse chunk;
- Peer que termina o download valida o arquivo e vira seed automaticamente;
- Heartbeat para remover peers offline do tracker;
- Catalogo local persistente em `peer_state/`.

## Estrutura

```text
.
├── README.md
└── src/
    ├── constants.py
    ├── peer.py
    ├── protocol.py
    ├── tracker.py
    └── shared/
```

Pastas criadas durante a execucao:

```text
downloads/       arquivos completos baixados
partial_chunks/  chunks parciais enquanto baixa
peer_state/      catalogo local do peer
```

## Como rodar localmente em uma maquina

Terminal 1:

```bash
python src/tracker.py --host 127.0.0.1 --port 5000
```

Terminal 2, Peer A:

```bash
python src/peer.py --peer-id peer-a --listen-host 127.0.0.1 --public-host 127.0.0.1 --port 6001 --tracker-host 127.0.0.1 --tracker-port 5000
```

Terminal 3, Peer B:

```bash
python src/peer.py --peer-id peer-b --listen-host 127.0.0.1 --public-host 127.0.0.1 --port 6002 --tracker-host 127.0.0.1 --tracker-port 5000
```

No Peer A:

```text
1 - Compartilhar arquivo local (vira seed)
```

Digite um arquivo que exista em `src/shared/`, por exemplo:

```text
teste.txt
```

No Peer B:

```text
2 - Buscar arquivo no tracker
3 - Baixar arquivo
5 - Ver status do tracker
```

Depois do download, o tracker deve mostrar `seed_count: 2` para o arquivo baixado.

## Como rodar em dois computadores

Exemplo:

```text
PC 1 = 192.168.0.10
PC 2 = 192.168.0.20
```

No PC 1, tracker:

```bash
python src/tracker.py --host 0.0.0.0 --port 5000
```

No PC 1, Peer A:

```bash
python src/peer.py --peer-id peer-a --listen-host 0.0.0.0 --public-host 192.168.0.10 --port 6001 --tracker-host 192.168.0.10 --tracker-port 5000
```

No PC 2, Peer B:

```bash
python src/peer.py --peer-id peer-b --listen-host 0.0.0.0 --public-host 192.168.0.20 --port 6002 --tracker-host 192.168.0.10 --tracker-port 5000
```

Importante: entre computadores diferentes, nao use `127.0.0.1` como `--public-host`. Use o IP real da maquina na rede local.

## Fluxo da logica de seed

1. O Peer A compartilha um arquivo.
2. O arquivo e dividido em chunks.
3. O Peer A registra todos os chunks no tracker.
4. Como tem 100% dos chunks, o Peer A e seed.
5. O Peer B busca o arquivo no tracker.
6. O Peer B baixa os chunks diretamente do Peer A.
7. A cada chunk valido, o Peer B anuncia esse chunk ao tracker e ja pode enviar esse pedaco.
8. Ao completar todos os chunks, o Peer B monta o arquivo final.
9. O Peer B valida o hash final.
10. O Peer B registra todos os chunks e vira seed.

## Testando downloads simultâneos (múltiplos peers)

Para demonstrar o download paralelo, é necessário ter ao menos dois seeds antes de iniciar o leecher.
Crie dois seeds com o mesmo arquivo (Peer A e Peer B) e depois suba um terceiro peer e baixe o arquivo:

Terminal 4, Peer C:

```bash
python src/peer.py --peer-id peer-c --listen-host 127.0.0.1 --public-host 127.0.0.1 --port 6003 --tracker-host 127.0.0.1 --tracker-port 5000
```

No Peer C, escolha a opção `3`, informe o nome do arquivo e o número de workers paralelos.

Nos logs do Peer C, chunks chegando de `peer-a` e `peer-b` intercalados e fora de ordem confirmam que o download paralelo está funcionando.
Ao final, a opção `5` deve exibir `seed_count: 3`no arquivo testado.

O número de workers pode ser ajustado conforme o cenário: mais workers aproveitam melhor redes com muitos peers disponíveis, mas podem causar sobrecarga em redes com poucos seeds ou alta latência.

## Menu do peer

```text
1 - Compartilhar arquivo local (vira seed)
2 - Buscar arquivo no tracker
3 - Baixar arquivo
4 - Ver catalogo local
5 - Ver status do tracker
6 - Reanunciar meus chunks/arquivos ao tracker
0 - Sair
```

## Observacoes

- O tracker guarda metadados e fontes, nao guarda arquivos.
- O arquivo em si nao grava que e seed.
- O catalogo local do peer grava quais arquivos/chunks aquele peer possui.
- O tracker calcula quem e seed verificando se um peer possui todos os chunks de um arquivo.
- Se um peer sair da rede e parar de enviar heartbeat, o tracker remove os chunks dele apos o timeout.
