import { useState, useRef } from "react";
import { WebcamPixelGrid } from "@/components/ui/webcam-pixel-grid";
import ScrambledTitle from "@/components/ui/modern-animated-text-scramble";
import { LiquidMetalButton } from "@/components/ui/liquid-metal-button";
import { KnowledgeGraphReferencePage } from "@/components/ui/knowledge-graph-reference-page";
import { Dashboard } from "@/components/ui/dashboard";
export function App() {
  const [githubUrl, setGithubUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");
  const [candidateId, setCandidateId] = useState<number>(0);
  const [candidateName, setCandidateName] = useState<string>("");
  const [ingestedUsername, setIngestedUsername] = useState<string>("");
  const [viewingDashboard, setViewingDashboard] = useState(false);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleResumeSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setResumeFile(file);
      setError("");
    }
  };

  const handleIngest = async () => {
    if (!githubUrl && !resumeFile) {
      setError("Please provide a GitHub URL/Username or a Resume");
      return;
    }
    
    setLoading(true);
    setError("");

    const formData = new FormData();
    if (githubUrl) {
      const username = githubUrl.replace('https://github.com/', '').replace('/', '').trim();
      formData.append("github_username", username);
      setIngestedUsername(username); // Store tentatively
    }
    if (resumeFile) {
      formData.append("resume_file", resumeFile);
    }

    try {
      const res = await fetch("http://localhost:8000/ingest/unified", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || data.error || "Ingestion failed");
      }

      setCandidateId(data.candidate_id ?? 0);
      setCandidateName(data.name ?? ingestedUsername);
      if (!githubUrl && data.name) {
        setIngestedUsername(data.name);
      }
      setSuccess(true);
    } catch (err: any) {
      setError(err.message || "An error occurred during ingestion");
    } finally {
      setLoading(false);
    }
  };

  if (viewingDashboard) {
    return (
      <Dashboard 
        onSelectCandidate={(id, name) => {
          setCandidateId(id);
          setCandidateName(name);
          setIngestedUsername(name);
          setSuccess(true);
          setViewingDashboard(false);
        }}
        onBack={() => setViewingDashboard(false)}
      />
    );
  }

  if (success) {
    return (
      <KnowledgeGraphReferencePage
        candidateId={candidateId}
        candidateName={candidateName || ingestedUsername}
        username={ingestedUsername}
        onGoBack={() => {
          setSuccess(false);
          setGithubUrl("");
          setError("");
        }}
      />
    );
  }

  return (
    <div className="relative h-screen w-screen bg-black overflow-hidden">
      {/* Webcam pixel grid background */}
      <div className="absolute inset-0">
        <WebcamPixelGrid
          gridCols={60}
          gridRows={40}
          maxElevation={50}
          motionSensitivity={0.25}
          elevationSmoothing={0.2}
          colorMode="webcam"
          backgroundColor="#030303"
          mirror={true}
          gapRatio={0.05}
          invertColors={false}
          darken={0.6}
          borderColor="#ffffff"
          borderOpacity={0.06}
          className="w-full h-full"
        />
      </div>

      {/* Gradient overlay for better text readability */}
      <div className="absolute inset-0 bg-gradient-to-b from-black/40 via-transparent to-black/60 pointer-events-none" />

      {/* Hero content */}
      <div className="relative z-10 flex h-full flex-col items-center justify-center px-4">
        <div className="max-w-4xl text-center w-full">
          {/* Title */}
          <div className="mb-6">
            <ScrambledTitle />
          </div>

          {/* Description */}
          <p className="mx-auto mb-10 max-w-2xl text-base text-white/60 sm:text-xl">
            Precision meets potential. We turn every commit and project into traceable evidence, structurally matching your verified skills to the jobs you were built for
          </p>

          {/* Ingest Form */}
          <div className="flex flex-col items-center justify-center gap-4 w-full max-w-md mx-auto">
            <input
              type="text"
              placeholder="Enter GitHub Profile URL or Username"
              className="w-full h-12 px-4 rounded-full bg-white/5 border border-white/20 text-white placeholder:text-white/40 focus:outline-none focus:border-white/50 backdrop-blur-sm transition-all text-center"
              value={githubUrl}
              onChange={(e) => setGithubUrl(e.target.value)}
              disabled={loading}
              onKeyDown={(e) => e.key === 'Enter' && handleIngest()}
            />

            {error && <p className="text-red-400 text-sm mt-1">{error}</p>}

            <div className="mt-2 flex flex-col sm:flex-row gap-4 w-full">
              <div className="flex-1">
                <LiquidMetalButton
                  label={loading ? "Ingesting..." : "Ingest Profile"}
                  onClick={handleIngest}
                />
              </div>
              <div className="flex-1">
                <input
                  type="file"
                  accept=".pdf,.txt"
                  style={{ display: "none" }}
                  ref={fileInputRef}
                  onChange={handleResumeSelect}
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={loading}
                  className="w-full h-12 rounded-full border border-emerald-500/30 text-emerald-400 bg-emerald-950/20 hover:bg-emerald-900/40 transition-colors font-mono text-[10px] uppercase tracking-widest cursor-pointer disabled:opacity-50 flex items-center justify-center truncate px-2"
                  style={{backdropFilter: "blur(4px)"}}
                  title={resumeFile?.name || "Attach Optional Resume"}
                >
                  {resumeFile ? `Selected: ${resumeFile.name}` : "+ Attach Resume"}
                </button>
              </div>
            </div>
            
            <button
              onClick={() => setViewingDashboard(true)}
              className="mt-6 text-emerald-400/60 hover:text-emerald-400 text-[10px] uppercase tracking-widest transition-colors font-mono"
            >
              View Previous Candidates →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
