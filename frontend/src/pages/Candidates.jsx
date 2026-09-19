import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';

export default function Candidates() {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    api.get('/candidates').then(data => { setCandidates(data); setLoading(false); });
  }, []);

  const filtered = candidates.filter(c =>
    (c.name || '').toLowerCase().includes(search.toLowerCase()) ||
    c.skills.some(s => s.toLowerCase().includes(search.toLowerCase()))
  );

  const totalCommits = (c) => {
    // not available from list endpoint — show project count as proxy
    return c.project_count;
  };

  if (loading) return <div className="loading"><div className="spinner" /><span>Loading candidates...</span></div>;

  return (
    <div>
      <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:'1.75rem'}}>
        <div>
          <h1 className="page-title">Candidates</h1>
          <p className="page-sub">{candidates.length} indexed in graph</p>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/ingest')}>+ Add Candidate</button>
      </div>

      <input
        className="form-input"
        placeholder="Search by name or skill…"
        value={search}
        onChange={e => setSearch(e.target.value)}
        style={{marginBottom:'1.25rem', width:'100%'}}
      />

      {filtered.length === 0 && (
        <div className="empty">
          <div className="empty-icon">🔍</div>
          <div className="empty-text">No candidates found</div>
        </div>
      )}

      <div className="card-grid">
        {filtered.map(c => (
          <div key={c.id} className="card card-clickable" onClick={() => navigate(`/candidates/${c.id}`)}>
            <div style={{display:'flex', alignItems:'center', gap:'0.75rem', marginBottom:'0.85rem'}}>
              <div style={{
                width:38, height:38, borderRadius:'50%', flexShrink:0,
                background:`linear-gradient(135deg, hsl(${(c.id * 60) % 360},70%,55%), hsl(${(c.id * 60 + 60) % 360},70%,40%))`,
                display:'flex', alignItems:'center', justifyContent:'center',
                fontWeight:700, fontSize:'0.9rem', color:'#fff',
              }}>
                {(c.name || 'C')[0].toUpperCase()}
              </div>
              <div>
                <div style={{fontWeight:700, fontSize:'0.95rem'}}>{c.name || `Candidate #${c.id}`}</div>
                <div style={{fontSize:'0.75rem', color:'var(--muted2)'}}>
                  {c.email || `id: ${c.id}`}
                </div>
              </div>
            </div>
            <div style={{display:'flex', gap:'0.5rem', marginBottom:'0.85rem'}}>
              <span className="badge badge-accent">{c.skills.length} skills</span>
              <span className="badge badge-muted">{c.project_count} repos</span>
            </div>
            <div className="skill-tags">
              {c.skills.slice(0,6).map(s => (
                <span key={s} className={`skill-tag skill-${s.toLowerCase().replace('#','sharp').replace(/\s/g,'-')}`}>{s}</span>
              ))}
              {c.skills.length > 6 && <span className="badge badge-muted">+{c.skills.length - 6}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
