import { useState, useEffect } from 'react';
import { api } from '../api';

export default function Jobs() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [expanded, setExpanded] = useState(null);
  const [scraping, setScraping] = useState(false);
  const [scrapeResult, setScrapeResult] = useState(null);

  const loadJobs = () => {
    setLoading(true);
    api.get('/jobs').then(data => { setJobs(data); setLoading(false); });
  };

  useEffect(() => { loadJobs(); }, []);

  const refreshJobs = async () => {
    setScraping(true);
    setScrapeResult(null);
    try {
      const result = await api.post('/scrape/jobs', { sources: ['remoteok', 'arbeitnow', 'adzuna'], limit: 20 });
      setScrapeResult(result);
      if (!result.error) loadJobs(); // reload list after scrape
    } catch (e) {
      setScrapeResult({ error: e.message });
    }
    setScraping(false);
  };

  const filtered = jobs.filter(j =>
    (j.title || '').toLowerCase().includes(search.toLowerCase()) ||
    (j.company || '').toLowerCase().includes(search.toLowerCase()) ||
    j.skills.some(s => s.toLowerCase().includes(search.toLowerCase()))
  );

  if (loading) return <div className="loading"><div className="spinner" /><span>Loading jobs...</span></div>;

  return (
    <div>
      <div style={{display:'flex', alignItems:'flex-start', justifyContent:'space-between', marginBottom:'1.75rem', flexWrap:'wrap', gap:'1rem'}}>
        <div>
          <h1 className="page-title">Job Postings</h1>
          <p className="page-sub">{jobs.length} positions in graph</p>
        </div>
        <div style={{display:'flex', flexDirection:'column', alignItems:'flex-end', gap:'0.5rem'}}>
          <button className="btn btn-primary" onClick={refreshJobs} disabled={scraping}>
            {scraping
              ? <><span className="spinner" style={{width:14,height:14,borderWidth:2}} />Scraping…</>
              : '↻ Refresh Jobs'}
          </button>
          {scrapeResult && !scrapeResult.error && (
            <span className="badge badge-green">
              +{scrapeResult.added} jobs from {scrapeResult.sources?.join(', ')}
            </span>
          )}
          {scrapeResult?.error && (
            <span className="badge badge-red">⚠ {scrapeResult.error}</span>
          )}
        </div>
      </div>

      <input
        className="form-input"
        placeholder="Search by title, company or skill…"
        value={search}
        onChange={e => setSearch(e.target.value)}
        style={{marginBottom:'1.25rem', width:'100%'}}
      />

      {filtered.length === 0 && (
        <div className="empty">
          <div className="empty-icon">📭</div>
          <div className="empty-text">No jobs found. Run <code style={{fontFamily:'JetBrains Mono',fontSize:'0.8rem', background:'var(--surface2)',padding:'0.1rem 0.4rem',borderRadius:'4px'}}>make scrape</code> to pull live postings.</div>
        </div>
      )}

      <div style={{display:'flex', flexDirection:'column', gap:'0.75rem'}}>
        {filtered.map(j => (
          <div key={j.id} className="card">
            <div
              style={{display:'flex', alignItems:'flex-start', justifyContent:'space-between', cursor:'pointer'}}
              onClick={() => setExpanded(expanded === j.id ? null : j.id)}
            >
              <div>
                <div style={{fontWeight:700, fontSize:'1rem'}}>{j.title}</div>
                <div style={{fontSize:'0.82rem', color:'var(--muted2)', marginTop:'0.2rem'}}>{j.company}</div>
              </div>
              <div style={{display:'flex', gap:'0.5rem', alignItems:'center', flexShrink:0, marginLeft:'1rem'}}>
                <span className="badge badge-accent">{j.skills.length} skills required</span>
                <span style={{color:'var(--muted)', fontSize:'0.8rem'}}>{expanded === j.id ? '▲' : '▼'}</span>
              </div>
            </div>

            <div className="skill-tags" style={{marginTop:'0.75rem'}}>
              {j.skills.slice(0, expanded === j.id ? undefined : 6).map(s => (
                <span key={s} className={`skill-tag skill-${s.toLowerCase().replace('#','sharp').replace(/\s/g,'-')}`}>{s}</span>
              ))}
              {expanded !== j.id && j.skills.length > 6 && (
                <span className="badge badge-muted">+{j.skills.length - 6} more</span>
              )}
            </div>

            {expanded === j.id && j.description && (
              <div style={{marginTop:'1rem', padding:'0.85rem', background:'rgba(0,0,0,0.2)', borderRadius:'var(--radius-sm)', fontSize:'0.83rem', color:'var(--muted2)', lineHeight:1.6, maxHeight:200, overflowY:'auto'}}>
                {j.description}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
