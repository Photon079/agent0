import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api';

function SkillSection({ skillName, projectEvidence, expEvidence }) {
  const [open, setOpen] = useState(false);
  const total = projectEvidence.length + expEvidence.length;
  const cls = `skill-tag skill-${skillName.toLowerCase().replace('#','sharp').replace(/\s/g,'-')}`;

  return (
    <div className="skill-section">
      <div className="skill-section-header" onClick={() => setOpen(o => !o)}>
        <div className="skill-section-name">
          <span className={cls}>{skillName}</span>
          <span className="badge badge-muted">{total} sources</span>
        </div>
        <span style={{color:'var(--muted)', fontSize:'0.8rem'}}>{open ? '▲' : '▼'}</span>
      </div>
      {open && (
        <div className="skill-section-body">
          {projectEvidence.length > 0 && (
            <div className="evidence-section">
              <div className="evidence-section-title">🛠 Projects</div>
              {projectEvidence.map((p, i) => (
                <div key={i} className="evidence-item">
                  <div className="evidence-icon">📁</div>
                  <div className="evidence-body">
                    <div className="evidence-name">{p.name}</div>
                    {p.description && <div style={{fontSize:'0.78rem', color:'var(--muted2)', marginTop:'0.15rem'}}>{p.description}</div>}
                    <div className="evidence-meta">
                      {p.commits > 0 && <span>⚡ {p.commits.toLocaleString()} commits</span>}
                      {p.url && <a href={p.url} target="_blank" rel="noreferrer" className="evidence-link">↗ GitHub</a>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
          {expEvidence.length > 0 && (
            <div className="evidence-section">
              <div className="evidence-section-title">🏢 Experience</div>
              {expEvidence.map((e, i) => (
                <div key={i} className="evidence-item">
                  <div className="evidence-icon">💼</div>
                  <div className="evidence-body">
                    <div className="evidence-name">{e.role} @ {e.company}</div>
                    <div className="evidence-meta"><span>{e.duration}</span></div>
                  </div>
                </div>
              ))}
            </div>
          )}
          {total === 0 && <div style={{color:'var(--muted2)', fontSize:'0.85rem'}}>No evidence recorded yet</div>}
        </div>
      )}
    </div>
  );
}

export default function CandidateDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [candidate, setCandidate] = useState(null);
  const [evidence, setEvidence] = useState(null);
  const [matches, setMatches] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState('');
  const [gap, setGap] = useState(null);
  const [gapLoading, setGapLoading] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get('/candidates'),
      api.get(`/evidence/candidate/${id}`),
      api.get(`/match/${id}`),
      api.get('/jobs'),
    ]).then(([cs, ev, m, j]) => {
      const cand = cs.find(c => c.id == id);
      setCandidate(cand);
      setEvidence(ev);
      setMatches(m.slice(0, 10));
      setJobs(j);
      setLoading(false);
    });
  }, [id]);

  const analyzeGap = () => {
    if (!selectedJob) return;
    setGapLoading(true);
    setGap(null);
    api.get(`/gap/${id}/${selectedJob}`).then(data => {
      setGap(data);
      setGapLoading(false);
    });
  };

  if (loading) return <div className="loading"><div className="spinner" /><span>Loading candidate graph...</span></div>;
  if (!candidate) return <div className="empty"><div className="empty-icon">❓</div><div className="empty-text">Candidate not found</div></div>;

  const maxOverlap = Math.max(...matches.map(m => m.overlap), 1);

  return (
    <div>
      <button className="back-btn" onClick={() => navigate('/candidates')}>← Back to Candidates</button>

      {/* Header */}
      <div className="card" style={{marginBottom:'1.5rem', background:'linear-gradient(135deg, rgba(99,102,241,0.08), rgba(34,211,238,0.04))'}}>
        <div style={{display:'flex', alignItems:'center', gap:'1rem'}}>
          <div style={{
            width:56, height:56, borderRadius:'50%', flexShrink:0,
            background:`linear-gradient(135deg, hsl(${(candidate.id * 60) % 360},70%,55%), hsl(${(candidate.id * 60 + 60) % 360},70%,40%))`,
            display:'flex', alignItems:'center', justifyContent:'center',
            fontWeight:700, fontSize:'1.4rem', color:'#fff',
          }}>
            {(candidate.name || 'C')[0].toUpperCase()}
          </div>
          <div>
            <h1 style={{fontSize:'1.5rem', fontWeight:700, letterSpacing:'-0.03em'}}>{candidate.name || `Candidate #${id}`}</h1>
            {candidate.email && <div style={{color:'var(--muted2)', fontSize:'0.875rem'}}>{candidate.email}</div>}
            <div style={{display:'flex', gap:'0.5rem', marginTop:'0.5rem'}}>
              <span className="badge badge-accent">{candidate.skills.length} skills</span>
              <span className="badge badge-muted">{candidate.project_count} repos</span>
            </div>
          </div>
        </div>
      </div>

      <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:'1.5rem'}}>
        {/* Skills + Evidence */}
        <div>
          <div className="section-title">🧠 Skills & Evidence</div>
          <p style={{fontSize:'0.8rem', color:'var(--muted2)', marginBottom:'1rem'}}>Click any skill to expand its project/experience evidence.</p>
          {evidence?.evidence?.map(e => (
            <SkillSection
              key={e.skill}
              skillName={e.skill}
              projectEvidence={e.project_evidence}
              expEvidence={e.experience_evidence}
            />
          ))}
          {(!evidence?.evidence || evidence.evidence.length === 0) && (
            <div className="empty"><div className="empty-icon">📭</div><div className="empty-text">No skill evidence recorded</div></div>
          )}
        </div>

        {/* Right column */}
        <div>
          {/* Job Matches */}
          <div className="section-title">🎯 Job Matches</div>
          <div style={{marginBottom:'1.5rem'}}>
            {matches.map((m, i) => {
              const pct = Math.round((m.overlap / maxOverlap) * 100);
              return (
                <div key={i} className="match-row">
                  <div className="match-left">
                    <div className="match-title">{m.job}</div>
                    <div className="match-company">{m.company}</div>
                  </div>
                  <div className="match-overlap">
                    <div className="overlap-bar">
                      <div className="overlap-fill" style={{width:`${pct}%`}} />
                    </div>
                    <span className="badge badge-accent">{m.overlap} skills</span>
                  </div>
                </div>
              );
            })}
            {matches.length === 0 && (
              <div className="empty"><div className="empty-icon">📭</div><div className="empty-text">No job postings yet</div></div>
            )}
          </div>

          <hr className="divider" />

          {/* Gap Analysis */}
          <div className="section-title">📉 Skill Gap Analysis</div>
          <div style={{display:'flex', gap:'0.75rem', marginBottom:'1rem', flexWrap:'wrap'}}>
            <select className="select" style={{flex:1}} value={selectedJob} onChange={e => setSelectedJob(e.target.value)}>
              <option value="">Select a job posting…</option>
              {jobs.map(j => <option key={j.id} value={j.id}>{j.title} @ {j.company}</option>)}
            </select>
            <button className="btn btn-primary" onClick={analyzeGap} disabled={!selectedJob || gapLoading}>
              {gapLoading ? 'Analyzing…' : 'Analyze'}
            </button>
          </div>
          {gap && (
            <div>
              {gap.missing_skills.length === 0 ? (
                <div className="alert alert-success">✅ No skill gaps — this candidate meets all requirements!</div>
              ) : (
                <div>
                  <div style={{fontSize:'0.8rem', color:'var(--muted2)', marginBottom:'0.6rem'}}>
                    Missing {gap.missing_skills.length} skills:
                  </div>
                  <div className="skill-tags">
                    {gap.missing_skills.map(s => <span key={s} className="gap-tag">{s}</span>)}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
