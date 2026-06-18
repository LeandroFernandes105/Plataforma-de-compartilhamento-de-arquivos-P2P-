import { useState, useEffect, useCallback } from "react";

const API_BASE = "http://localhost:8000/api";
const REFRESH_INTERVAL = 5000;

const fmt = {
  bytes: (b) => {
    if (!b) return "—";
    const units = ["B", "KB", "MB", "GB"];
    let i = 0, v = b;
    while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
    return `${v.toFixed(1)} ${units[i]}`;
  },
  ago: (s) => {
    if (s == null) return "—";
    if (s < 60) return `${Math.round(s)}s atrás`;
    return `${Math.round(s / 60)}m atrás`;
  },
};
 
function Badge({ type, children }) {
  const styles = {
    seed:    { background: "#00ff9580", color: "#00ff95", border: "1px solid #00ff9560" },
    leech:   { background: "#ff6b3580", color: "#ff9060", border: "1px solid #ff6b3560" },
    online:  { background: "#3b82f640", color: "#60a5fa", border: "1px solid #3b82f660" },
    neutral: { background: "#ffffff18", color: "#94a3b8",  border: "1px solid #ffffff20" },
  };
  return (
    <span style={{
      ...styles[type] || styles.neutral,
      padding: "2px 8px", borderRadius: 4, fontSize: 11,
      fontFamily: "monospace", fontWeight: 600, letterSpacing: "0.05em",
    }}>
      {children}
    </span>
  );
}
 
function StatCard({ label, value, sub }) {
  return (
    <div style={{
      background: "#0f172a", border: "1px solid #1e293b",
      borderRadius: 8, padding: "18px 24px", minWidth: 140,
    }}>
      <div style={{ color: "#475569", fontSize: 11, fontFamily: "monospace",
        letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ color: "#f1f5f9", fontSize: 28, fontWeight: 700, lineHeight: 1 }}>
        {value}
      </div>
      {sub && <div style={{ color: "#475569", fontSize: 12, marginTop: 4 }}>{sub}</div>}
    </div>
  );
}
 
function ChunkBar({ chunks, total }) {
  if (!total) return null;
  const present = new Set(chunks.map(Number));
  return (
    <div style={{ display: "flex", gap: 1, flexWrap: "wrap", marginTop: 4 }}>
      {Array.from({ length: Math.min(total, 60) }, (_, i) => (
        <div key={i} title={`chunk ${i}`} style={{
          width: 8, height: 8, borderRadius: 2,
          background: present.has(i) ? "#00ff95" : "#1e293b",
        }} />
      ))}
      {total > 60 && <span style={{ color: "#475569", fontSize: 10, alignSelf: "center" }}>+{total - 60}</span>}
    </div>
  );
}
 
