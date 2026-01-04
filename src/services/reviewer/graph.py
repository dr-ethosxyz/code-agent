"""LangGraph agent for code review with parallel file processing."""

import asyncio
import json
from dataclasses import dataclass

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.config import settings
from src.core.llm import get_chat_llm
from src.core.logging import get_logger
from src.core.prompts import (
    render_file_review_prompt,
    render_generate_summary_prompt,
    render_review_system_prompt,
    render_summary_system_prompt,
)
from src.services.reviewer.tools import create_github_tools

logger = get_logger("reviewer.graph")

MAX_TOOL_ITERATIONS = 5  # Max tool calls per file


@dataclass
class FileReviewResult:
    """Result of reviewing a single file."""

    filename: str
    comments: list[dict]
    summary: str


async def review_single_file(
    file: dict,
    pr_title: str,
    pr_description: str | None,
    owner: str,
    repo: str,
    head_ref: str,
) -> FileReviewResult:
    """Review a single file with tool calling support.

    This function handles the complete review of one file,
    including multiple tool call iterations if needed.
    """
    filename = file["filename"]
    logger.info(f"Starting review: {filename}")

    # Create tools and LLM for this file
    tools = create_github_tools(owner, repo, head_ref)
    llm = get_chat_llm(model=settings.review_model)
    llm_with_tools = llm.bind_tools(tools)

    # Build tool map for execution
    tool_map = {tool.name: tool for tool in tools}

    # Initial prompt
    prompt = render_file_review_prompt(
        pr_title=pr_title,
        pr_description=pr_description,
        filename=filename,
        additions=file["additions"],
        deletions=file["deletions"],
        patch=file["patch"],
    )

    messages = [
        SystemMessage(content=render_review_system_prompt()),
        HumanMessage(content=prompt),
    ]

    # Tool calling loop
    for iteration in range(MAX_TOOL_ITERATIONS):
        response = await llm_with_tools.ainvoke(messages)
        messages.append(response)

        # Check if LLM wants to use tools
        if isinstance(response, AIMessage) and response.tool_calls:
            logger.info(
                f"[{filename}] Tool calls: {[t['name'] for t in response.tool_calls]}"
            )

            # Execute all tool calls
            tool_results = []
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]

                if tool_name in tool_map:
                    try:
                        result = tool_map[tool_name].invoke(tool_args)
                    except Exception as e:
                        result = f"Error: {e}"
                else:
                    result = f"Unknown tool: {tool_name}"

                tool_results.append(
                    {
                        "role": "tool",
                        "content": str(result),
                        "tool_call_id": tool_call["id"],
                    }
                )

            # Add tool results to messages
            for tr in tool_results:
                messages.append(tr)

            continue  # Let LLM process tool results

        # No tool calls - LLM is done
        break

    # Parse the final response
    content = response.content if isinstance(response, AIMessage) else ""
    comments = []
    summary = "Reviewed"

    try:
        # Find JSON in the response
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start != -1 and json_end > json_start:
            json_str = content[json_start:json_end]
            result = json.loads(json_str)

            # Extract comments
            for comment in result.get("comments", []):
                comments.append(
                    {
                        "path": filename,
                        "line": comment.get("line"),
                        "message": comment.get("message", ""),
                    }
                )

            summary = result.get("summary", "Reviewed")

            logger.info(f"[{filename}] Completed: {len(comments)} comments")
    except json.JSONDecodeError as e:
        logger.warning(f"[{filename}] Failed to parse JSON: {e}")
        summary = "Review completed (parse error)"

    return FileReviewResult(filename=filename, comments=comments, summary=summary)


async def generate_summary(file_summaries: list[str]) -> str:
    """Generate overall review summary from file summaries."""
    if not file_summaries:
        return "No files were reviewed."

    prompt = render_generate_summary_prompt(file_summaries)
    llm = get_chat_llm(model=settings.synthesis_model)

    messages = [
        SystemMessage(content=render_summary_system_prompt()),
        HumanMessage(content=prompt),
    ]

    response = await llm.ainvoke(messages)
    summary = response.content if isinstance(response.content, str) else str(response.content)

    logger.info("Generated overall summary")
    return summary


async def review_files_parallel(
    files: list[dict],
    pr_title: str,
    pr_description: str | None,
    owner: str,
    repo: str,
    head_ref: str,
    max_concurrency: int = 5,
) -> tuple[list[dict], str]:
    """Review all files in parallel with concurrency limit.

    Args:
        files: List of file dicts with filename, patch, additions, deletions
        pr_title: PR title for context
        pr_description: PR description for context
        owner: Repository owner
        repo: Repository name
        head_ref: PR head branch ref
        max_concurrency: Maximum concurrent file reviews

    Returns:
        Tuple of (all_comments, overall_summary)
    """
    logger.info(f"Reviewing {len(files)} files in parallel (max {max_concurrency} concurrent)")

    # Create semaphore for concurrency control
    semaphore = asyncio.Semaphore(max_concurrency)

    async def review_with_limit(file: dict) -> FileReviewResult:
        async with semaphore:
            return await review_single_file(
                file=file,
                pr_title=pr_title,
                pr_description=pr_description,
                owner=owner,
                repo=repo,
                head_ref=head_ref,
            )

    # Run all file reviews in parallel
    results = await asyncio.gather(
        *[review_with_limit(f) for f in files],
        return_exceptions=True,
    )

    # Collect results
    all_comments = []
    file_summaries = []

    for result in results:
        if isinstance(result, Exception):
            logger.error(f"File review failed: {result}")
            continue
        if isinstance(result, FileReviewResult):
            all_comments.extend(result.comments)
            file_summaries.append(f"**{result.filename}**: {result.summary}")

    # Generate overall summary
    overall_summary = await generate_summary(file_summaries)

    return all_comments, overall_summary
