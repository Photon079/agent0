import React, { useRef, useMemo, useEffect, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

export default function CandidateGraph({ candidate, evidenceData }) {
  const fgRef = useRef();
  const [dimensions, setDimensions] = useState({ width: 800, height: 500 });
  const containerRef = useRef();

  useEffect(() => {
    if (containerRef.current) {
      setDimensions({
        width: containerRef.current.clientWidth,
        height: 500
      });
    }
    const handleResize = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth,
          height: 500
        });
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const { nodes, links } = useMemo(() => {
    if (!candidate || !evidenceData?.evidence) return { nodes: [], links: [] };

    const nodesMap = new Map();
    const links = [];

    // Root node (Candidate)
    const rootId = `cand_${candidate.id}`;
    nodesMap.set(rootId, {
      id: rootId,
      name: candidate.name || 'Candidate',
      group: 'candidate',
      val: 25
    });

    // Process skills and their evidence
    evidenceData.evidence.forEach(e => {
      const skillId = `skill_${e.skill}`;
      
      // Skill Node
      if (!nodesMap.has(skillId)) {
        nodesMap.set(skillId, {
          id: skillId,
          name: e.skill,
          group: 'skill',
          val: 12
        });
        // Link Candidate -> Skill
        links.push({ source: rootId, target: skillId });
      }

      // Projects
      e.project_evidence.forEach(p => {
        const projId = `proj_${p.name}`;
        if (!nodesMap.has(projId)) {
          nodesMap.set(projId, {
            id: projId,
            name: p.name,
            group: 'project',
            url: p.url,
            val: 8
          });
        }
        // Link Skill -> Project
        links.push({ source: skillId, target: projId });
      });

      // Experience
      e.experience_evidence.forEach(exp => {
        const expId = `exp_${exp.company}_${exp.role}`;
        if (!nodesMap.has(expId)) {
          nodesMap.set(expId, {
            id: expId,
            name: `${exp.role} @ ${exp.company}`,
            group: 'experience',
            val: 8
          });
        }
        // Link Skill -> Experience
        links.push({ source: skillId, target: expId });
      });
    });

    return {
      nodes: Array.from(nodesMap.values()),
      links
    };
  }, [candidate, evidenceData]);

  const handleNodeClick = (node) => {
    if (node.url) {
      window.open(node.url, '_blank');
    }
  };

  return (
    <div ref={containerRef} style={{ width: '100%', height: '500px', background: 'var(--surface-bg)', borderRadius: '12px', border: '1px solid var(--border)', overflow: 'hidden' }}>
      <ForceGraph2D
        ref={fgRef}
        width={dimensions.width}
        height={dimensions.height}
        graphData={{ nodes, links }}
        nodeLabel="name"
        nodeColor={node => {
          if (node.group === 'candidate') return '#6366f1';
          if (node.group === 'skill') return '#22d3ee';
          if (node.group === 'project') return '#f59e0b';
          if (node.group === 'experience') return '#10b981';
          return '#94a3b8';
        }}
        linkColor={() => 'rgba(148, 163, 184, 0.3)'}
        nodeCanvasObject={(node, ctx, globalScale) => {
          const label = node.name;
          const fontSize = 12/globalScale;
          ctx.font = `${fontSize}px Sans-Serif`;
          
          // Draw circle
          ctx.beginPath();
          ctx.arc(node.x, node.y, node.val, 0, 2 * Math.PI, false);
          ctx.fillStyle = node.group === 'candidate' ? '#6366f1' : 
                          node.group === 'skill' ? '#22d3ee' : 
                          node.group === 'project' ? '#f59e0b' : '#10b981';
          ctx.fill();
          
          // Draw outline for links
          if (node.url) {
            ctx.lineWidth = 2/globalScale;
            ctx.strokeStyle = '#fff';
            ctx.stroke();
          }

          // Draw text label
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillStyle = 'var(--text)';
          ctx.fillText(label, node.x, node.y + node.val + (8/globalScale));
        }}
        onNodeClick={handleNodeClick}
        cooldownTicks={100}
        onEngineStop={() => fgRef.current?.zoomToFit(400, 50)}
      />
    </div>
  );
}
