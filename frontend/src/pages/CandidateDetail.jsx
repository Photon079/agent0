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
  const [bullets, setBullets] = useState(null);
  const [bulletsLoading, setBulletsLoading] = useState(false);
  const [activeBullet, setActiveBullet] = useState(null);
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
    api.get(`/gap/${id}/${selectedJob}/project`).then(data => {
      setGap(data);
      setGapLoading(false);
    });
  };

  const generateBullets = () => {
    if (!selectedJob) return;
    setBulletsLoading(true);
    setBullets(null);
    setActiveBullet(null);
    api.post('/generate/bullets', { candidate_id: id, job_id: selectedJob }).then(data => {
      setBullets(data.bullets);
      setBulletsLoading(false);
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
          <div className="section-title">📈 Bridge the Gap</div>
          <p style={{fontSize:'0.8rem', color:'var(--muted2)', marginBottom:'1rem'}}>Select a job to generate a personalized micro-project to fill your skill gaps.</p>
          <div style={{display:'flex', gap:'0.75rem', marginBottom:'1rem', flexWrap:'wrap'}}>
            <select className="select" style={{flex:1}} value={selectedJob} onChange={e => setSelectedJob(e.target.value)}>
              <option value="">Select a job posting…</option>
              {jobs.map(j => <option key={j.id} value={j.id}>{j.title} @ {j.company}</option>)}
            </select>
            <button className="btn btn-primary" onClick={analyzeGap} disabled={!selectedJob || gapLoading}>
              {gapLoading ? 'Generating…' : 'Generate Project'}
            </button>
          </div>
          {gap && (
            <div>
              {gap.title === "No Gap Detected" ? (
                <div className="alert alert-success">✅ {gap.description}</div>
              ) : (
                <div className="card" style={{marginTop: '1rem', background: 'var(--surface2)', border: '1px solid var(--border)'}}>
                  <div style={{fontWeight: '700', fontSize: '1.1rem', marginBottom: '0.5rem', color: 'var(--accent)'}}>
                    💡 {gap.title}
                  </div>
                  <div style={{fontSize: '0.875rem', color: 'var(--muted)', lineHeight: '1.6'}}>
                    {gap.description}
                  </div>
                </div>
              )}
            </div>
          )}

          <hr className="divider" />

          {/* Resume Bullets */}
          <div className="section-title">📄 Proof-Backed Resume</div>
          <p style={{fontSize:'0.8rem', color:'var(--muted2)', marginBottom:'1rem'}}>Generate resume bullets for this job, tied directly to verifiable graph evidence.</p>
          <div style={{display:'flex', gap:'0.75rem', marginBottom:'1rem'}}>
            <button className="btn btn-primary" onClick={generateBullets} disabled={!selectedJob || bulletsLoading} style={{flex:1}}>
              {bulletsLoading ? 'Writing...' : 'Draft Tailored Resume Bullets'}
            </button>
          </div>
          {bullets && (
            <div style={{display:'flex', flexDirection:'column', gap:'0.75rem'}}>
              {bullets.length === 0 ? (
                <div className="empty"><div className="empty-text">Not enough matching skills to generate bullets.</div></div>
              ) : (
                bullets.map((b, i) => (
                  <div key={i} className="card" style={{padding:'1rem'}}>
                    <div style={{fontSize:'0.9rem', lineHeight:'1.5', marginBottom:'0.75rem'}}>
                      • {b.bullet}
                    </div>
                    <div style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                      <span className="badge badge-muted">{b.skill}</span>
                      <button 
                        className="btn btn-sm btn-outline" 
                        onClick={() => setActiveBullet(activeBullet === i ? null : i)}
                      >
                        {activeBullet === i ? 'Hide Proof' : 'Why this claim?'}
                      </button>
                    </div>
                    {activeBullet === i && (
                      <div style={{marginTop:'1rem', padding:'0.75rem', background:'var(--surface-bg)', borderRadius:'4px', fontSize:'0.8rem', borderLeft:'3px solid var(--accent)'}}>
                        <div style={{fontWeight:700, marginBottom:'0.5rem'}}>Graph Evidence Trace:</div>
                        <div style={{fontFamily:'JetBrains Mono', color:'var(--muted)'}}>
                          Node: Candidate 
                          <br/>↓ HAS_SKILL 
                          <br/>Node: {b.skill}
                          <br/>↓ PROVEN_BY 
                          <br/>Sources: {b.evidence_ids?.join(', ') || 'N/A'}
                        </div>
                        <div style={{marginTop:'0.75rem'}}>
                          <a href="#" className="evidence-link">🔗 Copy Public Verification URL</a>
                        </div>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
