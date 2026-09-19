import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api';
import CandidateGraph from '../components/CandidateGraph';

function EvidenceSection({ skillName, projectEvidence, expEvidence }) {
  const total = projectEvidence.length + expEvidence.length;
  if (total === 0) return null;

  return (
    <div className="card" style={{marginBottom: '1rem', padding: '1.25rem'}}>
      <div style={{fontWeight: 700, fontSize: '1.1rem', marginBottom: '1rem', color: 'var(--accent)'}}>
        {skillName}
      </div>
      
      {projectEvidence.length > 0 && (
        <div style={{marginBottom: expEvidence.length > 0 ? '1rem' : '0'}}>
          <div style={{fontSize: '0.85rem', color: 'var(--muted2)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem', fontWeight: 600}}>Projects</div>
          <div style={{display: 'flex', flexDirection: 'column', gap: '0.75rem'}}>
            {projectEvidence.map((p, i) => (
              <div key={i} style={{background: 'var(--surface2)', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--border)'}}>
                <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start'}}>
                  <div style={{fontWeight: 600}}>{p.name}</div>
                  {p.url && (
                    <a href={p.url} target="_blank" rel="noreferrer" style={{fontSize: '0.8rem', color: 'var(--accent)', textDecoration: 'none', background: 'rgba(99,102,241,0.1)', padding: '0.15rem 0.5rem', borderRadius: '4px'}}>
                      View on GitHub ↗
                    </a>
                  )}
                </div>
                {p.description && <div style={{fontSize: '0.85rem', color: 'var(--muted)', marginTop: '0.25rem', lineHeight: 1.5}}>{p.description}</div>}
                {p.commits > 0 && <div style={{fontSize: '0.8rem', color: 'var(--muted2)', marginTop: '0.4rem'}}>⚡ {p.commits.toLocaleString()} commits</div>}
              </div>
            ))}
          </div>
        </div>
      )}

      {expEvidence.length > 0 && (
        <div>
          <div style={{fontSize: '0.85rem', color: 'var(--muted2)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem', fontWeight: 600}}>Experience</div>
          <div style={{display: 'flex', flexDirection: 'column', gap: '0.75rem'}}>
            {expEvidence.map((e, i) => (
              <div key={i} style={{background: 'var(--surface2)', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--border)'}}>
                <div style={{fontWeight: 600}}>{e.role} @ {e.company}</div>
                <div style={{fontSize: '0.8rem', color: 'var(--muted2)', marginTop: '0.2rem'}}>{e.duration}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function PublicProfile() {
  const { id } = useParams();
  const [candidate, setCandidate] = useState(null);
  const [evidence, setEvidence] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get('/candidates'),
      api.get(`/evidence/candidate/${id}`)
    ]).then(([cs, ev]) => {
      const cand = cs.find(c => c.id == id);
      setCandidate(cand);
      setEvidence(ev);
      setLoading(false);
    });
  }, [id]);

  if (loading) return <div className="loading" style={{marginTop: '4rem'}}><div className="spinner" /><span>Loading public profile...</span></div>;
  if (!candidate) return <div className="empty" style={{marginTop: '4rem'}}><div className="empty-icon">❓</div><div className="empty-text">Profile not found</div></div>;

  return (
    <div style={{maxWidth: '800px', margin: '0 auto', padding: '2rem 1rem'}}>
      {/* Header Profile Banner */}
      <div style={{textAlign: 'center', marginBottom: '3rem'}}>
        <div style={{
          width: 96, height: 96, borderRadius: '50%', margin: '0 auto 1rem auto',
          background: `linear-gradient(135deg, hsl(${(candidate.id * 60) % 360},70%,55%), hsl(${(candidate.id * 60 + 60) % 360},70%,40%))`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontWeight: 700, fontSize: '2.5rem', color: '#fff',
          boxShadow: '0 8px 16px rgba(0,0,0,0.1)'
        }}>
          {(candidate.name || 'C')[0].toUpperCase()}
        </div>
        <h1 style={{fontSize: '2rem', fontWeight: 800, margin: '0 0 0.5rem 0'}}>{candidate.name || `Candidate #${id}`}</h1>
        {candidate.email && <div style={{color: 'var(--muted)', fontSize: '1rem'}}>{candidate.email}</div>}
        <div style={{marginTop: '1rem'}}>
          <span className="badge badge-accent" style={{fontSize: '0.9rem', padding: '0.4rem 0.8rem'}}>{candidate.skills.length} Verified Skills</span>
        </div>
      </div>

      <div style={{marginBottom: '2rem', textAlign: 'center'}}>
        <h2 style={{fontSize: '1.25rem', fontWeight: 600, color: 'var(--muted)', marginBottom: '1.5rem'}}>Verified Technical Dossier</h2>
        <p style={{fontSize: '0.95rem', color: 'var(--muted2)', maxWidth: '600px', margin: '0 auto', marginBottom: '2rem'}}>
          This profile is generated directly from source code and public commits. Every skill listed below is backed by verifiable project evidence.
        </p>
      </div>

      <div style={{marginBottom: '3rem'}}>
        <CandidateGraph candidate={candidate} evidenceData={evidence} />
      </div>

      <div>
        {evidence?.evidence?.map(e => (
          <EvidenceSection
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
      
      <div style={{textAlign: 'center', marginTop: '3rem', color: 'var(--muted2)', fontSize: '0.85rem'}}>
        Powered by CareerGraph
      </div>
    </div>
  );
}
