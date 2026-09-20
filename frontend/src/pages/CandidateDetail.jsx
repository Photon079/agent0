import { useState, useEffect, useCallback } from 'react';
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

// Experience level tier helper
const expTier = (label) => {
  if (!label) return -1;
  const l = label.toLowerCase();
  if (l.includes('intern')) return 0;
  if (l.includes('junior') || l.includes('entry') || l.includes('jr') || l.includes('associate')) return 1;
  if (l.includes('mid') || l.includes('intermediate')) return 2;
  if (l.includes('senior') || l.includes('sr')) return 3;
  if (l.includes('lead') || l.includes('staff') || l.includes('principal')) return 4;
  if (l.includes('manager') || l.includes('director') || l.includes('head')) return 5;
  return -1;
};

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
  const [tailorLoading, setTailorLoading] = useState({});
  const [tailoredResumeData, setTailoredResumeData] = useState({});

  const loadData = useCallback(() => {
    Promise.all([
      api.get('/candidates'),
      api.get(`/evidence/candidate/${id}`),
      api.get(`/match/${id}?limit=50`),
      api.get('/jobs'),
    ]).then(([cs, ev, m, j]) => {
      const cand = cs.find(c => c.id == id);
      setCandidate(cand);
      setEvidence(ev);
      setJobs(j);

      const jobMap = {};
      j.forEach(job => {
        if (job.id) jobMap['id:' + job.id] = job;
        if (job.url) jobMap['url:' + job.url] = job;
        jobMap[job.title + '|' + job.company] = job;
      });

      const candExpTierRaw = expTier(cand?.experience_level);
      const candExpTier = candExpTierRaw >= 0 ? candExpTierRaw : 1;

      const maxOverlap = Math.max(...m.map(match => match.overlap), 1);

      const enriched = m.map(match => {
        const jobMeta = (match.job_id && jobMap['id:' + match.job_id]) ||
                        (match.url && jobMap['url:' + match.url]) ||
                        jobMap[match.job + '|' + match.company] || null;
        const jobExpLabel = jobMeta?.experience_level || null;
        const jobExpSource = jobExpLabel || match.job || '';
        const jobExpTier = expTier(jobExpSource);
        const tierDiff = (candExpTier >= 0 && jobExpTier >= 0) ? Math.abs(candExpTier - jobExpTier) : -1;

        const expFactor = tierDiff < 0 ? 1.0
          : tierDiff === 0 ? 1.0
          : tierDiff === 1 ? 0.7
          : tierDiff === 2 ? 0.35
          : 0.1;

        const jobTotalSkills = jobMeta?.skills?.length || 0;
        const skillPct = jobTotalSkills > 0 ? (match.overlap / jobTotalSkills) : null;
        const compositePct = skillPct !== null
          ? Math.round((skillPct * 0.4 + expFactor * 0.6) * 100)
          : Math.min(100, Math.round((match.overlap / maxOverlap) * 100));

        return {
          ...match,
          jobMeta,
          jobExpLabel,
          jobExpSource,
          jobExpTier,
          tierDiff,
          expFactor,
          compositePct: Math.max(0, Math.min(100, compositePct)),
        };
      });

      // Rank strictly from 100% match down to low match
      enriched.sort((a, b) => b.compositePct - a.compositePct || b.overlap - a.overlap);

      setMatches(enriched);
      setLoading(false);
    }).catch(err => {
      console.error("Failed to load candidate matches:", err);
      setLoading(false);
    });
  }, [id]);

  useEffect(() => {
    loadData();

    const handleUpdate = () => {
      loadData();
    };

    window.addEventListener('jobs-scraped', handleUpdate);
    window.addEventListener('jobs-updated', handleUpdate);

    // Poll every 5 seconds so background scrapes automatically trigger updates
    const interval = setInterval(loadData, 5000);

    return () => {
      window.removeEventListener('jobs-scraped', handleUpdate);
      window.removeEventListener('jobs-updated', handleUpdate);
      clearInterval(interval);
    };
  }, [id, loadData]);

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

  const tailorResume = (jobId) => {
    if (!jobId) return;
    setTailorLoading(prev => ({ ...prev, [jobId]: true }));
    setTailoredResumeData(prev => ({ ...prev, [jobId]: null }));
    api.post('/tailor-resume', { candidate_id: String(id), job_id: String(jobId) })
      .then(data => {
        setTailoredResumeData(prev => ({ ...prev, [jobId]: data }));
        setTailorLoading(prev => ({ ...prev, [jobId]: false }));
      })
      .catch(err => {
        console.error("Failed to tailor resume:", err);
        setTailorLoading(prev => ({ ...prev, [jobId]: false }));
      });
  };

  if (loading) return <div className="loading"><div className="spinner" /><span>Loading candidate graph...</span></div>;
  if (!candidate) return <div className="empty"><div className="empty-icon">❓</div><div className="empty-text">Candidate not found</div></div>;

  const candExpTierRaw = expTier(candidate?.experience_level);
  const candExpTier = candExpTierRaw >= 0 ? candExpTierRaw : 1;

  return (
    <div>
      <div style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
        <button className="back-btn" onClick={() => navigate('/candidates')}>← Back to Candidates</button>
        <button className="btn btn-sm btn-outline" onClick={() => window.open(`/profile/${id}`, '_blank')}>
          🔗 View Public Profile
        </button>
      </div>

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
              const compositePct = m.compositePct;

              // Badge colour based on composite score
              const fitColor = compositePct >= 70 ? { background: 'rgba(34,197,94,0.12)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.25)' }
                : compositePct >= 45 ? { background: 'rgba(234,179,8,0.12)', color: '#eab308', border: '1px solid rgba(234,179,8,0.25)' }
                : { background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)' };

              const expBadgeColor = m.tierDiff < 0 ? null
                : m.tierDiff === 0 ? { background: 'rgba(34,197,94,0.12)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.25)' }
                : m.tierDiff === 1 ? { background: 'rgba(234,179,8,0.12)', color: '#eab308', border: '1px solid rgba(234,179,8,0.25)' }
                : { background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)' };
              return (
                <div key={i} style={{display:'flex', flexDirection:'column', marginBottom:'1rem'}}>
                  <div className="match-row" style={{marginBottom:0}}>
                    <div className="match-left">
                      {m.jobMeta?.url || m.url ? (
                        <a
                          href={m.jobMeta?.url || m.url}
                          target="_blank"
                          rel="noreferrer"
                          className="match-title"
                          style={{color:'var(--accent)', textDecoration:'none'}}
                          onMouseEnter={e => e.currentTarget.style.textDecoration='underline'}
                          onMouseLeave={e => e.currentTarget.style.textDecoration='none'}
                        >
                          {m.job} ↗
                        </a>
                      ) : (
                        <div className="match-title">{m.job}</div>
                      )}
                      <div className="match-company">{m.company}</div>
                      <div style={{display:'flex', gap:'0.4rem', marginTop:'0.4rem', flexWrap:'wrap'}}>
                        <span className="badge" style={fitColor}>
                          {compositePct}% fit
                        </span>
                        {m.jobExpTier >= 0 && expBadgeColor && (
                          <span className="badge" style={expBadgeColor}>
                            {m.tierDiff === 0 ? '✓' : '⚠'} {m.jobExpLabel || m.jobExpSource.split(' ').find(w => expTier(w) >= 0) || m.jobExpSource}
                          </span>
                        )}
                        {m.penalties && m.penalties.filter(p => !p.startsWith('Requires')).map((p, idx) => (
                          <span key={idx} className="badge" style={{background:'rgba(239,68,68,0.1)', color:'#ef4444', border:'1px solid rgba(239,68,68,0.2)'}}>⚠ {p}</span>
                        ))}
                      </div>
                    </div>
                    <div className="match-overlap">
                      <div className="overlap-bar">
                        {/* Bar width driven by composite fit, not raw overlap */}
                        <div className="overlap-fill" style={{
                          width: `${compositePct}%`,
                          background: compositePct >= 70
                            ? 'linear-gradient(90deg, #22c55e, #16a34a)'
                            : compositePct >= 45
                            ? 'linear-gradient(90deg, #eab308, #ca8a04)'
                            : 'linear-gradient(90deg, #ef4444, #dc2626)',
                        }} />
                      </div>
                      <span className="badge badge-accent">{m.overlap} skills</span>
                    </div>
                  </div>
                  <div style={{padding:'0.75rem 1rem', background:'var(--surface-bg)', border:'1px solid var(--border)', borderTop:'none', borderBottomLeftRadius:'8px', borderBottomRightRadius:'8px'}}>
                     <button className="btn btn-sm btn-outline" onClick={() => tailorResume(m.job_id)} disabled={tailorLoading[m.job_id]}>
                       {tailorLoading[m.job_id] ? 'Generating Agentic Resume...' : 'Generate Agentic Resume'}
                     </button>
                     {tailoredResumeData[m.job_id] && (
                       <div className="card" style={{padding:'1rem', background:'var(--surface2)', marginTop: '0.75rem', border:'1px solid var(--border)'}}>
                         <div style={{fontWeight:700, color:'var(--accent)', marginBottom: '0.75rem'}}>✅ Resume Generated!</div>
                         <div style={{display:'flex', gap:'0.75rem', flexWrap:'wrap'}}>
                           {tailoredResumeData[m.job_id].pdf_file && (
                             <a href={`http://localhost:8000/download-resume/${tailoredResumeData[m.job_id].pdf_file.split('/').pop()}`} target="_blank" rel="noreferrer" download className="btn btn-primary btn-sm">
                               📥 Download PDF
                             </a>
                           )}
                           {tailoredResumeData[m.job_id].tex_file && (
                             <a href={`http://localhost:8000/download-resume/${tailoredResumeData[m.job_id].tex_file.split('/').pop()}`} target="_blank" rel="noreferrer" download className="btn btn-outline btn-sm">
                               📥 Download .tex
                             </a>
                           )}
                         </div>
                       </div>
                     )}
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
