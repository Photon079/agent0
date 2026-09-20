import React, { useEffect, useRef, useState, useCallback } from "react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface GraphNode {
  id: string;
  label: string;
  type: "candidate" | "skill" | "project";
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  color: string;
  glowColor: string;
}

interface GraphEdge {
  source: string;
  target: string;
}

interface JobMatch {
  job: string;
  company: string;
  overlap: number;
}

interface EvidenceItem {
  skill: string;
  project_evidence: { name: string; commits: number; url?: string }[];
  experience_evidence: { role: string; company: string }[];
}

interface KnowledgeGraphPageProps {
  candidateId: number;
  candidateName: string;
  username: string;
  onGoBack: () => void;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const API = "http://localhost:8000";

function truncateLabel(label: string, max = 18): string {
  return label.length > max ? label.slice(0, max - 1) + "…" : label;
}

// ─── Force-directed Graph Canvas ──────────────────────────────────────────────

const REPULSION = 3200;
const ATTRACTION = 0.025;
const DAMPING = 0.82;
const CENTER_PULL = 0.008;

function buildGraph(
  candidateName: string,
  evidence: EvidenceItem[]
): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];
  const seen = new Set<string>();

  const cx = 0.5;
  const cy = 0.5;

  // Candidate root node
  const rootId = "cand";
  nodes.push({
    id: rootId,
    label: candidateName.split(" ")[0] || candidateName,
    type: "candidate",
    x: cx,
    y: cy,
    vx: 0,
    vy: 0,
    radius: 18,
    color: "#ffffff",
    glowColor: "rgba(255,255,255,0.35)",
  });
  seen.add(rootId);

  // Top skills we'll accent in yellow-green (first 6)
  const accentSkills = evidence.slice(0, 6).map((e) => e.skill);

  evidence.forEach((ev, si) => {
    const skillId = `skill_${si}`;
    const isAccent = accentSkills.includes(ev.skill);
    const angle = (si / evidence.length) * Math.PI * 2;
    const r = 0.22 + Math.random() * 0.08;

    if (!seen.has(skillId)) {
      nodes.push({
        id: skillId,
        label: truncateLabel(ev.skill),
        type: "skill",
        x: cx + Math.cos(angle) * r,
        y: cy + Math.sin(angle) * r,
        vx: 0,
        vy: 0,
        radius: isAccent ? 10 : 7,
        color: isAccent ? "#c8f04a" : "rgba(255,255,255,0.85)",
        glowColor: isAccent
          ? "rgba(200,240,74,0.45)"
          : "rgba(255,255,255,0.15)",
      });
      seen.add(skillId);
    }
    edges.push({ source: rootId, target: skillId });

    // Project nodes
    ev.project_evidence.slice(0, 2).forEach((proj, pi) => {
      const projId = `proj_${si}_${pi}`;
      const pAngle = angle + (pi - 0.5) * 0.5;
      const pr = r + 0.12 + Math.random() * 0.06;
      if (!seen.has(projId)) {
        nodes.push({
          id: projId,
          label: truncateLabel(proj.name, 14),
          type: "project",
          x: cx + Math.cos(pAngle) * pr,
          y: cy + Math.sin(pAngle) * pr,
          vx: 0,
          vy: 0,
          radius: 5,
          color: "rgba(255,255,255,0.45)",
          glowColor: "rgba(255,255,255,0.06)",
        });
        seen.add(projId);
      }
      edges.push({ source: skillId, target: projId });
    });
  });

  return { nodes, edges };
}

interface GraphCanvasProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

