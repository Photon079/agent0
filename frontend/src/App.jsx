import { BrowserRouter, Routes, Route, NavLink, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { api } from './api';
import Dashboard from './pages/Dashboard';
import Candidates from './pages/Candidates';
import CandidateDetail from './pages/CandidateDetail';
import Jobs from './pages/Jobs';
import Ingest from './pages/Ingest';
import './App.css';

function Nav() {
  const [backend, setBackend] = useState(null);
  useEffect(() => {
    api.get('/backend').then(setBackend).catch(() => {});
  }, []);

  return (
    <nav className="nav">
      <div className="nav-brand">
        <span className="nav-logo">⬡</span>
        <span className="nav-title">CareerGraph</span>
      </div>
      <div className="nav-links">
        <NavLink to="/" end className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'}>Dashboard</NavLink>
        <NavLink to="/candidates" className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'}>Candidates</NavLink>
        <NavLink to="/jobs" className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'}>Jobs</NavLink>
        <NavLink to="/ingest" className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'}>+ Ingest</NavLink>
      </div>
      <div className="nav-backend">
        {backend && (
          <span className={`badge ${backend.falkordb_available ? 'badge-cyan' : 'badge-muted'}`}>
            {backend.active_backend === 'falkor' ? '⬡ FalkorDB' : '🗄 SQLite'}
          </span>
        )}
      </div>
    </nav>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Nav />
      <main className="main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/candidates" element={<Candidates />} />
          <Route path="/candidates/:id" element={<CandidateDetail />} />
          <Route path="/jobs" element={<Jobs />} />
          <Route path="/ingest" element={<Ingest />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
