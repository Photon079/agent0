"""LaTeX Renderer & PDF Compiler — Phase 5 of the Resume Tailoring Pipeline.

Renders structured, grounded resume JSON into clean, compilation-ready LaTeX source code
using Jinja2 template formatting and proper LaTeX special character escaping.
Compiles to PDF via pdflatex if available; safely falls back to returning source .tex.
"""

import os
import re
import shutil
import subprocess
import logging
from typing import Dict, Any, Tuple, Optional
from jinja2 import Environment, FunctionLoader

logger = logging.getLogger(__name__)


LATEX_SPECIAL_CHARS = {
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "\\": r"\textbackslash{}",
}


def escape_latex(text: Any) -> str:
    """Safely escape special LaTeX characters in strings."""
    if not isinstance(text, str):
        return str(text) if text is not None else ""
    
    # Do not escape if string already contains raw LaTeX commands like \textbf
    if "\\" in text and ("{" in text or "}" in text):
        return text

    pattern = re.compile("|".join(re.escape(k) for k in LATEX_SPECIAL_CHARS.keys()))
    return pattern.sub(lambda m: LATEX_SPECIAL_CHARS[m.group(0)], text)


# Embedded LaTeX Jinja2 Template (Modern CV / Clean Professional Style)
DEFAULT_RESUME_TEX_TEMPLATE = r"""
\documentclass[10pt, letterpaper]{article}

% Packages
\usepackage[utf8]{utf8}
\usepackage[margin=0.6in]{geometry}
\usepackage{hyperref}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage{xcolor}

% Color Definitions
\definecolor{primary}{RGB}{30, 41, 59}
\definecolor{accent}{RGB}{37, 99, 235}
\definecolor{darkgray}{RGB}{71, 85, 105}

% Hyperlink styling
\hypersetup{
    colorlinks=true,
    linkcolor=accent,
    urlcolor=accent,
}

% Formatting
\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlist[itemize]{leftmargin=1.5em, itemsep=2pt, parsep=0pt, topsep=2pt}

% Custom section headings
\titleformat{\section}{\color{primary}\large\bfseries\uppercase}{}{0em}{}[\titlerule]
\titlespacing*{\section}{0pt}{10pt}{6pt}

\begin{document}

% --- HEADER ---
\begin{center}
    {\huge \bfseries \color{primary} {{ name | escape_latex }}} \\[4pt]
    \small \color{darkgray}
    {% if contact.phone %}{{ contact.phone | escape_latex }} \quad $\cdot$ \quad {% endif %}
    {% if contact.email %}\href{mailto:{{ contact.email }}}{ {{ contact.email | escape_latex }} } \quad $\cdot$ \quad {% endif %}
    {% if contact.linkedin %}\href{https://{{ contact.linkedin }}}{ {{ contact.linkedin | escape_latex }} } \quad $\cdot$ \quad {% endif %}
    {% if contact.github %}\href{https://{{ contact.github }}}{ {{ contact.github | escape_latex }} } \quad $\cdot$ \quad {% endif %}
    {% if contact.location %}{{ contact.location | escape_latex }}{% endif %}
\end{center}

{% if summary %}
% --- PROFESSIONAL SUMMARY ---
\section{Professional Summary}
{{ summary | escape_latex }}
{% endif %}

{% if skills %}
% --- SKILLS ---
\section{Technical Skills}
\begin{description}[leftmargin=0pt, labelindent=0pt, itemsep=2pt]
{% for cat in skills %}
    \item[\textbf{ {{ cat.category | escape_latex }}:}] {{ cat.items | join(', ') | escape_latex }}
{% endfor %}
\end{description}
{% endif %}

{% if experience %}
% --- EXPERIENCE ---
\section{Work Experience}
{% for exp in experience %}
    \textbf{\color{primary} {{ exp.title | escape_latex }}} \hfill \textbf{ {{ exp.dates | escape_latex }} } \\
    \textit{\color{darkgray} {{ exp.company | escape_latex }} {% if exp.location %} $\cdot$ {{ exp.location | escape_latex }}{% endif %}}
    {% if exp.bullets %}
    \begin{itemize}
    {% for bullet in exp.bullets %}
        \item {{ bullet | escape_latex }}
    {% endfor %}
    \end{itemize}
    {% endif %}
    \vspace{4pt}
{% endfor %}
{% endif %}

{% if projects %}
% --- PROJECTS ---
\section{Projects}
{% for proj in projects %}
    \textbf{\color{primary} {{ proj.name | escape_latex }}} {% if proj.tech %} \hfill \small \textit{Technologies: {{ proj.tech | join(', ') | escape_latex }}}{% endif %} \\
    {% if proj.description %}\textit{\small \color{darkgray} {{ proj.description | escape_latex }}}{% endif %}
    {% if proj.bullets %}
    \begin{itemize}
    {% for bullet in proj.bullets %}
        \item {{ bullet | escape_latex }}
    {% endfor %}
    \end{itemize}
    {% endif %}
    \vspace{4pt}
{% endfor %}
{% endif %}

{% if education %}
% --- EDUCATION ---
\section{Education}
{% for edu in education %}
    \textbf{\color{primary} {{ edu.degree | escape_latex }}} \hfill \textbf{ {{ edu.dates | escape_latex }} } \\
    \textit{\color{darkgray} {{ edu.institution | escape_latex }} {% if edu.gpa %} $\cdot$ GPA: {{ edu.gpa | escape_latex }}{% endif %}} \\
    \vspace{2pt}
{% endfor %}
{% endif %}

\end{document}
"""


