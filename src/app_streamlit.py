import os
import threading
import streamlit as st

from constants import SHARED_FOLDER, DOWNLOAD_FOLDER, TRACKER_HOST, TRACKER_PORT
from peer import upload_server, register_file, search_file, download_file


st.set_page_config(
    page_title="Plataforma P2P",
    layout="wide",
    initial_sidebar_state="collapsed"
)


PEER_1_PORT = 6001
PEER_2_PORT = 6002


def init_state():
    defaults = {
        "peer_1_started": False,
        "peer_2_started": False,
        "last_search": [],
        "logs": [],
        "last_downloaded_file": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def add_log(message):
    st.session_state.logs.append(message)


def list_files(folder):
    if not os.path.exists(folder):
        return []

    return sorted([
        file
        for file in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, file))
    ])


def start_peer(peer_number, peer_port):
    state_key = f"peer_{peer_number}_started"

    if st.session_state[state_key]:
        return False, f"Peer {peer_number} já está ativo."

    thread = threading.Thread(
        target=upload_server,
        args=(peer_port,),
        daemon=True
    )

    thread.start()

    st.session_state[state_key] = True
    add_log(f"Peer {peer_number} iniciado na porta {peer_port}.")

    return True, f"Peer {peer_number} iniciado."


def status_badge(is_online):
    if is_online:
        return '<span class="badge online">Online</span>'

    return '<span class="badge offline">Inativo</span>'


def render_file_cards(files, empty_message):
    if not files:
        st.markdown(
            f"""
            <div class="empty-state">
                {empty_message}
            </div>
            """,
            unsafe_allow_html=True
        )
        return

    for file in files:
        st.markdown(
            f"""
            <div class="file-card">
                <div class="file-title">{file}</div>
            </div>
            """,
            unsafe_allow_html=True
        )


