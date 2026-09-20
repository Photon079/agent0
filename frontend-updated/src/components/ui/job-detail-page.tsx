import { useEffect, useState } from "react"
import { EvervaultCard, Icon } from "@/components/ui/evervault-card"

type Job = {
  id: number
  title: string
  company?: string
  description?: string
  url?: string
  skills: string[]
}
type JobSummary = {
  job_id?: number
  job: string
  company?: string
  url?: string
  overlap: number
}
type ProjectSuggestion = { title?: string; description?: string }
type ResumeBullet = { bullet: string; skill: string; evidence_ids?: string[] }

type Props = {
  candidateId: number
  jobId: number
  summary?: JobSummary
  onBack: () => void
}

const API = "http://localhost:8000"
const mono = "'Geist Mono', ui-monospace, monospace"
const colors = {
  text: "#e8f2ee",
  muted: "#7f9189",
  faint: "#43544d",
  neon: "#00ff9c",
  green: "#00d982",
  panel: "rgba(2,6,5,.82)",
}
const panel: React.CSSProperties = {
  border: "1px solid rgba(196,255,237,.18)",
//   background: "linear-gradient(135deg, rgba(7,22,18,.62), rgba(2,8,7,.42))",
  backdropFilter: "blur(20px) saturate(140%)",
  WebkitBackdropFilter: "blur(20px) saturate(140%)",
  borderRadius: 23,
  boxShadow: "0 18px 55px rgba(0,0,0,.32), inset 0 1px 0 rgba(255,255,255,.1)",
}
const button: React.CSSProperties = {
  border: "1px solid rgba(196,255,237,.22)",
  borderRadius: 8,
  background: "rgba(7,34,27,.42)",
  backdropFilter: "blur(14px)",
  WebkitBackdropFilter: "blur(14px)",
  color: colors.neon,
  cursor: "pointer",
  font: `10px ${mono}`,
  letterSpacing: ".06em",
  textTransform: "uppercase",
}