const GraphCanvas: React.FC<GraphCanvasProps> = ({ nodes, edges }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const nodesRef = useRef<GraphNode[]>(nodes);

  // Sync nodes ref when nodes change
  useEffect(() => {
    nodesRef.current = nodes.map((n) => ({ ...n }));
  }, [nodes]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const W = canvas.width;
    const H = canvas.height;
    const ns = nodesRef.current;

    // ── Physics ──────────────────────────────────────────────────────────────
    const nodeMap = new Map<string, GraphNode>();
    ns.forEach((n) => nodeMap.set(n.id, n));

    // Repulsion
    for (let i = 0; i < ns.length; i++) {
      for (let j = i + 1; j < ns.length; j++) {
        const a = ns[i];
        const b = ns[j];
        const dx = (a.x - b.x) * W;
        const dy = (a.y - b.y) * H;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = REPULSION / (dist * dist);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        a.vx += fx / W;
        a.vy += fy / H;
        b.vx -= fx / W;
        b.vy -= fy / H;
      }
    }

    // Attraction along edges
    edges.forEach((e) => {
      const a = nodeMap.get(e.source);
      const b = nodeMap.get(e.target);
      if (!a || !b) return;
      const dx = (b.x - a.x) * W;
      const dy = (b.y - a.y) * H;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = dist * ATTRACTION;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      a.vx += fx / W;
      a.vy += fy / H;
      b.vx -= fx / W;
      b.vy -= fy / H;
    });

    // Center pull (candidate root stays near center)
    ns.forEach((n) => {
      n.vx += (0.5 - n.x) * CENTER_PULL;
      n.vy += (0.5 - n.y) * CENTER_PULL;
      n.vx *= DAMPING;
      n.vy *= DAMPING;
      n.x = Math.max(0.04, Math.min(0.96, n.x + n.vx));
      n.y = Math.max(0.04, Math.min(0.96, n.y + n.vy));
    });

    // ── Render ───────────────────────────────────────────────────────────────
    ctx.clearRect(0, 0, W, H);

    // Edges
    edges.forEach((e) => {
      const a = nodeMap.get(e.source);
      const b = nodeMap.get(e.target);
      if (!a || !b) return;
      ctx.beginPath();
      ctx.moveTo(a.x * W, a.y * H);
      ctx.lineTo(b.x * W, b.y * H);
      ctx.strokeStyle = "rgba(255,255,255,0.10)";
      ctx.lineWidth = 0.8;
      ctx.stroke();
    });

    // Nodes
    ns.forEach((n) => {
      const px = n.x * W;
      const py = n.y * H;

      // Glow halo
      if (n.type !== "project") {
        const grad = ctx.createRadialGradient(px, py, 0, px, py, n.radius * 2.5);
        grad.addColorStop(0, n.glowColor);
        grad.addColorStop(1, "transparent");
        ctx.beginPath();
        ctx.arc(px, py, n.radius * 2.5, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();
      }

      // Circle
      ctx.beginPath();
      ctx.arc(px, py, n.radius, 0, Math.PI * 2);
      ctx.fillStyle = n.color;
      ctx.fill();

      // Label
      if (n.type !== "project") {
        ctx.font = `${n.type === "candidate" ? "bold " : ""}9px monospace`;
        ctx.fillStyle =
          n.type === "candidate" ? "#ffffff" : "rgba(255,255,255,0.75)";
        ctx.textAlign = "center";
        ctx.fillText(n.label, px, py + n.radius + 11);
      }
    });

    animRef.current = requestAnimationFrame(draw);
  }, [edges]);

  useEffect(() => {
    animRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animRef.current);
  }, [draw]);

  // Resize observer
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ro = new ResizeObserver(() => {
      canvas.width = canvas.offsetWidth * window.devicePixelRatio;
      canvas.height = canvas.offsetHeight * window.devicePixelRatio;
      const ctx = canvas.getContext("2d");
      if (ctx) ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
      // Re-apply css size
      canvas.style.width = canvas.offsetWidth + "px";
      canvas.style.height = canvas.offsetHeight + "px";
    });
    ro.observe(canvas);
    // Initial size
    canvas.width = canvas.offsetWidth * window.devicePixelRatio;
    canvas.height = canvas.offsetHeight * window.devicePixelRatio;
    const ctx = canvas.getContext("2d");
    if (ctx) ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    return () => ro.disconnect();
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="w-full h-full"
      style={{ display: "block" }}
    />
  );
};

// ─── Skill Chip ───────────────────────────────────────────────────────────────

