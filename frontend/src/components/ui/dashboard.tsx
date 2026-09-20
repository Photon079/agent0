import { useEffect, useState } from "react"
import { Icon } from "@/components/ui/evervault-card"

type Candidate = {
  id: number
  name: string
  email: string
}

type Props = {
  onSelectCandidate: (id: number, name: string) => void
  onBack: () => void
}

const mono = "'Geist Mono', ui-monospace, monospace"
const colors = {
  bg: "#010403",
  text: "#e8f2ee",
  muted: "#7f9189",
  faint: "#43544d",
  neon: "#00ff9c",
  panel: "rgba(2,6,5,.82)",
}

export function Dashboard({ onSelectCandidate, onBack }: Props) {
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch("http://localhost:8000/candidates")
      .then((res) => res.json())
      .then((data) => setCandidates(data))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div
      style={{
        minHeight: "100vh",
        background: colors.bg,
        color: colors.text,
        fontFamily: "'Geist Variable', Inter, sans-serif",
      }}
    >
      <header
        style={{
          position: "sticky",
          top: 0,
          zIndex: 10,
          height: 62,
          borderBottom: "1px solid rgba(196,255,237,.14)",
          background: "rgba(2,8,7,.54)",
          backdropFilter: "blur(20px) saturate(140%)",
          WebkitBackdropFilter: "blur(20px) saturate(140%)",
        }}
      >
        <div
          style={{
            maxWidth: 1280,
            height: "100%",
            margin: "auto",
            padding: "0 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <button
            onClick={onBack}
            style={{
              border: 0,
              background: "none",
              color: colors.text,
              cursor: "pointer",
              textAlign: "left",
            }}
          >
            <strong style={{ display: "block", font: `12px ${mono}`, letterSpacing: ".12em" }}>
              ● AGENT0
            </strong>
            <small style={{ color: "rgba(0,255,156,.7)", font: `8px ${mono}`, letterSpacing: ".12em" }}>
              TECHNICAL CONSTELLATION v2.4
            </small>
          </button>
        </div>
      </header>

      <main style={{ maxWidth: 1280, margin: "auto", padding: "64px 24px" }}>
        <h1 style={{ fontSize: 42, fontWeight: 300, marginBottom: 12 }}>Candidate Dashboard</h1>
        <p style={{ color: colors.muted, marginBottom: 48 }}>Select a previously ingested candidate to view their graph.</p>

        {loading ? (
          <p style={{ color: colors.faint, font: `11px ${mono}` }}>Loading candidates...</p>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
              gap: 16,
            }}
          >
            {candidates.map((cand) => (
              <button
                key={cand.id}
                onClick={() => onSelectCandidate(cand.id, cand.name)}
                style={{
                  border: "1px solid rgba(196,255,237,.18)",
                  background: colors.panel,
                  backdropFilter: "blur(20px)",
                  WebkitBackdropFilter: "blur(20px)",
                  borderRadius: 16,
                  padding: 24,
                  textAlign: "left",
                  color: colors.text,
                  cursor: "pointer",
                  position: "relative",
                  overflow: "hidden",
                }}
              >
                <Icon className="absolute h-6 w-6 -top-3 -left-3 text-emerald-500/30" />
                <Icon className="absolute h-6 w-6 -bottom-3 -left-3 text-emerald-500/30" />
                <Icon className="absolute h-6 w-6 -top-3 -right-3 text-emerald-500/30" />
                <Icon className="absolute h-6 w-6 -bottom-3 -right-3 text-emerald-500/30" />

                <div style={{ color: colors.neon, font: `10px ${mono}`, marginBottom: 8, letterSpacing: ".06em" }}>
                  ID: {cand.id}
                </div>
                <div style={{ fontSize: 20, fontWeight: 500, marginBottom: 4 }}>{cand.name}</div>
                <div style={{ color: colors.muted, fontSize: 13 }}>{cand.email || "No email provided"}</div>
              </button>
            ))}
            
            {candidates.length === 0 && (
              <p style={{ color: colors.muted }}>No candidates found in the database.</p>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
