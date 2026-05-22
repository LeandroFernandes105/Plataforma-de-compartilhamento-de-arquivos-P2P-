# Protótipo de Plataforma de Compartilhamento de Arquivos P2P

Este projeto é um protótipo de uma aplicação de compartilhamento de arquivos no modelo P2P, desenvolvido em Python.

A ideia principal é permitir que diferentes peers compartilhem arquivos entre si com o auxílio de um tracker central. O tracker não armazena os arquivos; ele apenas registra quais peers possuem determinado arquivo. Quando um peer deseja baixar um arquivo, ele consulta o tracker para descobrir quem possui esse arquivo e, em seguida, realiza o download diretamente do outro peer.

Nesta versão inicial, o protótipo possui as funcionalidades mínimas para validar a comunicação entre os componentes do sistema: registrar arquivos, buscar arquivos disponíveis e realizar o download entre peers.

## Tecnologias utilizadas

- Python
- Sockets TCP
- Threads
- JSON

## Estrutura do projeto

```text
tracker/
  tracker.py

peer/
  peer.py
  peer1.py
  shared/
    teste.txt
```

## Como executar

### 1. Executar o tracker

Abra um terminal na pasta principal do projeto e execute:

```bash
python tracker/tracker.py
```

O tracker ficará aguardando conexões dos peers.

### 2. Executar o primeiro peer

Abra outro terminal e execute:

```bash
python peer/peer.py
```

Esse peer pode registrar arquivos no tracker e compartilhar arquivos com outros peers.

### 3. Executar o segundo peer

Abra mais um terminal e execute:

```bash
python peer/peer1.py
```

Esse segundo peer pode buscar e baixar arquivos compartilhados pelo primeiro peer.

## Exemplo de uso

Com o tracker e os dois peers em execução:

1. No primeiro peer, escolha a opção de registrar arquivo.
2. Digite o nome de um arquivo existente na pasta `peer/shared/`, por exemplo:

```text
teste.txt
```

3. No segundo peer, escolha a opção de buscar arquivo.
4. Digite o mesmo nome do arquivo:

```text
teste.txt
```

5. Após localizar o peer que possui o arquivo, escolha a opção de download.
6. O arquivo será transferido diretamente de um peer para o outro.
