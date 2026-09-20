import { useState } from "react";
import { WebcamPixelGrid } from "@/components/ui/webcam-pixel-grid";
import ScrambledTitle from "@/components/ui/modern-animated-text-scramble";
import { LiquidMetalButton } from "@/components/ui/liquid-metal-button";
import { KnowledgeGraphPage } from "@/components/ui/knowledge-graph-page";

export function App() {
  const [githubUrl, setGithubUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");
  const [candidateId, setCandidateId] = useState<number>(0);
  const [candidateName, setCandidateName] = useState<string>("");
  const [ingestedUsername, setIngestedUsername] = useState<string>("");

  const handleIngest = async () => {
    if (!githubUrl) return;
    setLoading(true);
    setError("");

    // Extract username from URL or just use the input if it's already a username
    const username = githubUrl.replace('https://github.com/', '').replace('/', '').trim();

    try {
      const res = await fetch("http://localhost:8000/ingest/github", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: username,
          max_repos: 100,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Ingestion failed");
      }

      // Capture candidate details returned by the ingest endpoint
      setCandidateId(data.candidate_id ?? 0);
      setCandidateName(data.name ?? username);
      setIngestedUsername(username);
      setSuccess(true);
    } catch (err: any) {
      setError(err.message || "An error occurred during ingestion");
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <KnowledgeGraphPage
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

            <div className="mt-2">
              <LiquidMetalButton
                label={loading ? "Ingesting..." : "Ingest Profile"}
                onClick={handleIngest}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