class LatexRenderer:
    """Renders structured resume JSON into compilation-ready LaTeX and optionally compiles to PDF."""

    def __init__(self, template_str: Optional[str] = None):
        self.template_str = template_str or DEFAULT_RESUME_TEX_TEMPLATE
        
        # Configure Jinja2 Environment for LaTeX (using custom delimiters to avoid clash with LaTeX {})
        self.env = Environment(
            block_start_string='{%',
            block_end_string='%}',
            variable_start_string='{{',
            variable_end_string='}}',
            comment_start_string='{#',
            comment_end_string='#}',
            autoescape=False
        )
        self.env.filters['escape_latex'] = escape_latex
        self.template = self.env.from_string(self.template_str)

    def render_tex(self, resume_json: Dict[str, Any]) -> str:
        """Render structured resume JSON to raw LaTeX string."""
        # Pre-process skills if formatted as list of dicts with single key
        skills_formatted = []
        raw_skills = resume_json.get("skills", [])
        if isinstance(raw_skills, list):
            for s in raw_skills:
                if isinstance(s, dict):
                    if "category" in s and "items" in s:
                        skills_formatted.append(s)
                    else:
                        for k, v in s.items():
                            items_list = v if isinstance(v, list) else [v]
                            skills_formatted.append({"category": k, "items": items_list})
                elif isinstance(s, str):
                    skills_formatted.append({"category": "General", "items": [s]})

        # Ensure contact dict exists
        contact = resume_json.get("contact", {})

        render_ctx = {
            "name": resume_json.get("name", "Candidate"),
            "contact": contact,
            "summary": resume_json.get("summary", ""),
            "skills": skills_formatted,
            "experience": resume_json.get("experience", []),
            "projects": resume_json.get("projects", []),
            "education": resume_json.get("education", []),
        }

        rendered_tex = self.template.render(**render_ctx)
        return rendered_tex

    def compile_pdf(self, tex_code: str, output_dir: str = "output", filename: str = "tailored_resume") -> Tuple[str, Optional[str], Optional[str]]:
        """Write tex_code to file and compile to PDF if pdflatex is present.

        Returns:
            Tuple[tex_filepath, pdf_filepath_or_none, error_message_or_none]
        """
        os.makedirs(output_dir, exist_ok=True)
        tex_file = os.path.join(output_dir, f"{filename}.tex")
        pdf_file = os.path.join(output_dir, f"{filename}.pdf")

        # Save .tex file
        with open(tex_file, "w", encoding="utf-8") as f:
            f.write(tex_code)

        # Check for pdflatex or xelatex executable
        compiler = shutil.which("pdflatex") or shutil.which("xelatex")
        if not compiler:
            logger.warning("pdflatex/xelatex command not found on system. Returning .tex file only.")
            return tex_file, None, "LaTeX compiler (pdflatex) not found on system environment. Generated .tex source code successfully."

        try:
            cmd = [compiler, "-interaction=nonstopmode", f"-output-directory={output_dir}", tex_file]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            
            if res.returncode == 0 and os.path.exists(pdf_file):
                logger.info(f"Successfully compiled PDF: {pdf_file}")
                return tex_file, pdf_file, None
            else:
                err_log = res.stdout[-500:] if res.stdout else res.stderr
                logger.error(f"LaTeX compilation failed: {err_log}")
                return tex_file, None, f"LaTeX compilation warning/error: {err_log}"
        except Exception as e:
            logger.error(f"Failed to execute LaTeX compiler: {e}")
            return tex_file, None, f"Failed to execute pdflatex: {str(e)}"
