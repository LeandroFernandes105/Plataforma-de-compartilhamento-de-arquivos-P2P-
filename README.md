# Plataforma de Compartilhamento de Arquivos P2P

Projeto desenvolvido como trabalho acadêmico para a disciplina de **Computação Paralela e Distribuída**, do **IFSP**.

A aplicação simula uma rede P2P para compartilhamento de arquivos entre peers. O sistema utiliza um tracker para registrar quais peers estão online e quais partes de cada arquivo estão disponíveis na rede. A transferência dos arquivos acontece diretamente entre os peers, por meio de chunks.

## Objetivo

O objetivo do projeto é demonstrar conceitos de sistemas distribuídos aplicados a uma rede P2P, incluindo:

* comunicação entre processos;
* descoberta de peers por meio de um tracker;
* divisão de arquivos em chunks;
* download direto entre peers;
* controle de seeds e leechers;
* formação de uma swarm para cada arquivo;
* exposição de dados da rede para um futuro front-end.

## Componentes

### Tracker

O tracker atua como um catálogo da rede. Ele não armazena arquivos, apenas mantém informações sobre:

* peers conectados;
* arquivos disponíveis;
* chunks de cada arquivo;
* quais peers possuem cada chunk;
* quantidade de seeds;
* quantidade de leechers.

### Peer

O peer é o nó que participa da rede P2P. Ele pode:

* compartilhar arquivos locais;
* dividir arquivos em chunks;
* enviar chunks para outros peers;
* baixar chunks de outros peers;
* anunciar chunks baixados ao tracker;
* virar seed ao completar o download.

### Seed e Leecher

Um **seed** é um peer que possui todos os chunks de um arquivo e pode compartilhá-lo completamente.

Um **leecher** é um peer que ainda está baixando o arquivo, mas já possui alguns chunks. Durante o download, ele pode anunciar os chunks já recebidos e ajudar outros peers.

Quando um leecher completa todos os chunks e valida o arquivo, ele passa automaticamente a ser seed.

## Funcionamento geral

Fluxo simplificado:

```text
1. Peer A compartilha um arquivo.
2. O arquivo é dividido em chunks.
3. Peer A anuncia os chunks ao tracker.
4. Peer B busca o arquivo no tracker.
5. Peer B baixa os chunks diretamente do Peer A.
6. Durante o download, Peer B anuncia os chunks que já possui.
7. Ao finalizar o download, Peer B vira seed.
8. Outros peers podem baixar o arquivo de Peer A, Peer B ou ambos.
```

A transferência real dos arquivos acontece diretamente entre peers. O tracker apenas informa onde os chunks estão disponíveis.

## Executando localmente

Abra três terminais na pasta do projeto.

### Terminal 1: iniciar tracker e API

```bash
python src/tracker.py --host 127.0.0.1 --port 5000 --api-host 127.0.0.1 --api-port 8000
```

Portas usadas:

```text
5000 -> comunicação entre peers e tracker
8000 -> API HTTP para consulta do front
```

### Terminal 2: iniciar Peer A

```bash
python src/peer.py --peer-id peer-a --listen-host 127.0.0.1 --public-host 127.0.0.1 --port 6001 --tracker-host 127.0.0.1 --tracker-port 5000
```

No menu, escolha a opção de compartilhar arquivo local.

O arquivo deve estar na pasta:

```text
src/shared/
```

### Terminal 3: iniciar Peer B

```bash
python src/peer.py --peer-id peer-b --listen-host 127.0.0.1 --public-host 127.0.0.1 --port 6002 --tracker-host 127.0.0.1 --tracker-port 5000
```

No menu, é possível buscar e baixar arquivos disponíveis na rede.

Após concluir o download, o Peer B passa automaticamente a ser seed do arquivo baixado.

## Testando com três peers

Para iniciar um terceiro peer:

```bash
python src/peer.py --peer-id peer-c --listen-host 127.0.0.1 --public-host 127.0.0.1 --port 6003 --tracker-host 127.0.0.1 --tracker-port 5000
```

Esse teste permite validar que múltiplos peers podem virar seeds do mesmo arquivo.

## API HTTP do Tracker

O tracker possui uma API HTTP somente de leitura para facilitar a integração com um futuro front-end.

A API fica implementada no arquivo:

```text
src/tracker.py
```

Ela é iniciada junto com o tracker usando os parâmetros:

```bash
--api-host 127.0.0.1 --api-port 8000
```

URL base local:

```text
http://127.0.0.1:8000
```

### Endpoints disponíveis

```http
GET /api/health
```

Verifica se a API está online.

```http
GET /api/status
```

Retorna o estado geral da rede, incluindo arquivos, peers, seeds, leechers e chunks.

```http
GET /api/files
```

Lista os arquivos disponíveis na rede.

```http
GET /api/peers
```

Lista os peers conhecidos pelo tracker.

```http
GET /api/files/<filename>
```

Retorna os detalhes de um arquivo específico.

Exemplo:

```text
http://127.0.0.1:8000/api/files/iptables.mp4
```

```http
GET /api/swarm/<filename>
```

Retorna a swarm de um arquivo, ou seja, os peers que participam do compartilhamento daquele arquivo.

Exemplo:

```text
http://127.0.0.1:8000/api/swarm/iptables.mp4
```
