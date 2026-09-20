import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

type Evidence = {
  skill: string;
  project_evidence: { name: string; commits?: number; url?: string; description?: string }[];
  experience_evidence: { role: string; company: string; duration?: string }[];
};

type JobMatch = { job: string; company: string; overlap: number };
type GraphNode = { id: string; name: string; group: string; val: number; url?: string; x: number; y: number; z: number; description: string; repositories: number; commits: number };

type Props = {
  candidateId: number;
  candidateName: string;
  username: string;
  onGoBack: () => void;
};

const API = "http://localhost:8000";
const mono = "'Geist Mono', ui-monospace, monospace";
const colors = { bg: "#010403", panel: "rgba(2,6,5,.78)", text: "#e8f2ee", muted: "#7f9189", faint: "#43544d", neon: "#00ff9c", vibrant: "#00d982", dim: "#087a55" };
const cardStyle: React.CSSProperties = { border: "1px solid rgba(0,255,156,.12)", background: colors.panel, borderRadius: 8 };

function Graph({ evidence, candidateName, reducedMotion }: { evidence: Evidence[]; candidateName: string; reducedMotion: boolean }) {
  const graphData = useMemo(() => {
    const nodes: GraphNode[] = [{ id: "candidate", name: candidateName || "Candidate", group: "root", val: 20, x: 0, y: 0, z: 0, description: "Root candidate identity synthesized from the ingested GitHub profile.", repositories: evidence.reduce((total, item) => total + item.project_evidence.length, 0), commits: evidence.reduce((total, item) => total + item.project_evidence.reduce((sum, project) => sum + (project.commits || 0), 0), 0) }];
    const links: { source: string; target: string }[] = [];
    const domains = new Map<string, GraphNode>();
    evidence.forEach((item, index) => {
      const normalized = item.skill.toLowerCase();
      const group = /python|javascript|typescript|java|go|rust|ruby|php|kotlin|c\+\+/.test(normalized) ? "Languages" : /react|vue|angular|fastapi|django|next|flask|express|spring/.test(normalized) ? "Frameworks" : "Cloud & Tools";
      const domainId = `domain-${group.toLowerCase().replace(/\s/g, "-")}`;
      if (!domains.has(domainId)) {
        const angle = domains.size * Math.PI * 0.8 - 1.6;
        domains.set(domainId, { id: domainId, name: group, group: "domain", val: 13, x: Math.cos(angle) * 120, y: Math.sin(angle) * 110, z: Math.sin(angle * 1.7) * 90, description: `${group} signals found across the ingested repositories.`, repositories: 0, commits: 0 });
        links.push({ source: "candidate", target: domainId });
      }
      const domain = domains.get(domainId);
      if (domain) { domain.repositories += item.project_evidence.length; domain.commits += item.project_evidence.reduce((sum, project) => sum + (project.commits || 0), 0); }
      const skillId = `skill-${index}`;
      const angle = (index / Math.max(evidence.length, 1)) * Math.PI * 2;
      nodes.push({ id: skillId, name: item.skill, group: "skill", val: 11, x: Math.cos(angle) * 210, y: Math.sin(angle) * 150, z: Math.cos(angle * 1.4) * 120, description: `Verified through ${item.project_evidence.length} GitHub project${item.project_evidence.length === 1 ? "" : "s"} and repository telemetry.`, repositories: item.project_evidence.length, commits: item.project_evidence.reduce((sum, project) => sum + (project.commits || 0), 0) });
      links.push({ source: domainId, target: skillId });
      item.project_evidence.slice(0, 3).forEach((project, projectIndex) => {
        const projectId = `project-${index}-${projectIndex}`;
        nodes.push({ id: projectId, name: project.name, group: "project", val: 6, x: Math.cos(angle + projectIndex * .3) * 290, y: Math.sin(angle + projectIndex * .3) * 220, z: Math.sin(angle + projectIndex) * 170, url: project.url, description: project.description || "Repository evidence linked to this verified skill.", repositories: 1, commits: project.commits || 0 });
        links.push({ source: skillId, target: projectId });
      });
    });
    return { nodes: [...nodes, ...domains.values()], links };
  }, [candidateName, evidence]);

  const containerRef = useRef<HTMLDivElement>(null);
  const [hovered, setHovered] = useState<GraphNode | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const hoveredRef = useRef<GraphNode | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x010403, 0.0012);
    const camera = new THREE.PerspectiveCamera(55, 1, 1, 3000);
    camera.position.set(0, 40, 420 / zoom);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x010403, 1);
    container.appendChild(renderer.domElement);
    const graphGroup = new THREE.Group();
    scene.add(graphGroup);
    const nodeObjects: THREE.Mesh[] = [];
    const textureCanvas = document.createElement("canvas");
    textureCanvas.width = 128; textureCanvas.height = 128;
    const textureContext = textureCanvas.getContext("2d");
    if (!textureContext) return;
    const glow = textureContext.createRadialGradient(64, 64, 0, 64, 64, 64);
    glow.addColorStop(0, "rgba(255,255,255,1)"); glow.addColorStop(.14, "rgba(0,255,156,.95)"); glow.addColorStop(.42, "rgba(0,217,130,.4)"); glow.addColorStop(1, "rgba(0,0,0,0)");
    textureContext.fillStyle = glow; textureContext.fillRect(0, 0, 128, 128);
    const glowTexture = new THREE.CanvasTexture(textureCanvas);
    const starfieldPositions = new Float32Array(2400 * 3);
    for (let index = 0; index < 2400; index += 1) { const radius = 300 + Math.random() * 850; const theta = Math.random() * Math.PI * 2; const phi = Math.acos(Math.random() * 2 - 1); starfieldPositions[index * 3] = radius * Math.sin(phi) * Math.cos(theta); starfieldPositions[index * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta); starfieldPositions[index * 3 + 2] = radius * Math.cos(phi); }
    const starGeometry = new THREE.BufferGeometry(); starGeometry.setAttribute("position", new THREE.BufferAttribute(starfieldPositions, 3));
    const stars = new THREE.Points(starGeometry, new THREE.PointsMaterial({ color: 0x087a55, size: 3.5, map: glowTexture, transparent: true, opacity: .58, blending: THREE.AdditiveBlending, depthWrite: false })); scene.add(stars);
    graphData.nodes.forEach((data) => { const color = data.group === "root" ? 0xffffff : data.group === "domain" ? 0x00ff9c : data.group === "skill" ? 0x00d982 : 0x087a55; const size = data.group === "root" ? 14 : data.group === "domain" ? 9 : data.group === "skill" ? 6 : 3.5; const mesh = new THREE.Mesh(new THREE.SphereGeometry(size * .4, 16, 16), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: .95 })); const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture, color, transparent: true, opacity: .86, blending: THREE.AdditiveBlending })); sprite.scale.set(size * 4, size * 4, 1); mesh.add(sprite); mesh.position.set(data.x, data.y, data.z); mesh.userData = { data, sprite }; graphGroup.add(mesh); nodeObjects.push(mesh); });
    const edgeGeometry = new THREE.BufferGeometry(); const edgePositions: number[] = []; graphData.links.forEach((link) => { const source = nodeObjects.find((node) => (node.userData.data as GraphNode).id === link.source); const target = nodeObjects.find((node) => (node.userData.data as GraphNode).id === link.target); if (source && target) edgePositions.push(source.position.x, source.position.y, source.position.z, target.position.x, target.position.y, target.position.z); }); edgeGeometry.setAttribute("position", new THREE.Float32BufferAttribute(edgePositions, 3)); const edges = new THREE.LineSegments(edgeGeometry, new THREE.LineBasicMaterial({ color: 0x087a55, transparent: true, opacity: .3, blending: THREE.AdditiveBlending })); graphGroup.add(edges);
    const raycaster = new THREE.Raycaster(); const pointer = new THREE.Vector2(); let dragging = false; let lastPointer = { x: 0, y: 0 }; let animationFrame = 0;
    const resize = () => { const { width, height } = container.getBoundingClientRect(); camera.aspect = width / Math.max(height, 1); camera.updateProjectionMatrix(); renderer.setSize(width, height); }; resize(); const observer = new ResizeObserver(resize); observer.observe(container);
    const move = (event: PointerEvent) => { const rect = container.getBoundingClientRect(); pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1; pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1; if (dragging) { graphGroup.rotation.y += (event.clientX - lastPointer.x) * .004; graphGroup.rotation.x += (event.clientY - lastPointer.y) * .004; lastPointer = { x: event.clientX, y: event.clientY }; } raycaster.setFromCamera(pointer, camera); const hit = raycaster.intersectObjects(nodeObjects)[0]?.object; const next = hit?.userData.data as GraphNode | undefined; if (next && hoveredRef.current?.id !== next.id) { hoveredRef.current = next; setHovered(next); } else if (!next && hoveredRef.current) { hoveredRef.current = null; setHovered(null); } if (next) setTooltipPosition({ x: event.clientX - rect.left, y: event.clientY - rect.top }); };
    const down = (event: PointerEvent) => { dragging = true; lastPointer = { x: event.clientX, y: event.clientY }; container.setPointerCapture(event.pointerId); }; const up = () => { dragging = false; };
    container.addEventListener("pointermove", move); container.addEventListener("pointerdown", down); container.addEventListener("pointerup", up);
    const animate = () => { if (!reducedMotion && !dragging) { graphGroup.rotation.y += .0012; stars.rotation.y += .0002; } animationFrame = requestAnimationFrame(animate); renderer.render(scene, camera); }; animate();
    return () => { cancelAnimationFrame(animationFrame); observer.disconnect(); container.removeEventListener("pointermove", move); container.removeEventListener("pointerdown", down); container.removeEventListener("pointerup", up); graphData.nodes.forEach(() => undefined); renderer.dispose(); glowTexture.dispose(); starGeometry.dispose(); edgeGeometry.dispose(); container.removeChild(renderer.domElement); };
  }, [graphData, reducedMotion, zoom]);

  const graphUI = (
    <div
      ref={containerRef}
      style={{
        position: "absolute",
        inset: 0,
        cursor: "grab",
      }}
    >
      <div
        style={{
          position: "absolute",
          zIndex: 3,
          ...cardStyle,
          width: 242,
          padding: 14,
          pointerEvents: "none",
          opacity: hovered ? 1 : 0,
          transform: hovered ? "translateY(0)" : "translateY(8px)",
          transition: "opacity 180ms, transform 180ms",
          left: tooltipPosition.x,
          top: tooltipPosition.y - 190,
          marginLeft: -121,
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            borderBottom: "1px solid rgba(0,255,156,.15)",
            paddingBottom: 8,
            marginBottom: 9,
            font: `10px ${mono}`,
          }}
        >
          <strong style={{ color: colors.text }}>
            {hovered?.name}
          </strong>
          <span style={{ color: colors.neon, fontSize: 8 }}>
            {hovered?.group?.toUpperCase()}
          </span>
        </div>
  
        <p
          style={{
            margin: "0 0 12px",
            color: colors.muted,
            font: `11px ${mono}`,
            lineHeight: 1.5,
          }}
        >
          {hovered?.description}
        </p>
  
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 6,
            color: colors.muted,
            font: `9px ${mono}`,
          }}
        >
          <span style={{ ...cardStyle, padding: 7 }}>
            REPOSITORIES<br />
            <b style={{ color: colors.text }}>
              {hovered?.repositories}
            </b>
          </span>
  
          <span style={{ ...cardStyle, padding: 7 }}>
            TELEMETRY<br />
            <b style={{ color: colors.text }}>
              {hovered?.commits} commits
            </b>
          </span>
        </div>
  
        <div
          style={{
            marginTop: 10,
            paddingTop: 8,
            borderTop: "1px solid rgba(0,255,156,.1)",
            color: colors.neon,
            font: `9px ${mono}`,
          }}
        >
          ● Evidence groundedInspect ↓
        </div>
      </div>
  
      <div
        style={{
          position: "absolute",
          zIndex: 3,
          left: 24,
          bottom: 18,
          ...cardStyle,
          padding: "7px 10px",
          color: colors.muted,
          font: `9px ${mono}`,
        }}
      >
        HIERARCHY:{" "}
        <span style={{ color: "#fff" }}>● Root</span>{" "}
        <span style={{ color: colors.neon }}>● Domain</span>{" "}
        <span style={{ color: colors.vibrant }}>● Skill</span>{" "}
        <span style={{ color: colors.dim }}>● Project Evidence</span>
      </div>
  
      <div
        style={{
          position: "absolute",
          zIndex: 3,
          right: 24,
          bottom: 18,
          display: "flex",
          gap: 3,
          ...cardStyle,
          padding: 4,
        }}
      >
        <button
          onClick={() =>
            setZoom((value) => Math.min(1.45, value + 0.12))
          }
          style={buttonStyle}
        >
          ＋
        </button>
  
        <button
          onClick={() =>
            setZoom((value) => Math.max(0.75, value - 0.12))
          }
          style={buttonStyle}
        >
          −
        </button>
  
        <span
          style={{
            width: 1,
            margin: "3px 4px",
            background: "rgba(0,255,156,.2)",
          }}
        />
  
        <button
          onClick={() => setZoom(1)}
          style={buttonStyle}
        >
          ↻ RESET
        </button>
      </div>
    </div>
  );
  
  return graphUI;
}

