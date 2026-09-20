"""Resume Tailoring Pipeline Orchestrator — End-to-End Pipeline Coordinator.

Connects all 5 phases of the Graph-Grounded Resume Tailoring Pipeline:
1. Evidence Retrieval
2. ResumeContext Assembly
3. Resume Tailoring (Bedrock LLM / Deterministic Fallback)
4. Grounding Validation
5. LaTeX Rendering & PDF Compilation
"""

import os
import logging
from typing import Dict, Any, Optional

from .evidence_retrieval import EvidenceRetrievalService
from .resume_context import ResumeContextBuilder
from .tailoring_agent import ResumeTailoringAgent
from .grounding_validator import GroundingValidator
from .latex_renderer import LatexRenderer

logger = logging.getLogger(__name__)


class ResumePipelineOrchestrator:
    """Orchestrates end-to-end resume tailoring from JD + Candidate Graph to LaTeX/PDF."""

    def __init__(self, db_path: Optional[str] = None):
        self.evidence_service = EvidenceRetrievalService(db_path=db_path)
        self.context_builder = ResumeContextBuilder()
        self.tailoring_agent = ResumeTailoringAgent()
        self.validator = GroundingValidator()
        self.latex_renderer = LatexRenderer()

    def run_pipeline(
        self,
        candidate_data: Dict[str, Any],
        job_description: Dict[str, Any],
        matching_results: Optional[Dict[str, Any]] = None,
        output_dir: str = "output",
        output_filename: str = "tailored_resume"
    ) -> Dict[str, Any]:
        """Execute the complete resume tailoring pipeline.

        Args:
            candidate_data: Dict containing candidate resume info, profile, or skills.
            job_description: Dict containing structured JD analysis (from existing Job Analyzer).
            matching_results: Optional existing skill matching breakdown (matched/missing skills).
            output_dir: Output directory for generated .tex and .pdf files.
            output_filename: Base filename for output files.

        Returns:
            Dict containing:
                - resume_json: Grounded & tailored resume JSON structure
                - resume_context: The ResumeContext dict passed to the LLM agent
                - evidence_summary: Summary of graph evidence retrieved per skill
                - validation: Grounding validation report (score, ungrounded claims)
                - latex_code: Rendered LaTeX source string
                - tex_file: Path to saved .tex file
                - pdf_file: Path to compiled PDF file (if compiler installed, else None)
                - status: "SUCCESS" or "WARNING"
                - message: Status message
        """
        logger.info(f"Starting Resume Tailoring Pipeline for job: {job_description.get('title', 'Unknown Job')}")

        # --- Phase 1: Retrieve Graph Evidence ---
        matched_skills = []
        if matching_results and "matched_skills" in matching_results:
            matched_skills = [
                s.get("name", s) if isinstance(s, dict) else str(s)
                for s in matching_results.get("matched_skills", [])
            ]
        else:
            # Fallback to skills in JD if no matching_results explicitly provided
            jd_skills = job_description.get("required_skills", [])
            matched_skills = [
                s.get("name", s) if isinstance(s, dict) else str(s)
                for s in jd_skills
            ]

        evidence_report = self.evidence_service.retrieve_evidence_for_skills(matched_skills)
        logger.info(f"Phase 1 Complete: Retrieved evidence for {len(matched_skills)} matched skills.")

        # --- Phase 2: Build ResumeContext ---
        resume_context = self.context_builder.build_context(
            candidate_data=candidate_data,
            job_description=job_description,
            matching_results=matching_results,
            evidence_report=evidence_report
        )
        logger.info("Phase 2 Complete: Built grounded ResumeContext.")

        # --- Phase 3: Resume Tailoring Agent ---
        resume_json = self.tailoring_agent.generate_tailored_resume(resume_context)
        logger.info("Phase 3 Complete: Tailored resume JSON generated.")

        # --- Phase 4: Grounding Validation ---
        validation_report = self.validator.validate(resume_json, resume_context)
        logger.info(
            f"Phase 4 Complete: Validation score: {validation_report.get('grounding_score', 0):.2f} "
            f"(Valid: {validation_report.get('is_valid')})"
        )

        # --- Phase 5: LaTeX Rendering & Compilation ---
        tex_code = self.latex_renderer.render_tex(resume_json)
        tex_file, pdf_file, compile_msg = self.latex_renderer.compile_pdf(
            tex_code=tex_code,
            output_dir=output_dir,
            filename=output_filename
        )
        logger.info(f"Phase 5 Complete: Rendered LaTeX. PDF: {pdf_file}")

        # Assemble final result
        result = {
            "status": "SUCCESS" if validation_report.get("is_valid") else "WARNING",
            "resume_json": resume_json,
            "resume_context": resume_context,
            "evidence_summary": {
                "matched_skills_count": len(matched_skills),
                "skills_with_evidence": len([k for k, v in evidence_report.items() if v.get("evidence")]),
            },
            "validation": validation_report,
            "latex_code": tex_code,
            "tex_file": tex_file,
            "pdf_file": pdf_file,
            "compilation_message": compile_msg,
        }

        return result
