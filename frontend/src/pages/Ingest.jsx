import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';

export default function Ingest() {
  const [tab, setTab] = useState('github');
  const navigate = useNavigate();

  // GitHub tab state
  const [ghUsername, setGhUsername] = useState('');
  const [ghToken, setGhToken] = useState('');
  const [ghLoading, setGhLoading] = useState(false);
  const [ghResult, setGhResult] = useState(null);
  const [ghError, setGhError] = useState('');

  // Resume tab state
  const [resumeText, setResumeText] = useState('');
  const [resumeLoading, setResumeLoading] = useState(false);
  const [resumeResult, setResumeResult] = useState(null);
  const [resumeError, setResumeError] = useState('');

  // Job tab state
  const [jobText, setJobText] = useState('');
  const [jobLoading, setJobLoading] = useState(false);
  const [jobResult, setJobResult] = useState(null);
  const [jobError, setJobError] = useState('');

  const ingestGithub = async () => {
    if (!ghUsername.trim()) return;
    setGhLoading(true); setGhResult(null); setGhError('');
    try {
      const data = await api.post('/ingest/github', {
        username: ghUsername.trim(),
        token: ghToken.trim() || undefined,
        max_repos: 100,
      });
      if (data.detail) throw new Error(data.detail);
      setGhResult(data);
    } catch (e) {
      setGhError(e.message || 'Ingestion failed');
    }
    setGhLoading(false);
  };

  const ingestResume = async () => {
    if (!resumeText.trim()) return;
    setResumeLoading(true); setResumeResult(null); setResumeError('');
    try {
      const fd = new FormData();
      fd.append('text', resumeText);
      const data = await api.postForm('/parse/resume', fd);
      if (data.detail) throw new Error(data.detail);
      setResumeResult(data);
    } catch (e) {
      setResumeError(e.message || 'Parse failed');
    }
    setResumeLoading(false);
  };

  const ingestJob = async () => {
    if (!jobText.trim()) return;
    setJobLoading(true); setJobResult(null); setJobError('');
    try {
      const fd = new FormData();
      fd.append('text', jobText);
      const data = await api.postForm('/parse/job', fd);
      if (data.detail) throw new Error(data.detail);
      setJobResult(data);
    } catch (e) {
      setJobError(e.message || 'Parse failed');
    }
    setJobLoading(false);
  };

  return (
    <div style={{maxWidth:640}}>
      <div className="page-header">
        <h1 className="page-title">Ingest</h1>
        <p className="page-sub">Add candidates and job postings to the knowledge graph</p>
      </div>

      <div className="tabs">
        <button className={`tab ${tab === 'github' ? 'active' : ''}`} onClick={() => setTab('github')}>⬡ GitHub</button>
        <button className={`tab ${tab === 'resume' ? 'active' : ''}`} onClick={() => setTab('resume')}>📄 Resume</button>
        <button className={`tab ${tab === 'job' ? 'active' : ''}`} onClick={() => setTab('job')}>💼 Job Posting</button>
      </div>

      {/* ── GitHub Tab ── */}
      {tab === 'github' && (
        <div className="card">
          <p style={{fontSize:'0.85rem', color:'var(--muted2)', marginBottom:'1.25rem', lineHeight:1.6}}>
            Fetches all public repos, extracts languages and commit counts, and writes the candidate into the graph.
          </p>
          <div className="form-group">
            <label className="form-label">GitHub Username</label>
            <input className="form-input" placeholder="e.g. Photon079" value={ghUsername}
              onChange={e => setGhUsername(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && ingestGithub()} />
          </div>
          <div className="form-group">
            <label className="form-label">Personal Access Token <span style={{color:'var(--muted)', fontWeight:400}}>(optional — 5000 req/hr vs 60)</span></label>
            <input className="form-input" placeholder="ghp_…" type="password" value={ghToken}
              onChange={e => setGhToken(e.target.value)} />
          </div>
          <button className="btn btn-primary" onClick={ingestGithub} disabled={!ghUsername.trim() || ghLoading}>
            {ghLoading ? <><span className="spinner" style={{width:14,height:14,borderWidth:2}} />Ingesting repos…</> : '⬡ Ingest GitHub Profile'}
          </button>

          {ghError && <div className="alert alert-error" style={{marginTop:'1rem'}}>⚠ {ghError}</div>}
          {ghResult && (
            <div className="alert alert-success" style={{marginTop:'1rem'}}>
              <div style={{fontWeight:600, marginBottom:'0.5rem'}}>
                ✅ Ingested <strong>{ghResult.name}</strong> — candidate #{ghResult.candidate_id}
              </div>
              <div style={{fontSize:'0.82rem', marginBottom:'0.5rem'}}>
                {ghResult.project_count} repos · {ghResult.skills.length} skills detected
              </div>
              <div className="skill-tags">
                {ghResult.skills.map(s => <span key={s} className={`skill-tag skill-${s.toLowerCase().replace('#','sharp')}`}>{s}</span>)}
              </div>
              <button className="btn btn-secondary" style={{marginTop:'0.75rem'}}
                onClick={() => navigate(`/candidates/${ghResult.candidate_id}`)}>
                View Candidate →
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── Resume Tab ── */}
      {tab === 'resume' && (
        <div className="card">
          <p style={{fontSize:'0.85rem', color:'var(--muted2)', marginBottom:'1.25rem', lineHeight:1.6}}>
            Paste resume text. The parser extracts skills and experience nodes into the graph.
            Enable <code style={{fontFamily:'JetBrains Mono',fontSize:'0.8rem', background:'var(--surface2)',padding:'0.1rem 0.4rem',borderRadius:'4px'}}>CAREER_GRAPH_USE_BEDROCK=1</code> for Claude-powered extraction.
          </p>
          <div className="form-group">
            <label className="form-label">Resume Text</label>
            <textarea className="form-textarea" style={{minHeight:220}} placeholder="Paste resume text here…"
              value={resumeText} onChange={e => setResumeText(e.target.value)} />
          </div>
          <button className="btn btn-primary" onClick={ingestResume} disabled={!resumeText.trim() || resumeLoading}>
            {resumeLoading ? <><span className="spinner" style={{width:14,height:14,borderWidth:2}} />Parsing…</> : '📄 Parse Resume'}
          </button>

          {resumeError && <div className="alert alert-error" style={{marginTop:'1rem'}}>⚠ {resumeError}</div>}
          {resumeResult && (
            <div className="alert alert-success" style={{marginTop:'1rem'}}>
              <div style={{fontWeight:600, marginBottom:'0.4rem'}}>✅ Parsed — candidate #{resumeResult.candidate_id}</div>
              <div style={{fontSize:'0.82rem', color:'var(--green)'}}>Name: {resumeResult.name}</div>
              <button className="btn btn-secondary" style={{marginTop:'0.75rem'}}
                onClick={() => navigate(`/candidates/${resumeResult.candidate_id}`)}>
                View Candidate →
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── Job Tab ── */}
      {tab === 'job' && (
        <div className="card">
          <p style={{fontSize:'0.85rem', color:'var(--muted2)', marginBottom:'1.25rem', lineHeight:1.6}}>
            Paste a job description. The parser extracts required skills and writes the job posting into the graph so candidates can be matched against it.
          </p>
          <div className="form-group">
            <label className="form-label">Job Description</label>
            <textarea className="form-textarea" style={{minHeight:220}} placeholder="Paste job description text here…"
              value={jobText} onChange={e => setJobText(e.target.value)} />
          </div>
          <button className="btn btn-primary" onClick={ingestJob} disabled={!jobText.trim() || jobLoading}>
            {jobLoading ? <><span className="spinner" style={{width:14,height:14,borderWidth:2}} />Parsing…</> : '💼 Add Job Posting'}
          </button>

          {jobError && <div className="alert alert-error" style={{marginTop:'1rem'}}>⚠ {jobError}</div>}
          {jobResult && (
            <div className="alert alert-success" style={{marginTop:'1rem'}}>
              <div style={{fontWeight:600, marginBottom:'0.4rem'}}>✅ Job added — #{jobResult.job_id}</div>
              <div style={{fontSize:'0.82rem', color:'var(--green)'}}>"{jobResult.title}"</div>
              <button className="btn btn-secondary" style={{marginTop:'0.75rem'}} onClick={() => navigate('/jobs')}>
                View All Jobs →
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
