"""Prompt templates using Jinja2."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

PROMPTS_DIR = Path(__file__).parent
_env = Environment(loader=FileSystemLoader(PROMPTS_DIR))


def render_code_review_prompt(
    filename: str,
    patch: str,
    pr_title: str,
    pr_description: str | None,
    additions: int,
    deletions: int,
) -> str:
    """Render the code review prompt."""
    template = _env.get_template("code_review.jinja2")
    return template.render(
        filename=filename,
        patch=patch,
        pr_title=pr_title,
        pr_description=pr_description,
        additions=additions,
        deletions=deletions,
    )


def render_review_summary_prompt(file_reviews: str) -> str:
    """Render the review summary prompt."""
    template = _env.get_template("review_summary.jinja2")
    return template.render(file_reviews=file_reviews)


def render_review_system_prompt() -> str:
    """Render the review system prompt."""
    template = _env.get_template("review_system.jinja2")
    return template.render()


def render_summary_system_prompt() -> str:
    """Render the summary system prompt."""
    template = _env.get_template("summary_system.jinja2")
    return template.render()


def render_file_review_prompt(
    pr_title: str,
    pr_description: str | None,
    filename: str,
    additions: int,
    deletions: int,
    patch: str,
) -> str:
    """Render the file review prompt for a specific file."""
    template = _env.get_template("file_review.jinja2")
    return template.render(
        pr_title=pr_title,
        pr_description=pr_description,
        filename=filename,
        additions=additions,
        deletions=deletions,
        patch=patch,
    )


def render_generate_summary_prompt(file_summaries: list[str]) -> str:
    """Render the generate summary prompt."""
    template = _env.get_template("generate_summary.jinja2")
    return template.render(file_summaries=file_summaries)