const SkillChip: React.FC<{ label: string; index: number }> = ({
  label,
  index,
}) => {
  const isAccent = index < 6;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "4px 12px",
        borderRadius: "9999px",
        fontSize: "11px",
        fontWeight: 500,
        letterSpacing: "0.03em",
        background: isAccent
          ? "rgba(200,240,74,0.12)"
          : "rgba(255,255,255,0.07)",
        border: isAccent
          ? "1px solid rgba(200,240,74,0.35)"
          : "1px solid rgba(255,255,255,0.12)",
        color: isAccent ? "#c8f04a" : "rgba(255,255,255,0.75)",
        whiteSpace: "nowrap",
        transition: "background 0.2s, border-color 0.2s",
      }}
    >
      {label}
    </span>
  );
};

// ─── Job Card ─────────────────────────────────────────────────────────────────

const JobCard: React.FC<JobMatch & { rank: number }> = ({
  job,
  company,
  overlap,
  rank,
}) => (
  <div
    style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: "12px",
      padding: "12px 16px",
      borderRadius: "12px",
      background: "rgba(255,255,255,0.05)",
      border: "1px solid rgba(255,255,255,0.09)",
      transition: "background 0.2s, border-color 0.2s",
      cursor: "pointer",
    }}
    onMouseEnter={(e) => {
      (e.currentTarget as HTMLDivElement).style.background =
        "rgba(255,255,255,0.09)";
      (e.currentTarget as HTMLDivElement).style.borderColor =
        "rgba(255,255,255,0.16)";
    }}
    onMouseLeave={(e) => {
      (e.currentTarget as HTMLDivElement).style.background =
        "rgba(255,255,255,0.05)";
      (e.currentTarget as HTMLDivElement).style.borderColor =
        "rgba(255,255,255,0.09)";
    }}
  >
    <div style={{ display: "flex", flexDirection: "column", gap: "2px", minWidth: 0 }}>
      <span
        style={{
          fontSize: "13px",
          fontWeight: 600,
          color: "rgba(255,255,255,0.92)",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {rank}. {job}
      </span>
      <span
        style={{
          fontSize: "11px",
          color: "rgba(255,255,255,0.45)",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {company || "Unknown company"}
      </span>
    </div>
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "4px",
        flexShrink: 0,
        padding: "3px 10px",
        borderRadius: "9999px",
        background: "rgba(200,240,74,0.12)",
        border: "1px solid rgba(200,240,74,0.3)",
      }}
    >
      <span
        style={{ fontSize: "12px", fontWeight: 700, color: "#c8f04a" }}
      >
        {overlap}
      </span>
      <span
        style={{ fontSize: "10px", color: "rgba(200,240,74,0.7)" }}
      >
        skills
      </span>
    </div>
  </div>
);

// ─── Glass Panel ──────────────────────────────────────────────────────────────

const glassPanel: React.CSSProperties = {
  background: "rgba(0,0,0,0.48)",
  backdropFilter: "blur(24px) saturate(140%)",
  WebkitBackdropFilter: "blur(24px) saturate(140%)",
  border: "1px solid rgba(255,255,255,0.09)",
  borderRadius: "20px",
  boxShadow:
    "0 8px 40px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.06)",
  overflow: "hidden",
};

const sectionDivider: React.CSSProperties = {
  height: "1px",
  background:
    "linear-gradient(90deg, transparent, rgba(255,255,255,0.10) 30%, rgba(255,255,255,0.10) 70%, transparent)",
  margin: "16px 0",
  flexShrink: 0,
};

// ─── Main Page ────────────────────────────────────────────────────────────────

export const KnowledgeGraphPage: React.FC<KnowledgeGraphPageProps> = ({
  candidateId,
  candidateName,
  username,
  onGoBack,
}) => {
  const [skills, setSkills] = useState<string[]>([]);
  const [jobMatches, setJobMatches] = useState<JobMatch[]>([]);
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([]);
  const [loadingGraph, setLoadingGraph] = useState(true);
  const [loadingJobs, setLoadingJobs] = useState(true);

  const avatarUrl = `https://avatars.githubusercontent.com/${username}`;

  // Fetch evidence / skills for graph
  useEffect(() => {
    if (!candidateId) return;
    setLoadingGraph(true);
    fetch(`${API}/evidence/candidate/${candidateId}`)
      .then((r) => r.json())
      .then((data) => {
        const ev: EvidenceItem[] = data.evidence || [];
        setSkills(ev.map((e) => e.skill));
        const { nodes, edges } = buildGraph(candidateName, ev);
        setGraphNodes(nodes);
        setGraphEdges(edges);
      })
      .catch(() => {
        // Graceful degradation: show graph with just the candidate node
        const { nodes, edges } = buildGraph(candidateName, []);
        setGraphNodes(nodes);
        setGraphEdges(edges);
      })
      .finally(() => setLoadingGraph(false));
  }, [candidateId, candidateName]);

  // Fetch job matches
  useEffect(() => {
    if (!candidateId) return;
    setLoadingJobs(true);
    fetch(`${API}/match/${candidateId}?limit=8`)
      .then((r) => r.json())
      .then((data: JobMatch[]) => setJobMatches(data))
      .catch(() => setJobMatches([]))
      .finally(() => setLoadingJobs(false));
  }, [candidateId]);

  return (
    <div
      style={{
        position: "relative",
        width: "100vw",
        height: "100vh",
        background: "#000",
        overflow: "hidden",
        fontFamily: "'Geist Variable', sans-serif",
      }}
    >
      {/* ── Background video ──────────────────────────────────────────────── */}
      <video
        autoPlay
        loop
        muted
        playsInline
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          objectFit: "cover",
          opacity: 0.55,
          pointerEvents: "none",
        }}
        src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260405_171521_25968ba2-b594-4b32-aab7-f6b69398a6fa.mp4"
      />

      {/* ── Gradient vignette ─────────────────────────────────────────────── */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(ellipse 80% 80% at 50% 50%, transparent 40%, rgba(0,0,0,0.65) 100%)",
          pointerEvents: "none",
        }}
      />

      {/* ── Go Back button ────────────────────────────────────────────────── */}
      <button
        onClick={onGoBack}
        style={{
          position: "absolute",
          top: "20px",
          right: "24px",
          zIndex: 50,
          padding: "7px 18px",
          borderRadius: "9999px",
          background: "rgba(255,255,255,0.07)",
          border: "1px solid rgba(255,255,255,0.14)",
          color: "rgba(255,255,255,0.65)",
          fontSize: "12px",
          fontWeight: 500,
          cursor: "pointer",
          backdropFilter: "blur(12px)",
          transition: "background 0.2s, color 0.2s",
          fontFamily: "inherit",
          letterSpacing: "0.02em",
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.background =
            "rgba(255,255,255,0.13)";
          (e.currentTarget as HTMLButtonElement).style.color =
            "rgba(255,255,255,0.9)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.background =
            "rgba(255,255,255,0.07)";
          (e.currentTarget as HTMLButtonElement).style.color =
            "rgba(255,255,255,0.65)";
        }}
      >
        ← Go Back
      </button>

      {/* ── Main layout ───────────────────────────────────────────────────── */}
      <div
        style={{
          position: "relative",
          zIndex: 10,
          display: "flex",
          gap: "16px",
          padding: "24px",
          height: "100%",
          boxSizing: "border-box",
          paddingTop: "24px",
        }}
      >
        {/* ═══════════════════════════════════════════════════════════════════
            LEFT PANEL — Knowledge Graph
        ════════════════════════════════════════════════════════════════════ */}
        <div
          style={{
            ...glassPanel,
            width: "50%",
            minWidth: 0,
            display: "flex",
            flexDirection: "column",
            padding: "20px",
            gap: 0,
          }}
        >
          {/* Profile header */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "14px",
              flexShrink: 0,
            }}
          >
            <img
              src={avatarUrl}
              alt={candidateName}
              width={46}
              height={46}
              style={{
                borderRadius: "50%",
                border: "2px solid rgba(255,255,255,0.18)",
                objectFit: "cover",
                flexShrink: 0,
                background: "rgba(255,255,255,0.05)",
              }}
              onError={(e) => {
                (e.currentTarget as HTMLImageElement).style.display = "none";
              }}
            />
            <div style={{ display: "flex", flexDirection: "column", gap: "2px", minWidth: 0 }}>
              <span
                style={{
                  fontSize: "18px",
                  fontWeight: 700,
                  color: "#ffffff",
                  letterSpacing: "-0.02em",
                  lineHeight: 1.2,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {candidateName}
              </span>
              <span
                style={{
                  fontSize: "12px",
                  color: "rgba(255,255,255,0.42)",
                  letterSpacing: "0.01em",
                }}
              >
                @{username}
              </span>
            </div>

            {/* Skill count badge */}
            <div style={{ marginLeft: "auto", flexShrink: 0 }}>
              <span
                style={{
                  padding: "4px 12px",
                  borderRadius: "9999px",
                  background: "rgba(200,240,74,0.10)",
                  border: "1px solid rgba(200,240,74,0.28)",
                  color: "#c8f04a",
                  fontSize: "11px",
                  fontWeight: 600,
                  letterSpacing: "0.03em",
                }}
              >
                {skills.length} skills
              </span>
            </div>
          </div>

          {/* Divider */}
          <div style={sectionDivider} />

          {/* Graph label */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexShrink: 0,
              marginBottom: "10px",
            }}
          >
            <span
              style={{
                fontSize: "11px",
                fontWeight: 600,
                color: "rgba(255,255,255,0.35)",
                letterSpacing: "0.08em",
                textTransform: "uppercase",
              }}
            >
              Knowledge Graph
            </span>
            {loadingGraph && (
              <span
                style={{
                  fontSize: "10px",
                  color: "rgba(200,240,74,0.6)",
                  letterSpacing: "0.04em",
                }}
              >
                building…
              </span>
            )}
          </div>

          {/* Canvas */}
          <div
            style={{
              flex: 1,
              borderRadius: "12px",
              overflow: "hidden",
              background: "rgba(0,0,0,0.55)",
              border: "1px solid rgba(255,255,255,0.06)",
              minHeight: 0,
            }}
          >
            {!loadingGraph && graphNodes.length > 0 && (
              <GraphCanvas nodes={graphNodes} edges={graphEdges} />
            )}
            {loadingGraph && (
              <div
                style={{
                  width: "100%",
                  height: "100%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <span
                  style={{
                    fontSize: "12px",
                    color: "rgba(255,255,255,0.25)",
                    letterSpacing: "0.04em",
                  }}
                >
                  Mapping your graph…
                </span>
              </div>
            )}
          </div>
        </div>

        {/* ═══════════════════════════════════════════════════════════════════
            RIGHT PANEL — Skills + Job Matches
        ════════════════════════════════════════════════════════════════════ */}
        <div
          style={{
            ...glassPanel,
            flex: 1,
            minWidth: 0,
            display: "flex",
            flexDirection: "column",
            padding: "20px",
            gap: 0,
            overflowY: "auto",
          }}
        >
          {/* Skills section */}
          <span
            style={{
              fontSize: "11px",
              fontWeight: 600,
              color: "rgba(255,255,255,0.35)",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              flexShrink: 0,
              marginBottom: "12px",
            }}
          >
            Verified Skills
          </span>

          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "6px",
              flexShrink: 0,
            }}
          >
            {skills.length === 0 && !loadingGraph && (
              <span style={{ fontSize: "12px", color: "rgba(255,255,255,0.3)" }}>
                No skills found.
              </span>
            )}
            {skills.map((sk, i) => (
              <SkillChip key={sk} label={sk} index={i} />
            ))}
          </div>

          {/* Divider */}
          <div style={sectionDivider} />

          {/* Job Matches */}
          <span
            style={{
              fontSize: "11px",
              fontWeight: 600,
              color: "rgba(255,255,255,0.35)",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              flexShrink: 0,
              marginBottom: "12px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <span>Job Matches</span>
            {loadingJobs && (
              <span
                style={{ fontSize: "10px", color: "rgba(200,240,74,0.6)", textTransform: "none" }}
              >
                loading…
              </span>
            )}
          </span>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "8px",
              flex: 1,
            }}
          >
            {jobMatches.length === 0 && !loadingJobs && (
              <span style={{ fontSize: "12px", color: "rgba(255,255,255,0.3)" }}>
                No job matches yet — try scraping live jobs.
              </span>
            )}
            {jobMatches.map((jm, i) => (
              <JobCard key={`${jm.job}_${i}`} {...jm} rank={i + 1} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default KnowledgeGraphPage;
