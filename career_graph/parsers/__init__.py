"""Parsers package for transforming raw inputs into the parsed dict format
expected by `GraphWriter`.
"""

from .interfaces import Parser
from .simple_resume_parser import SimpleResumeParser
from .github_parser import GithubParser
from .job_parser import JobParser

__all__ = ["Parser", "SimpleResumeParser", "GithubParser", "JobParser"]