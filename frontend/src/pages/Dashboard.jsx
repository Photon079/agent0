import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';

export default function Dashboard() {
  const [candidates, setCandidates] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [backend, setBackend] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([
      api.get('/candidates'),
      api.get('/jobs'),
      api.get('/backend'),
    ]).then(([c, j, b]) => {
      setCandidates(c);
      setJobs(j);
      setBackend(b);
      setLoading(false);
    });
  }, []);

  const totalSkills = [...new Set(candidates.flatMap(c => c.skills))].length;

  if (loading) return <div className="loading"><div className="spinner" /><span>Loading graph...</span></div>;

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Knowledge Graph</h1>
        <p className="page-sub">Career intelligence powered by graph-grounded AI</p>
      </div>

      <div className="stats-row">
        <div className="stat-card" style={{'--accent-color':'#6366f1'}}>
          <div className="stat-number" style={{color:'#818cf8'}}>{candidates.length}</div>
          <div className="stat-label">Candidates</div>
        </div>
        <div className="stat-card" style={{'--accent-color':'#22d3ee'}}>
          <div className="stat-number" style={{color:'#67e8f9'}}>{jobs.length}</div>
          <div className="stat-label">Job Postings</div>
        </div>
        <div className="stat-card" style={{'--accent-color':'#34d399'}}>
          <div className="stat-number" style={{color:'#6ee7b7'}}>{totalSkills}</div>
          <div className="stat-label">Unique Skills</div>
        </div>
        <div className="stat-card" style={{'--accent-color':'#f59e0b'}}>
          <div className="stat-number" style={{color:'#fcd34d'}}>
            {backend?.active_backend === 'falkor' ? '⬡' : '🗄'}
          </div>
          <div className="stat-label">
            {backend?.active_backend === 'falkor' ? 'FalkorDB' : 'SQLite'}
          </div>
        </div>
      </div>

      <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:'1.5rem'}}>
        {/* Recent Candidates */}
        <div>
          <div className="section-title">👥 Recent Candidates</div>
          <div style={{display:'flex', flexDirection:'column', gap:'0.5rem'}}>
            {candidates.slice(0,6).map(c => (
              <div key={c.id} className="card card-clickable" onClick={() => navigate(`/candidates/${c.id}`)}>
                <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:'0.6rem'}}>
                  <div>
                    <div style={{fontWeight:600, fontSize:'0.95rem'}}>{c.name || `Candidate #${c.id}`}</div>
                    <div style={{fontSize:'0.75rem', color:'var(--muted2)'}}>
                      {c.experience_level && `${c.experience_level} `} 
                      {c.location && `• ${c.location}`}
                    </div>
                  </div>
                  <span className="badge badge-muted">{c.project_count} repos</span>
                </div>
                <div className="skill-tags">
                  {c.skills.slice(0,5).map(s => (
                    <span key={s} className={`skill-tag skill-${s.toLowerCase().replace('#','sharp').replace(/\s/g,'-')}`}>{s}</span>
                  ))}
                  {c.skills.length > 5 && <span className="badge badge-muted">+{c.skills.length - 5}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Jobs */}
        <div>
          <div className="section-title">💼 Job Postings</div>
          <div style={{display:'flex', flexDirection:'column', gap:'0.5rem'}}>
            {jobs.slice(0,6).map(j => (
              <div key={j.id} className="card">
                <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:'0.6rem'}}>
                  <div>
                    <div style={{fontWeight:600, fontSize:'0.9rem'}}>{j.title}</div>
                    <div style={{fontSize:'0.78rem', color:'var(--muted2)'}}>
                      {j.company} 
                      {j.location && ` • ${j.location}`}
                      {j.experience_level && ` • ${j.experience_level}`}
                    </div>
                  </div>
                  <span className="badge badge-accent">{j.skills.length} skills</span>
                </div>
                <div className="skill-tags">
                  {j.skills.slice(0,4).map(s => (
                    <span key={s} className={`skill-tag skill-${s.toLowerCase().replace('#','sharp')}`}>{s}</span>
                  ))}
                  {j.skills.length > 4 && <span className="badge badge-muted">+{j.skills.length - 4}</span>}
                </div>
              </div>
            ))}
            {jobs.length === 0 && (
              <div className="card">
                <div className="empty">
                  <div className="empty-icon">📭</div>
                  <div className="empty-text">No jobs yet. Run the scraper or add via API.</div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
