"""LangGraph agent for code review."""

import json
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from src.core.llm import get_chat_llm
from src.core.logging import get_logger
from src.config import settings
from src.services.reviewer.state import ReviewState
from src.services.reviewer.tools import create_github_tools

logger = get_logger("reviewer.graph")

REVIEW_SYSTEM_PROMPT = """You are an expert code reviewer. Your task is to review code changes in a pull request.

For the current file, you will:
1. Analyze the diff/patch carefully
2. If you need more context (full file, imports, related files), use the available tools
3. Once you have enough context, provide your review

When you're done reviewing the file, respond with a JSON object in this exact format:
```json
{
  "done": true,
  "comments": [
    {"line": <line_number>, "message": "<comment>"}
  ],
  "summary": "<brief summary of this file's changes>"
}
```

The line numbers should correspond to the NEW file (lines starting with +).
Only include comments for actual issues - bugs, security concerns, performance problems, or significant code quality issues.
Do NOT comment on style preferences or minor improvements unless they're significant.

If you need to use a tool to get more context, just call the tool. Do not include the JSON response until you're done.

Available tools:
- get_file: Get full contents of any file in the repo
- list_files: List files in a directory
- search_codebase: Search for code patterns
- get_imports: Extract import statements from a file
- find_related_files: Find test files, types, related code"""


SUMMARY_SYSTEM_PROMPT = """You are summarizing a code review. Given the individual file summaries, create a concise overall summary.

Format your response as a brief paragraph (2-4 sentences) that captures:
- The main theme of the changes
- Any notable issues found
- Overall assessment (LGTM, needs changes, etc.)

Be direct and specific. Don't be overly positive or negative."""


def create_review_graph(owner: str, repo: str):
    """Create the review agent graph."""

    # Create tools bound to this repo
    tools = create_github_tools(owner, repo)

    # Create LLM with tools
    llm = get_chat_llm(model=settings.review_model)
    llm_with_tools = llm.bind_tools(tools)

    def select_next_file(state: ReviewState) -> dict:
        """Select the next file to review."""
        idx = state["current_file_index"]
        files = state["files"]

        if idx >= len(files):
            logger.info("All files reviewed")
            return {}

        current_file = files[idx]
        logger.info(f"Selecting file {idx + 1}/{len(files)}: {current_file['filename']}")

        # Build the initial prompt for this file
        prompt = f"""Review this file from PR: {state['pr_title']}

PR Description: {state['pr_description'] or 'No description provided'}

File: {current_file['filename']}
Additions: {current_file['additions']}, Deletions: {current_file['deletions']}

Diff:
```
{current_file['patch']}
```

Analyze this diff. If you need more context to provide a good review, use the available tools.
When you're done, respond with the JSON format described in your instructions."""

        return {
            "messages": [
                SystemMessage(content=REVIEW_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
        }

    async def review_file_node(state: ReviewState) -> dict:
        """Have the LLM review the current file (may call tools)."""
        messages = state["messages"]
        response = await llm_with_tools.ainvoke(messages)
        return {"messages": [response]}

    def route_after_review(
        state: ReviewState,
    ) -> Literal["tools", "process_review", "select_file"]:
        """Route based on LLM response - tools, done with file, or error."""
        last_message = state["messages"][-1]

        if not isinstance(last_message, AIMessage):
            logger.warning("Expected AIMessage, got something else")
            return "select_file"

        # Check if LLM wants to use tools
        if last_message.tool_calls:
            logger.info(f"Agent calling tools: {[t['name'] for t in last_message.tool_calls]}")
            return "tools"

        # Check if response contains done JSON
        content = last_message.content
        if isinstance(content, str) and '"done": true' in content.lower():
            return "process_review"

        # LLM responded but didn't finish - might need prompting
        logger.warning("LLM response doesn't contain done marker, continuing")
        return "process_review"

    def process_review_result(state: ReviewState) -> dict:
        """Extract comments and summary from the LLM's final response."""
        last_message = state["messages"][-1]
        content = last_message.content if isinstance(last_message, AIMessage) else ""

        current_file = state["files"][state["current_file_index"]]
        file_comments = list(state["file_comments"])
        file_summaries = list(state["file_summaries"])

        # Try to parse the JSON response
        try:
            # Find JSON in the response
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                json_str = content[json_start:json_end]
                result = json.loads(json_str)

                # Extract comments
                for comment in result.get("comments", []):
                    file_comments.append({
                        "path": current_file["filename"],
                        "line": comment.get("line"),
                        "message": comment.get("message", ""),
                    })

                # Extract summary
                if result.get("summary"):
                    file_summaries.append(
                        f"**{current_file['filename']}**: {result['summary']}"
                    )

                logger.info(
                    f"Processed review for {current_file['filename']}: "
                    f"{len(result.get('comments', []))} comments"
                )
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse review JSON: {e}")
            # Still move to next file
            file_summaries.append(
                f"**{current_file['filename']}**: Review completed (parse error)"
            )

        return {
            "file_comments": file_comments,
            "file_summaries": file_summaries,
            "current_file_index": state["current_file_index"] + 1,
            "messages": [],  # Clear messages for next file
        }

    def should_continue_or_summarize(
        state: ReviewState,
    ) -> Literal["review_file", "generate_summary"]:
        """Check if there are more files to review."""
        if state["current_file_index"] >= len(state["files"]):
            return "generate_summary"
        return "review_file"

    async def generate_summary_node(state: ReviewState) -> dict:
        """Generate overall review summary."""
        file_summaries = state["file_summaries"]

        if not file_summaries:
            return {
                "overall_summary": "No files were reviewed.",
                "review_complete": True,
            }

        prompt = f"""These are the individual file reviews from a PR:

{chr(10).join(file_summaries)}

Provide an overall summary of this code review."""

        llm = get_chat_llm(model=settings.review_model)
        messages = [
            SystemMessage(content=SUMMARY_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]

        response = await llm.ainvoke(messages)
        summary = response.content if isinstance(response.content, str) else str(response.content)

        logger.info("Generated overall summary")

        return {
            "overall_summary": summary,
            "review_complete": True,
        }

    # Build the graph
    graph = StateGraph(ReviewState)

    # Add nodes
    graph.add_node("select_file", select_next_file)
    graph.add_node("review_file", review_file_node)
    graph.add_node("tools", ToolNode(tools=tools))
    graph.add_node("process_review", process_review_result)
    graph.add_node("generate_summary", generate_summary_node)

    # Set entry point
    graph.set_entry_point("select_file")

    # Add edges
    graph.add_conditional_edges(
        "select_file",
        should_continue_or_summarize,
        {
            "review_file": "review_file",
            "generate_summary": "generate_summary",
        },
    )

    graph.add_conditional_edges(
        "review_file",
        route_after_review,
        {
            "tools": "tools",
            "process_review": "process_review",
            "select_file": "select_file",
        },
    )

    graph.add_edge("tools", "review_file")
    graph.add_edge("process_review", "select_file")
    graph.add_edge("generate_summary", END)

    return graph.compile()