const buttonStyle: React.CSSProperties = { border: 0, borderRadius: 3, padding: "4px 7px", background: "transparent", color: colors.muted, cursor: "pointer", font: `10px ${mono}` };

function SkillCard({ item, index, open, onToggle }: { item: Evidence; index: number; open: boolean; onToggle: () => void }) {
  const projects = item.project_evidence || [];
  const commits = projects.reduce((total, project) => total + (project.commits || 0), 0);
  return <article style={{ ...cardStyle, padding: 20, borderColor: open ? "rgba(0,255,156,.4)" : undefined }}><div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 22 }}><div><span style={{ color: "rgba(0,217,130,.75)", font: `9px ${mono}`, letterSpacing: ".12em", textTransform: "uppercase" }}>Verified skill</span><h3 style={{ margin: "6px 0 0", color: colors.text, fontSize: 20, fontWeight: 500 }}>{item.skill}</h3></div><span style={{ color: colors.neon, font: `10px ${mono}`, whiteSpace: "nowrap" }}>● VERIFIED</span></div><div style={{ display: "flex", justifyContent: "space-between", padding: "12px 0", borderTop: "1px solid rgba(0,255,156,.1)", borderBottom: "1px solid rgba(0,255,156,.1)", color: colors.muted, font: `9px ${mono}` }}><span>REPOSITORIES<br /><strong style={{ color: colors.text, fontSize: 13 }}>{projects.length}</strong></span><span>COMMITS LOGGED<br /><strong style={{ color: colors.text, fontSize: 13 }}>{commits}</strong></span></div><div style={{ height: 4, margin: "16px 0", background: "#050b09", borderRadius: 4 }}><div style={{ width: `${Math.min(96, 42 + projects.length * 14 + index * 2)}%`, height: "100%", background: `linear-gradient(90deg, ${colors.dim}, ${colors.neon})`, borderRadius: 4 }} /></div><button onClick={onToggle} style={{ width: "100%", display: "flex", justifyContent: "space-between", padding: 0, border: 0, background: "none", color: colors.neon, cursor: "pointer", font: `10px ${mono}` }}><span>Inspect raw evidence</span><span style={{ transform: open ? "rotate(180deg)" : "none" }}>↓</span></button>{open && <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px dashed rgba(0,255,156,.18)", color: colors.muted, font: `10px ${mono}` }}>{projects.length ? projects.map((project) => <div key={project.name} style={{ display: "flex", justifyContent: "space-between", gap: 8, marginBottom: 7 }}><span style={{ color: colors.text }}>• {project.name}</span><span>{project.commits || 0} commits</span></div>) : "No repository evidence recorded."}</div>}</article>;
}

