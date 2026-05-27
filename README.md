# Plataforma de Compartilhamento de Arquivos P2P

Este projeto é um protótipo de uma plataforma de compartilhamento de arquivos baseada no modelo Peer-to-Peer (P2P), desenvolvido em Python.

A aplicação permite simular uma rede P2P simples, na qual um peer registra um arquivo em um tracker, outro peer consulta esse tracker para localizar o arquivo e, em seguida, realiza o download diretamente do peer que possui o conteúdo.

O tracker não armazena os arquivos. Ele atua apenas como um catálogo, registrando quais peers possuem determinados arquivos. A transferência dos arquivos ocorre diretamente entre os peers.

## Funcionalidades do protótipo

- Registro de arquivos no tracker;
- Busca de arquivos disponíveis na rede;
- Download direto entre peers;
- Simulação de dois peers locais;
- Interface de demonstração em Streamlit;
- Comunicação entre processos usando sockets TCP;
- Uso de threads para manter os peers disponíveis para conexões.

## Tecnologias utilizadas

- Python;
- Sockets TCP;
- Threads;
- JSON;
- Streamlit.

## Estrutura do projeto

```text
.
├── README.md
├── .gitignore
└── src/
    ├── app_streamlit.py
    ├── constants.py
    ├── peer.py
    ├── tracker.py
    └── shared/
        ├── teste.txt
```

## Como funciona

O funcionamento básico da aplicação ocorre em três etapas principais:

1. Um peer registra um arquivo no tracker.
2. Outro peer busca esse arquivo no tracker.
3. O download é feito diretamente entre os peers.

Fluxo simplificado:

```text
Peer 1 registra arquivo → Tracker salva a localização
Peer 2 busca arquivo → Tracker retorna o Peer 1
Peer 2 baixa o arquivo diretamente do Peer 1
```

A interface em Streamlit funciona como um painel de demonstração. Ela permite visualizar e controlar dois peers locais na mesma tela, facilitando a apresentação do funcionamento do protótipo.

Mesmo com a interface, a lógica P2P se mantém: o tracker apenas localiza os arquivos e a transferência continua acontecendo diretamente entre os peers.

## Como executar

### 1. Instalar as dependências

O projeto utiliza Python e Streamlit. Para instalar o Streamlit, execute:

```bash
pip install streamlit
```

### 2. Executar o tracker

Na raiz do projeto, execute:

```bash
python src/tracker.py
```

O tracker ficará aguardando conexões dos peers na porta `5000`.

### 3. Executar a interface Streamlit

Em outro terminal, ainda na raiz do projeto, execute:

```bash
streamlit run src/app_streamlit.py
```

```bash
python -m streamlit run src/app_streamlit.py
```

A interface será aberta no navegador.

## Como testar pela interface

Com o tracker rodando e a interface aberta:

1. Clique em **Iniciar Peer 1**.
2. Clique em **Iniciar Peer 2**.
3. No campo do Peer 1, digite o nome de um arquivo existente em `src/shared/`.

Exemplo:

```text
teste.txt
```

4. Clique em **Registrar no tracker**.
5. No campo do Peer 2, digite o mesmo nome do arquivo.
6. Clique em **Buscar**.
7. Após o arquivo ser localizado, clique em **Baixar**.
8. O arquivo baixado será salvo na pasta `downloads/`.

## Pastas importantes

### `src/shared/`

Pasta onde ficam os arquivos que podem ser compartilhados pelos peers.

Para registrar um arquivo no tracker, ele precisa existir primeiro nessa pasta.

Exemplo:

```text
src/shared/teste.txt
```

### `downloads/`

Pasta onde são salvos os arquivos baixados.

Essa pasta é gerada durante os testes e não precisa ser versionada no Git.
- Arthur
- Gabriel
- Leandro