function PeersTable({ peers }) {
  if (!peers.length) return <Empty msg="Nenhum peer conectado." />;
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
      <thead>
        <tr style={{ color: "#475569", fontFamily: "monospace", fontSize: 11 }}>
          {["Peer ID", "Host", "Porta", "Último contato"].map(h => (
            <th key={h} style={{ textAlign: "left", padding: "6px 12px",
              borderBottom: "1px solid #1e293b", fontWeight: 500 }}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {peers.map((p) => (
          <tr key={p.peer_id} style={{ borderBottom: "1px solid #0f172a" }}>
            <td style={{ padding: "10px 12px", fontFamily: "monospace", color: "#60a5fa" }}>
              {p.peer_id.slice(0, 16)}…
            </td>
            <td style={{ padding: "10px 12px", color: "#94a3b8" }}>{p.host}</td>
            <td style={{ padding: "10px 12px", color: "#94a3b8" }}>{p.port}</td>
            <td style={{ padding: "10px 12px", color: "#475569" }}>
              {fmt.ago(p.seconds_since_seen)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
 
function FileRow({ file, onSelect, selected }) {
  const availability = (file.seed_count + file.leecher_count) > 0
    ? Math.round((file.seed_count / (file.seed_count + file.leecher_count)) * 100)
    : 0;
 
  return (
    <div
      onClick={() => onSelect(file.filename)}
      style={{
        background: selected ? "#0f172a" : "transparent",
        border: selected ? "1px solid #3b82f660" : "1px solid transparent",
        borderRadius: 8, padding: "14px 20px", cursor: "pointer",
        transition: "all 0.15s", marginBottom: 4,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontFamily: "monospace", color: "#e2e8f0", fontWeight: 600 }}>
          {file.filename}
        </span>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Badge type="seed">⬆ {file.seed_count} seed{file.seed_count !== 1 ? "s" : ""}</Badge>
          <Badge type="leech">⬇ {file.leecher_count} leech{file.leecher_count !== 1 ? "ers" : "er"}</Badge>
        </div>
      </div>
      <div style={{ display: "flex", gap: 24, marginTop: 8, color: "#475569", fontSize: 12 }}>
        <span>{fmt.bytes(file.file_size)}</span>
        <span>{file.total_chunks} chunks</span>
        <span>{availability}% na rede</span>
      </div>
    </div>
  );
}
 
function FileDetail({ filename }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
 
  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE}/files/${encodeURIComponent(filename)}`)
      .then(r => r.json())
      .then(d => { setData(d.file); setLoading(false); })
      .catch(() => setLoading(false));
  }, [filename]);
 
  if (loading) return <div style={{ color: "#475569", padding: 20 }}>Carregando…</div>;
  if (!data) return <Empty msg="Arquivo não encontrado." />;
 
  const allPeers = [...(data.seeders || []), ...(data.leechers || [])];
 
  return (
    <div style={{ padding: "0 4px" }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 24 }}>
        {[
          ["Tamanho", fmt.bytes(data.file_size)],
          ["Chunks", `${data.total_chunks} × ${fmt.bytes(data.chunk_size)}`],
          ["Seeders", data.seed_count],
          ["Leechers", data.leecher_count],
        ].map(([l, v]) => (
          <div key={l} style={{ background: "#0f172a", borderRadius: 6, padding: "10px 14px" }}>
            <div style={{ color: "#475569", fontSize: 11, fontFamily: "monospace" }}>{l}</div>
            <div style={{ color: "#f1f5f9", fontWeight: 600, marginTop: 2 }}>{v}</div>
          </div>
        ))}
      </div>
 
      <div style={{ color: "#475569", fontSize: 11, fontFamily: "monospace",
        marginBottom: 8, letterSpacing: "0.08em" }}>HASH DO ARQUIVO</div>
      <div style={{ fontFamily: "monospace", fontSize: 11, color: "#60a5fa",
        background: "#0f172a", padding: "8px 12px", borderRadius: 6,
        wordBreak: "break-all", marginBottom: 20 }}>
        {data.file_hash}
      </div>
 
      <div style={{ color: "#475569", fontSize: 11, fontFamily: "monospace",
        marginBottom: 12, letterSpacing: "0.08em" }}>PEERS ({allPeers.length})</div>
      {allPeers.map(p => (
        <div key={p.peer_id} style={{
          background: "#0f172a", borderRadius: 6, padding: "12px 14px", marginBottom: 8,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <span style={{ fontFamily: "monospace", color: "#60a5fa", fontSize: 12 }}>
              {p.peer_id.slice(0, 16)}…
            </span>
            <Badge type={p.chunk_count === data.total_chunks ? "seed" : "leech"}>
              {p.chunk_count === data.total_chunks ? "seed" : "leech"}
            </Badge>
          </div>
          <div style={{ color: "#475569", fontSize: 12, marginBottom: 4 }}>
            {p.host}:{p.port} — {p.chunk_count}/{data.total_chunks} chunks
          </div>
          <ChunkBar chunks={p.chunks || []} total={data.total_chunks} />
        </div>
      ))}
    </div>
  );
}
 
function Empty({ msg }) {
  return (
    <div style={{ color: "#334155", textAlign: "center", padding: "40px 0",
      fontFamily: "monospace", fontSize: 13 }}>
      {msg}
    </div>
  );
}
 
function Dot({ ok }) {
  return (
    <span style={{
      display: "inline-block", width: 8, height: 8, borderRadius: "50%",
      background: ok ? "#00ff95" : "#ef4444",
      boxShadow: ok ? "0 0 6px #00ff95" : "none",
      marginRight: 8,
    }} />
  );
}
 
export default function App() {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [tab, setTab] = useState("files"); // "files" | "peers"
  const [lastUpdate, setLastUpdate] = useState(null);
 
  const fetchStatus = useCallback(() => {
    fetch(`${API_BASE}/status`)
      .then(r => r.json())
      .then(d => {
        setStatus(d);
        setError(false);
        setLastUpdate(new Date());
      })
      .catch(() => setError(true));
  }, []);
 
  useEffect(() => {
    fetchStatus();
    const t = setInterval(fetchStatus, REFRESH_INTERVAL);
    return () => clearInterval(t);
  }, [fetchStatus]);
 
  const files = status?.files || [];
  const peers = status?.peers || [];
  const totalSize = files.reduce((a, f) => a + (f.file_size || 0), 0);
 
  const tabStyle = (active) => ({
    padding: "6px 16px", borderRadius: 6, cursor: "pointer", fontSize: 13,
    fontFamily: "monospace", border: "none",
    background: active ? "#1e40af" : "transparent",
    color: active ? "#bfdbfe" : "#475569",
    transition: "all 0.15s",
  });
 
  return (
    <div style={{
      minHeight: "100vh", background: "#020817", color: "#e2e8f0",
      fontFamily: "'Inter', system-ui, sans-serif", padding: "0 0 60px",
    }}>
      {/* Header */}
      <div style={{
        borderBottom: "1px solid #0f172a", padding: "16px 32px",
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 18, fontWeight: 700, letterSpacing: "-0.02em", color: "#f8fafc" }}>
            ▶ tracker
          </span>
          <span style={{ color: "#334155", fontSize: 13 }}>P2P Network Dashboard</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16, fontSize: 12, color: "#475569" }}>
          <span><Dot ok={!error} />{error ? "Offline" : "Online"}</span>
          {lastUpdate && (
            <span style={{ fontFamily: "monospace" }}>
              atualizado {lastUpdate.toLocaleTimeString("pt-BR")}
            </span>
          )}
          <button onClick={fetchStatus} style={{
            background: "#0f172a", border: "1px solid #1e293b", color: "#94a3b8",
            borderRadius: 6, padding: "4px 12px", cursor: "pointer", fontSize: 12,
          }}>↻ Atualizar</button>
        </div>
      </div>
 
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 24px" }}>
        {/* Stats */}
        <div style={{ display: "flex", gap: 12, marginBottom: 32, flexWrap: "wrap" }}>
          <StatCard label="Arquivos" value={files.length} />
          <StatCard label="Peers ativos" value={peers.length} />
          <StatCard label="Total na rede" value={fmt.bytes(totalSize)} />
          <StatCard label="Seeders" value={files.reduce((a, f) => a + f.seed_count, 0)} />
        </div>
 
        {/* Main layout */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 380px", gap: 20, alignItems: "start" }}>
          {/* Left panel */}
          <div style={{
            background: "#060d1b", border: "1px solid #0f172a",
            borderRadius: 12, overflow: "hidden",
          }}>
            <div style={{
              padding: "12px 20px", borderBottom: "1px solid #0f172a",
              display: "flex", gap: 4,
            }}>
              <button style={tabStyle(tab === "files")} onClick={() => setTab("files")}>
                Arquivos ({files.length})
              </button>
              <button style={tabStyle(tab === "peers")} onClick={() => setTab("peers")}>
                Peers ({peers.length})
              </button>
            </div>
 
            <div style={{ padding: "16px 20px", minHeight: 300 }}>
              {tab === "files" && (
                files.length
                  ? files.map(f => (
                      <FileRow
                        key={f.filename}
                        file={f}
                        selected={selectedFile === f.filename}
                        onSelect={setSelectedFile}
                      />
                    ))
                  : <Empty msg="Nenhum arquivo indexado." />
              )}
              {tab === "peers" && <PeersTable peers={peers} />}
            </div>
          </div>
 
          {/* Right panel – file detail */}
          <div style={{
            background: "#060d1b", border: "1px solid #0f172a",
            borderRadius: 12, overflow: "hidden",
          }}>
            <div style={{
              padding: "12px 20px", borderBottom: "1px solid #0f172a",
              fontFamily: "monospace", fontSize: 12, color: "#475569",
            }}>
              {selectedFile ? `→ ${selectedFile}` : "Selecione um arquivo"}
            </div>
            <div style={{ padding: "16px 20px", minHeight: 300 }}>
              {selectedFile
                ? <FileDetail filename={selectedFile} />
                : <Empty msg="Clique em um arquivo para ver os detalhes do swarm." />}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
