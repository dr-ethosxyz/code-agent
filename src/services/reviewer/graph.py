"""LangGraph agent for code review."""

import json
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from src.config import settings
from src.core.llm import get_chat_llm
from src.core.logging import get_logger
from src.core.prompts import (
    render_file_review_prompt,
    render_generate_summary_prompt,
    render_review_system_prompt,
    render_summary_system_prompt,
)
from src.services.reviewer.state import ReviewState
from src.services.reviewer.tools import create_github_tools

logger = get_logger("reviewer.graph")


def create_review_graph(owner: str, repo: str, head_ref: str):
    """Create the review agent graph."""

    # Create tools bound to this repo and PR branch
    tools = create_github_tools(owner, repo, head_ref)

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

        # Build the initial prompt for this file using jinja2 template
        prompt = render_file_review_prompt(
            pr_title=state["pr_title"],
            pr_description=state["pr_description"],
            filename=current_file["filename"],
            additions=current_file["additions"],
            deletions=current_file["deletions"],
            patch=current_file["patch"],
        )

        return {
            "messages": [
                SystemMessage(content=render_review_system_prompt()),
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
                    file_comments.append(
                        {
                            "path": current_file["filename"],
                            "line": comment.get("line"),
                            "message": comment.get("message", ""),
                        }
                    )

                # Extract summary
                if result.get("summary"):
                    file_summaries.append(f"**{current_file['filename']}**: {result['summary']}")

                logger.info(
                    f"Processed review for {current_file['filename']}: "
                    f"{len(result.get('comments', []))} comments"
                )
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse review JSON: {e}")
            # Still move to next file
            file_summaries.append(f"**{current_file['filename']}**: Review completed (parse error)")

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

        # Build the summary prompt using jinja2 template
        prompt = render_generate_summary_prompt(file_summaries)

        llm = get_chat_llm(model=settings.synthesis_model)
        messages = [
            SystemMessage(content=render_summary_system_prompt()),
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