export function JobDetailPage({ candidateId, jobId, summary, onBack }: Props) {
  const [job, setJob] = useState<Job | null>(null)
  const [loading, setLoading] = useState(true)
  const [project, setProject] = useState<ProjectSuggestion | null>(null)
  const [projectLoading, setProjectLoading] = useState(false)
  const [bullets, setBullets] = useState<ResumeBullet[] | null>(null)
  const [bulletsLoading, setBulletsLoading] = useState(false)
  const [showSkills, setShowSkills] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    fetch(`${API}/jobs`)
      .then((response) => response.json())
      .then((jobs: Job[]) =>
        setJob(jobs.find((item) => item.id === jobId) || null)
      )
      .catch(() => setError("Job details could not be loaded."))
      .finally(() => setLoading(false))
  }, [jobId])

  const generateProject = async () => {
    setProjectLoading(true)
    setProject(null)
    setError("")
    try {
      const response = await fetch(`${API}/gap/${candidateId}/${jobId}/project`)
      const data = await response.json()
      if (!response.ok || data.error)
        throw new Error(data.error || "Project generation failed.")
      setProject(data)
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Project generation failed."
      )
    } finally {
      setProjectLoading(false)
    }
  }

  const generateResume = async () => {
    setBulletsLoading(true)
    setBullets(null)
    setError("")
    try {
      const response = await fetch(`${API}/generate/bullets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          candidate_id: String(candidateId),
          job_id: String(jobId),
        }),
      })
      const data = await response.json()
      if (!response.ok || data.error)
        throw new Error(data.error || "Resume generation failed.")
      setBullets(data.bullets || [])
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Resume generation failed."
      )
    } finally {
      setBulletsLoading(false)
    }
  }

  const currentJob = job || {
    id: jobId,
    title: summary?.job || "Job posting",
    company: summary?.company,
    description: "Loading the full job description from the graph.",
    url: summary?.url,
    skills: [],
  }
  return (
    <main
      style={{
        minHeight: "100vh",
        background: "#010403",
        position: "relative",
        overflow: "hidden",
        color: colors.text,
        padding: "28px clamp(18px, 5vw, 76px) 80px",
        fontFamily: "'Geist Variable', sans-serif",
      }}
    >
      <video
        autoPlay
        loop
        muted
        playsInline
        src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260808_064556_051587f1-74a1-4336-8c05-4dde3594ed05.mp4"
        style={{
          position: "fixed",
          inset: 0,
          width: "100%",
          height: "100%",
          objectFit: "cover",
          opacity: 0.34,
          pointerEvents: "none",
          zIndex: 0,
        }}
      />
      <div
        style={{
          position: "fixed",
          inset: 0,
          zIndex: 1,
          pointerEvents: "none",
          background: "linear-gradient(180deg, rgba(1,4,3,.66), rgba(1,4,3,.84)), radial-gradient(circle at 50% 12%, rgba(0,255,156,.1), transparent 54%)",
        }}
      />
      <header
        style={{
          position: "relative",
          zIndex: 2,
          maxWidth: 1280,
          margin: "0 auto 42px",
          padding: "12px 16px",
          border: "1px solid rgba(196,255,237,.14)",
          borderRadius: 14,
          background: "rgba(2,8,7,.42)",
          backdropFilter: "blur(20px) saturate(140%)",
          WebkitBackdropFilter: "blur(20px) saturate(140%)",
          boxShadow: "0 14px 42px rgba(0,0,0,.24), inset 0 1px 0 rgba(255,255,255,.08)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 20,
        }}
      >
        <button
          onClick={onBack}
          style={{ ...button, padding: "9px 13px", background: "transparent" }}
        >
          ← Back to knowledge graph
        </button>
        <span
          style={{
            color: colors.faint,
            font: `10px ${mono}`,
            letterSpacing: ".12em",
          }}
        >
          JOB INTELLIGENCE / {jobId}
        </span>
      </header>

      <section
        style={{
          position: "relative",
          zIndex: 2,
          maxWidth: 1280,
          margin: "0 auto",
          display: "grid",
          gridTemplateColumns:
            "repeat(auto-fit, minmax(min(100%, 480px), 1fr))",
          gap: "clamp(26px, 5vw, 72px)",
          alignItems: "stretch",
        }}
      >
        <div
          style={{ minHeight: 560, display: "flex", flexDirection: "column" }}
        >
          <div
            style={{
              ...panel,
              minHeight: 460,
              overflow: "hidden",
              position: "relative",
            }}
          >
            <EvervaultCard className="job-evervault">
              <span
                style={{
                  display: "block",
                  maxWidth: 250,
                  fontSize: "clamp(28px, 4vw, 54px)",
                  lineHeight: 1.04,
                }}
              >
                {currentJob.title}
              </span>
            </EvervaultCard>
          </div>
          <div style={{ marginTop: 18, padding: "0 4px" }}>
            <p
              style={{
                margin: 0,
                color: colors.text,
                fontSize: 13,
                lineHeight: 1.55,
              }}
            >
              {currentJob.description ||
                "No description was provided for this posting."}
            </p>
            <div
              style={{
                marginTop: 12,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 12,
              }}
            >
              <span style={{ color: colors.muted, font: `11px ${mono}` }}>
                {currentJob.company || "Unknown company"}
              </span>
              {currentJob.url && (
                <a
                  href={currentJob.url}
                  target="_blank"
                  rel="noreferrer"
                  style={{ color: colors.neon, font: `10px ${mono}` }}
                >
                  VIEW POSTING ↗
                </a>
              )}
            </div>
            <button
              onClick={() => setShowSkills((value) => !value)}
              style={{ ...button, marginTop: 16, padding: "9px 12px" }}
            >
              <Icon className="mr-2 inline-block h-4 w-4 align-middle" />
              {showSkills ? "Hide skills" : "Skills"}
            </button>
            {showSkills && (
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 7,
                  marginTop: 12,
                }}
              >
                {(currentJob.skills || []).map((skill) => (
                  <span
                    key={skill}
                    style={{
                      ...panel,
                      padding: "5px 8px",
                      color: colors.neon,
                      font: `10px ${mono}`,
                    }}
                  >
                    {skill}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateRows: "1fr 1fr", gap: 24 }}>
          <article
            style={{
              ...panel,
              minHeight: 250,
              padding: "clamp(24px, 4vw, 48px)",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
            }}
          >
            <div>
              <div
                style={{
                  color: colors.neon,
                  font: `10px ${mono}`,
                  letterSpacing: ".14em",
                  textTransform: "uppercase",
                }}
              >
                Skill gap analysis
              </div>
              <h2
                style={{
                  margin: "18px 0 10px",
                  fontSize: "clamp(28px, 4vw, 48px)",
                  lineHeight: 1.02,
                  fontWeight: 300,
                }}
              >
                Bridge the gap
              </h2>
              <p
                style={{
                  maxWidth: 510,
                  margin: 0,
                  color: colors.muted,
                  fontSize: 14,
                  lineHeight: 1.6,
                }}
              >
                Generate a focused project that targets the missing requirements
                in this job posting.
              </p>
            </div>
            <div style={{ marginTop: 28 }}>
              <button
                onClick={generateProject}
                disabled={projectLoading || loading}
                style={{
                  ...button,
                  padding: "12px 16px",
                  opacity: projectLoading ? 0.6 : 1,
                }}
              >
                {projectLoading
                  ? "Generating project..."
                  : "Generate bridge project"}
              </button>
              {project && (
                <div style={{ ...panel, marginTop: 18, padding: 16 }}>
                  <strong style={{ color: colors.neon, fontSize: 16 }}>
                    {project.title || "Suggested project"}
                  </strong>
                  <p
                    style={{
                      margin: "8px 0 0",
                      color: colors.muted,
                      fontSize: 13,
                      lineHeight: 1.6,
                    }}
                  >
                    {project.description}
                  </p>
                </div>
              )}
            </div>
          </article>
          <article
            style={{
              ...panel,
              minHeight: 250,
              padding: "clamp(24px, 4vw, 48px)",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
            }}
          >
            <div>
              <div
                style={{
                  color: colors.neon,
                  font: `10px ${mono}`,
                  letterSpacing: ".14em",
                  textTransform: "uppercase",
                }}
              >
                Evidence-grounded writing
              </div>
              <h2
                style={{
                  margin: "18px 0 10px",
                  fontSize: "clamp(28px, 4vw, 48px)",
                  lineHeight: 1.02,
                  fontWeight: 300,
                }}
              >
                Resume generation
              </h2>
              <p
                style={{
                  maxWidth: 510,
                  margin: 0,
                  color: colors.muted,
                  fontSize: 14,
                  lineHeight: 1.6,
                }}
              >
                Draft tailored proof-backed bullets using only the skills and
                repository evidence in your graph.
              </p>
            </div>
            <div style={{ marginTop: 28 }}>
              <button
                onClick={generateResume}
                disabled={bulletsLoading || loading}
                style={{
                  ...button,
                  padding: "12px 16px",
                  opacity: bulletsLoading ? 0.6 : 1,
                }}
              >
                {bulletsLoading
                  ? "Writing resume..."
                  : "Generate tailored resume"}
              </button>
              {bullets && (
                <div
                  style={{
                    ...panel,
                    marginTop: 18,
                    padding: 16,
                    display: "grid",
                    gap: 12,
                  }}
                >
                  {bullets.length ? (
                    bullets.map((bullet) => (
                      <div
                        key={`${bullet.skill}-${bullet.bullet}`}
                        style={{
                          color: colors.text,
                          fontSize: 13,
                          lineHeight: 1.55,
                        }}
                      >
                        <span style={{ color: colors.neon }}>•</span>{" "}
                        {bullet.bullet}
                        <small
                          style={{
                            display: "block",
                            marginTop: 4,
                            color: colors.faint,
                            font: `10px ${mono}`,
                          }}
                        >
                          {bullet.skill}
                        </small>
                      </div>
                    ))
                  ) : (
                    <span style={{ color: colors.muted, fontSize: 13 }}>
                      Not enough matching evidence to generate resume bullets.
                    </span>
                  )}
                </div>
              )}
            </div>
          </article>
        </div>
      </section>
      {error && (
        <p
          style={{
            maxWidth: 1280,
            margin: "24px auto 0",
            color: "#ff7181",
            font: `11px ${mono}`,
          }}
        >
          {error}
        </p>
      )}
    </main>
  )
}

export default JobDetailPage