def show_downloaded_file(filename):
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)

    if not os.path.exists(filepath):
        st.warning("O arquivo baixado não foi encontrado na pasta downloads.")
        return

    st.markdown("#### Arquivo baixado")

    st.markdown(
        f"""
        <div class="download-card">
            <div class="download-name">{filename}</div>
            <div class="download-path">Salvo em: downloads/{filename}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    with open(filepath, "rb") as file:
        st.download_button(
            label="Abrir ou salvar arquivo",
            data=file,
            file_name=filename,
            mime="application/octet-stream",
            use_container_width=True
        )

    if filename.lower().endswith(".txt"):
        try:
            with open(filepath, "r", encoding="utf-8") as file:
                content = file.read()

            st.text_area(
                "Prévia do conteúdo",
                value=content,
                height=160,
                disabled=True
            )

        except UnicodeDecodeError:
            st.info("O arquivo foi baixado, mas não pôde ser exibido como texto.")


init_state()


st.markdown(
    """
    <style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1220px;
    }

    .hero {
        border: 1px solid #273449;
        border-radius: 18px;
        background: linear-gradient(135deg, #0f172a 0%, #111827 55%, #172554 100%);
        padding: 26px 30px;
        margin-bottom: 22px;
    }

    .hero-label {
        color: #38bdf8;
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 8px;
    }

    .hero-title {
        color: #f8fafc;
        font-size: 34px;
        font-weight: 850;
        line-height: 1.15;
        margin: 0;
    }

    .hero-subtitle {
        color: #cbd5e1;
        font-size: 15px;
        line-height: 1.55;
        max-width: 850px;
        margin-top: 10px;
        margin-bottom: 0;
    }

    .metric-card {
        border: 1px solid #273449;
        border-radius: 16px;
        background: #111827;
        padding: 18px 20px;
        min-height: 118px;
        box-shadow: 0 10px 24px rgba(0, 0, 0, 0.16);
    }

    .metric-label {
        color: #94a3b8;
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin-bottom: 8px;
    }

    .metric-value {
        color: #f8fafc;
        font-size: 24px;
        font-weight: 850;
        margin-bottom: 6px;
    }

    .metric-description {
        color: #cbd5e1;
        font-size: 13px;
        line-height: 1.45;
        margin: 0;
    }

    .section-title {
        color: #f8fafc;
        font-size: 21px;
        font-weight: 850;
        margin: 26px 0 14px 0;
    }

    .peer-card {
        border: 1px solid #273449;
        border-radius: 18px;
        background: #111827;
        padding: 22px;
        box-shadow: 0 10px 24px rgba(0, 0, 0, 0.16);
    }

    .peer-head {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 12px;
        margin-bottom: 18px;
    }

    .peer-title {
        color: #f8fafc;
        font-size: 22px;
        font-weight: 850;
        margin: 0;
    }

    .peer-meta {
        color: #94a3b8;
        font-size: 13px;
        margin-top: 4px;
    }

    .badge {
        display: inline-block;
        padding: 6px 12px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 800;
        white-space: nowrap;
    }

    .online {
        color: #bbf7d0;
        border: 1px solid rgba(34, 197, 94, 0.55);
        background: rgba(34, 197, 94, 0.12);
    }

    .offline {
        color: #fed7aa;
        border: 1px solid rgba(245, 158, 11, 0.55);
        background: rgba(245, 158, 11, 0.12);
    }

    .file-card {
        border: 1px solid #273449;
        border-radius: 14px;
        background: #0f172a;
        padding: 13px 15px;
        margin-bottom: 10px;
    }

    .file-title {
        color: #f8fafc;
        font-size: 14px;
        font-weight: 800;
    }

    .empty-state {
        border: 1px dashed #334155;
        border-radius: 14px;
        background: #0f172a;
        padding: 16px;
        color: #94a3b8;
        text-align: center;
        font-size: 14px;
    }

    .result-card {
        border: 1px solid #273449;
        border-radius: 14px;
        background: #0f172a;
        padding: 13px 15px;
        margin-bottom: 10px;
    }

    .result-title {
        color: #f8fafc;
        font-size: 14px;
        font-weight: 800;
    }

    .result-text {
        color: #94a3b8;
        font-size: 13px;
        margin-top: 4px;
    }

    .download-card {
        border: 1px solid #273449;
        border-radius: 14px;
        background: #0f172a;
        padding: 14px 16px;
        margin-bottom: 12px;
    }

    .download-name {
        color: #f8fafc;
        font-size: 15px;
        font-weight: 850;
    }

    .download-path {
        color: #94a3b8;
        font-size: 13px;
        margin-top: 4px;
    }

    .log-item {
        border-left: 3px solid #38bdf8;
        background: rgba(56, 189, 248, 0.08);
        border-radius: 10px;
        padding: 10px 12px;
        margin-bottom: 8px;
        color: #cbd5e1;
        font-size: 14px;
    }

    .stButton > button {
        border-radius: 10px;
        border: 1px solid #334155;
        background: #1e293b;
        color: #f8fafc;
        font-weight: 750;
        height: 43px;
    }

    .stButton > button:hover {
        border-color: #38bdf8;
        background: #273449;
        color: #ffffff;
    }

    div[data-testid="stTextInput"] input {
        border-radius: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True
)


st.markdown(
    """
    <div class="hero">
        <div class="hero-label">Painel de demonstração</div>
        <h1 class="hero-title">Plataforma de Compartilhamento de Arquivos P2P</h1>
        <p class="hero-subtitle">
            Simulação visual de dois peers locais. O tracker localiza os arquivos,
            e a transferência continua ocorrendo diretamente entre os peers.
        </p>
    </div>
    """,
    unsafe_allow_html=True
)


shared_files = list_files(SHARED_FOLDER)
downloaded_files = list_files(DOWNLOAD_FOLDER)
active_peers = int(st.session_state.peer_1_started) + int(st.session_state.peer_2_started)

metric_1, metric_2, metric_3 = st.columns(3)

with metric_1:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Tracker</div>
            <div class="metric-value">{TRACKER_HOST}:{TRACKER_PORT}</div>
            <p class="metric-description">Catálogo central de localização.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

with metric_2:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Peers ativos</div>
            <div class="metric-value">{active_peers}/2</div>
            <p class="metric-description">Participantes locais da simulação.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

with metric_3:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Arquivos compartilhados</div>
            <div class="metric-value">{len(shared_files)}</div>
            <p class="metric-description">Itens disponíveis em src/shared.</p>
        </div>
        """,
        unsafe_allow_html=True
    )


st.markdown('<div class="section-title">Operação dos peers</div>', unsafe_allow_html=True)

peer_1_col, peer_2_col = st.columns(2)

with peer_1_col:
    st.markdown(
        f"""
        <div class="peer-card">
            <div class="peer-head">
                <div>
                    <div class="peer-title">Peer 1</div>
                    <div class="peer-meta">Porta {PEER_1_PORT} | compartilha arquivos</div>
                </div>
                {status_badge(st.session_state.peer_1_started)}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if st.button("Iniciar Peer 1", use_container_width=True):
        success, message = start_peer(1, PEER_1_PORT)

        if success:
            st.success(message)
        else:
            st.info(message)

    peer_1_filename = st.text_input(
        "Arquivo do Peer 1",
        placeholder="Exemplo: teste.txt",
        key="peer_1_filename"
    )

    if st.button("Registrar no tracker", use_container_width=True):
        if not st.session_state.peer_1_started:
            st.error("Inicie o Peer 1 antes de registrar.")
        elif not peer_1_filename:
            st.error("Informe o nome do arquivo.")
        else:
            success, message = register_file(peer_1_filename, PEER_1_PORT)

            if success:
                st.success("Arquivo registrado.")
            else:
                st.error(message)

            add_log(f"Peer 1 | registro de {peer_1_filename}: {message}")


with peer_2_col:
    st.markdown(
        f"""
        <div class="peer-card">
            <div class="peer-head">
                <div>
                    <div class="peer-title">Peer 2</div>
                    <div class="peer-meta">Porta {PEER_2_PORT} | busca e download</div>
                </div>
                {status_badge(st.session_state.peer_2_started)}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if st.button("Iniciar Peer 2", use_container_width=True):
        success, message = start_peer(2, PEER_2_PORT)

        if success:
            st.success(message)
        else:
            st.info(message)

    peer_2_filename = st.text_input(
        "Arquivo para buscar",
        placeholder="Exemplo: teste.txt",
        key="peer_2_filename"
    )

    search_col, download_col = st.columns(2)

    with search_col:
        if st.button("Buscar", use_container_width=True):
            if not st.session_state.peer_2_started:
                st.error("Inicie o Peer 2 antes de buscar.")
            elif not peer_2_filename:
                st.error("Informe o nome do arquivo.")
            else:
                success, result = search_file(peer_2_filename)

                if success:
                    st.session_state.last_search = result

                    if result:
                        st.success("Arquivo localizado.")
                    else:
                        st.warning("Nenhum peer encontrado.")

                    add_log(f"Peer 2 | busca por {peer_2_filename}: {result}")
                else:
                    st.session_state.last_search = []
                    st.error(result)
                    add_log(f"Peer 2 | falha na busca por {peer_2_filename}: {result}")

    with download_col:
        if st.button("Baixar", use_container_width=True):
            if not st.session_state.peer_2_started:
                st.error("Inicie o Peer 2 antes de baixar.")
            elif not peer_2_filename:
                st.error("Informe o nome do arquivo.")
            else:
                success, message = download_file(peer_2_filename)

                if success:
                    st.session_state.last_downloaded_file = peer_2_filename
                    st.success("Download concluído.")
                else:
                    st.error(message)

                add_log(f"Peer 2 | download de {peer_2_filename}: {message}")


results_col, downloads_col = st.columns([1, 1])

with results_col:
    st.markdown('<div class="section-title">Resultado da busca</div>', unsafe_allow_html=True)

    if st.session_state.last_search:
        for peer in st.session_state.last_search:
            st.markdown(
                f"""
                <div class="result-card">
                    <div class="result-title">Peer encontrado</div>
                    <div class="result-text">Endereço: {peer[0]} | Porta: {peer[1]}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
    else:
        st.markdown(
            """
            <div class="empty-state">
                Nenhuma busca realizada.
            </div>
            """,
            unsafe_allow_html=True
        )

with downloads_col:
    st.markdown('<div class="section-title">Download</div>', unsafe_allow_html=True)

    if st.session_state.last_downloaded_file:
        show_downloaded_file(st.session_state.last_downloaded_file)
    else:
        st.markdown(
            """
            <div class="empty-state">
                Nenhum arquivo baixado nesta sessão.
            </div>
            """,
            unsafe_allow_html=True
        )


files_col_1, files_col_2 = st.columns(2)

with files_col_1:
    st.markdown('<div class="section-title">Shared</div>', unsafe_allow_html=True)
    render_file_cards(shared_files, "Nenhum arquivo disponível em src/shared.")

with files_col_2:
    st.markdown('<div class="section-title">Downloads</div>', unsafe_allow_html=True)
    render_file_cards(list_files(DOWNLOAD_FOLDER), "Nenhum arquivo salvo em downloads.")


st.markdown('<div class="section-title">Atividade recente</div>', unsafe_allow_html=True)

if st.session_state.logs:
    for log in reversed(st.session_state.logs[-6:]):
        st.markdown(
            f"""
            <div class="log-item">{log}</div>
            """,
            unsafe_allow_html=True
        )
else:
    st.markdown(
        """
        <div class="empty-state">
            Nenhuma atividade registrada.
        </div>
        """,
        unsafe_allow_html=True
    )