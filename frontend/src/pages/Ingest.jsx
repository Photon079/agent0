import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';

export default function Ingest() {
  const [tab, setTab] = useState('candidate');
  const navigate = useNavigate();

  // Unified Candidate tab state
  const [ghUsername, setGhUsername] = useState('');
  const [ghToken, setGhToken] = useState('');
  const [resumeText, setResumeText] = useState('');
  const [resumeFile, setResumeFile] = useState(null);
  const [candLoading, setCandLoading] = useState(false);
  const [candResult, setCandResult] = useState(null);
  const [candError, setCandError] = useState('');

  // Job tab state
  const [jobText, setJobText] = useState('');
  const [jobLoading, setJobLoading] = useState(false);
  const [jobResult, setJobResult] = useState(null);
  const [jobError, setJobError] = useState('');

  const ingestCandidate = async () => {
    if (!ghUsername.trim() && !resumeText.trim()) return;
    setCandLoading(true); setCandResult(null); setCandError('');
    try {
      const fd = new FormData();
      if (ghUsername.trim()) fd.append('github_username', ghUsername.trim());
      if (ghToken.trim()) fd.append('github_token', ghToken.trim());
      if (resumeText.trim()) fd.append('resume_text', resumeText.trim());
      if (resumeFile) fd.append('resume_file', resumeFile);
      
      const data = await api.postForm('/ingest/unified', fd);
      if (data.detail || data.error) throw new Error(data.detail || data.error);
      setCandResult(data);
    } catch (e) {
      setCandError(e.message || 'Ingestion failed');
    }
    setCandLoading(false);
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
      window.dispatchEvent(new CustomEvent('jobs-updated'));
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
        <button className={`tab ${tab === 'candidate' ? 'active' : ''}`} onClick={() => setTab('candidate')}>👤 Candidate Profile</button>
        <button className={`tab ${tab === 'job' ? 'active' : ''}`} onClick={() => setTab('job')}>💼 Job Posting</button>
      </div>

      {/* ── Candidate Profile Tab ── */}
      {tab === 'candidate' && (
        <div className="card">
          <p style={{fontSize:'0.85rem', color:'var(--muted2)', marginBottom:'1.25rem', lineHeight:1.6}}>
            Ingest a complete candidate profile by providing their GitHub username, pasting their Resume, or both. Both sources will be unified into a single graph node.
          </p>
          <div className="form-group">
            <label className="form-label">GitHub Username <span style={{color:'var(--muted)', fontWeight:400}}>(optional)</span></label>
            <input className="form-input" placeholder="e.g. Photon079" value={ghUsername}
              onChange={e => setGhUsername(e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">Resume Text <span style={{color:'var(--muted)', fontWeight:400}}>(optional)</span></label>
            <textarea className="form-textarea" style={{minHeight:140}} placeholder="Paste resume text here…"
              value={resumeText} onChange={e => setResumeText(e.target.value)} />
          </div>
          <div className="form-group" style={{marginTop:'-0.5rem', marginBottom:'1.5rem'}}>
            <div style={{display:'flex', alignItems:'center', gap:'1rem'}}>
              <div style={{flex:1, height:1, background:'var(--border)'}}></div>
              <div style={{fontSize:'0.8rem', color:'var(--muted)'}}>OR</div>
              <div style={{flex:1, height:1, background:'var(--border)'}}></div>
            </div>
            <label className="form-label" style={{marginTop:'0.75rem'}}>Upload Resume PDF <span style={{color:'var(--muted)', fontWeight:400}}>(optional)</span></label>
            <input type="file" accept=".pdf,.txt" className="form-input" onChange={e => setResumeFile(e.target.files[0])} />
          </div>
          <button className="btn btn-primary" onClick={ingestCandidate} disabled={(!ghUsername.trim() && !resumeText.trim() && !resumeFile) || candLoading}>
            {candLoading ? <><span className="spinner" style={{width:14,height:14,borderWidth:2}} />Ingesting profile…</> : '👤 Ingest Candidate Profile'}
          </button>

          {candError && <div className="alert alert-error" style={{marginTop:'1rem'}}>⚠ {candError}</div>}
          {candResult && (
            <div className="alert alert-success" style={{marginTop:'1rem'}}>
              <div style={{fontWeight:600, marginBottom:'0.5rem'}}>
                ✅ Ingested <strong>{candResult.name}</strong> — candidate #{candResult.candidate_id}
              </div>
              <button className="btn btn-secondary" style={{marginTop:'0.75rem'}}
                onClick={() => navigate(`/candidates/${candResult.candidate_id}`)}>
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