export function KnowledgeGraphReferencePage({ candidateId, candidateName, username, onGoBack }: Props) {
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [jobs, setJobs] = useState<JobMatch[]>([]);
  const [filter, setFilter] = useState("all");
  const [openSkill, setOpenSkill] = useState<string | null>(null);
  const [motion, setMotion] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!candidateId) return;
    Promise.all([fetch(`${API}/evidence/candidate/${candidateId}`).then((response) => response.json()), fetch(`${API}/match/${candidateId}?limit=12`).then((response) => response.json())]).then(([evidenceData, jobData]) => { setEvidence(evidenceData.evidence || []); setJobs(Array.isArray(jobData) ? jobData : []); }).finally(() => setLoading(false));
  }, [candidateId]);

  const visibleEvidence = evidence.filter((item) => filter === "all" || (filter === "languages" ? /python|javascript|typescript|java|go|rust|ruby|php|kotlin|c\+\+/.test(item.skill.toLowerCase()) : filter === "frameworks" ? /react|vue|angular|fastapi|django|next|flask|express|spring/.test(item.skill.toLowerCase()) : !/python|javascript|typescript|java|go|rust|ruby|php|kotlin|c\+\+|react|vue|angular|fastapi|django|next|flask|express|spring/.test(item.skill.toLowerCase())));
  const go = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: motion ? "smooth" : "auto" });
  const button = (active: boolean): React.CSSProperties => ({ padding: "7px 9px", border: `1px solid ${active ? colors.neon : "rgba(0,255,156,.15)"}`, borderRadius: 4, background: active ? "rgba(0,255,156,.1)" : "transparent", color: active ? colors.neon : colors.muted, cursor: "pointer", font: `9px ${mono}` });

  return <div style={{ minHeight: "100vh", background: colors.bg, color: colors.text, fontFamily: "'Geist Variable', Inter, sans-serif" }}>
    <header style={{ position: "sticky", top: 0, zIndex: 10, height: 62, borderBottom: "1px solid rgba(0,255,156,.1)", background: "rgba(2,6,5,.9)", backdropFilter: "blur(14px)" }}><div style={{ maxWidth: 1280, height: "100%", margin: "auto", padding: "0 24px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 20 }}><button onClick={onGoBack} style={{ border: 0, background: "none", color: colors.text, cursor: "pointer", textAlign: "left" }}><strong style={{ display: "block", font: `12px ${mono}`, letterSpacing: ".12em" }}>● CAREERGRAPH</strong><small style={{ color: "rgba(0,255,156,.7)", font: `8px ${mono}`, letterSpacing: ".12em" }}>TECHNICAL CONSTELLATION v2.4</small></button><nav style={{ display: "flex", gap: 22, font: `10px ${mono}`, textTransform: "uppercase" }}><button onClick={() => go("constellation")} style={{ ...button(true), border: 0, borderBottom: `1px solid ${colors.neon}`, borderRadius: 0 }}>Knowledge Graph</button><button onClick={() => go("skills-section")} style={{ ...button(false), border: 0 }}>Skills Extracted</button><button onClick={() => go("jobs-section")} style={{ ...button(false), border: 0 }}>Job Postings</button></nav><div style={{ display: "flex", alignItems: "center", gap: 10, color: colors.muted, font: `9px ${mono}` }}><span>github.com/<b style={{ color: colors.neon }}>{username}</b></span><button onClick={() => setMotion((value) => !value)} style={button(motion)}>[Motion: {motion ? "ON" : "OFF"}]</button></div></div></header>
    <section id="constellation" style={{ position: "relative", height: "calc(100vh - 62px)", minHeight: 650, overflow: "hidden", borderBottom: "1px solid rgba(0,255,156,.1)", background: "radial-gradient(circle at 50% 42%, rgba(0,255,156,.05), transparent 50%)" }}><div style={{ position: "relative", zIndex: 2, maxWidth: 1280, margin: "auto", padding: "30px 24px" }}><div style={{ color: colors.neon, font: `10px ${mono}`, letterSpacing: ".12em", textTransform: "uppercase" }}>● Astronomical repository topology</div><h1 style={{ margin: "8px 0 2px", fontSize: "clamp(34px, 5vw, 58px)", lineHeight: 1, fontWeight: 300, letterSpacing: "-.03em" }}>KNOWLEDGE GRAPH</h1><p style={{ maxWidth: 430, margin: 0, color: colors.muted, fontSize: 13, lineHeight: 1.6 }}>Your technical constellation synthesized from verified repositories, language vectors, and commit telemetry.</p></div><div style={{ position: "absolute", inset: "0 0 54px" }}>{loading ? <div style={{ display: "grid", placeItems: "center", height: "100%", color: colors.faint, font: `11px ${mono}` }}>Mapping your graph...</div> : <Graph evidence={evidence} candidateName={candidateName} reducedMotion={!motion} />}</div><div style={{ position: "absolute", zIndex: 2, right: 24, bottom: 16, color: colors.neon, font: `10px ${mono}`, textTransform: "uppercase" }}><button onClick={() => go("skills-section")} style={{ border: 0, background: "none", color: colors.neon, cursor: "pointer", font: "inherit" }}>Scroll to explore evidence ↓</button></div></section>
    <section id="skills-section" style={{ padding: "84px 24px", borderBottom: "1px solid rgba(0,255,156,.1)" }}><div style={{ maxWidth: 1280, margin: "auto" }}><div style={{ display: "flex", justifyContent: "space-between", alignItems: "end", gap: 20, flexWrap: "wrap", borderBottom: "1px solid rgba(0,255,156,.1)", paddingBottom: 22, marginBottom: 36 }}><div><div style={{ color: colors.neon, font: `10px ${mono}`, letterSpacing: ".12em", textTransform: "uppercase" }}>● Synthesized telemetry & ground truth</div><h2 style={{ margin: "8px 0 5px", fontSize: 34, fontWeight: 300 }}>Skills extracted from GitHub</h2><p style={{ margin: 0, color: colors.muted, fontSize: 13 }}>Built from your repositories, languages, pull requests, and commit history.</p></div><div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>{[["all", `All Skills (${evidence.length})`], ["languages", "Languages"], ["frameworks", "Frameworks"], ["infrastructure", "Cloud & Tools"]].map(([key, label]) => <button key={key} onClick={() => setFilter(key)} style={button(filter === key)}>{label}</button>)}</div></div><div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: 22 }}>{visibleEvidence.map((item, index) => <SkillCard key={item.skill} item={item} index={index} open={openSkill === item.skill} onToggle={() => setOpenSkill(openSkill === item.skill ? null : item.skill)} />)}</div>{!loading && visibleEvidence.length === 0 && <p style={{ color: colors.muted, font: `11px ${mono}` }}>No verified skills found.</p>}</div></section>
    <section id="jobs-section" style={{ padding: "84px 24px", background: "rgba(2,6,5,.65)" }}><div style={{ maxWidth: 1280, margin: "auto" }}><div style={{ color: colors.neon, font: `10px ${mono}`, letterSpacing: ".12em", textTransform: "uppercase" }}>● Market alignment</div><h2 style={{ margin: "8px 0 5px", fontSize: 34, fontWeight: 300 }}>Job postings matched to your graph</h2><p style={{ margin: "0 0 32px", color: colors.muted, fontSize: 13 }}>Ranked by verified skill overlap with the profile you just ingested.</p>{loading ? <p style={{ color: colors.faint, font: `11px ${mono}` }}>Querying job graph...</p> : jobs.length ? <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 12 }}>{jobs.map((job, index) => <div key={`${job.job}-${index}`} style={{ ...cardStyle, padding: 16, display: "flex", justifyContent: "space-between", gap: 12 }}><div style={{ minWidth: 0 }}><strong style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 13 }}>{index + 1}. {job.job}</strong><span style={{ color: colors.muted, font: `11px ${mono}` }}>{job.company || "Unknown company"}</span></div><span style={{ flexShrink: 0, alignSelf: "center", padding: "4px 8px", border: "1px solid rgba(0,255,156,.3)", borderRadius: 999, color: colors.neon, font: `11px ${mono}` }}>{job.overlap} skills</span></div>)}</div> : <div style={{ ...cardStyle, padding: 24, color: colors.muted, font: `11px ${mono}` }}>No matched postings yet. Scrape live jobs to populate this section.</div>}</div></section>
    <footer style={{ padding: "28px 24px", borderTop: "1px solid rgba(0,255,156,.1)", color: colors.faint, font: `9px ${mono}`, display: "flex", justifyContent: "space-between" }}><span>● CareerGraph Scientific Visualization Engine</span><button onClick={() => go("constellation")} style={{ border: 0, background: "none", color: colors.muted, cursor: "pointer", font: "inherit" }}>Top of graph ↑</button></footer>
  </div>;
}

export default KnowledgeGraphReferencePage;