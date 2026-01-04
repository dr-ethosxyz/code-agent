"""Patch parser to extract valid line numbers for GitHub PR review comments."""

import re


def parse_patch_line_numbers(patch: str) -> set[int]:
    """Extract valid line numbers from a unified diff patch.

    GitHub PR review comments can only be placed on lines that are part of
    the diff - specifically lines that were added (+) or removed (-).

    Args:
        patch: Unified diff patch string

    Returns:
        Set of valid line numbers (in the new file) for review comments
    """
    valid_lines = set()

    if not patch:
        return valid_lines

    # Track current line number in the new file
    current_line = 0

    for line in patch.split("\n"):
        # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
        hunk_match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if hunk_match:
            current_line = int(hunk_match.group(1))
            continue

        # Skip if we haven't seen a hunk header yet
        if current_line == 0:
            continue

        if line.startswith("+") and not line.startswith("+++"):
            # Added line - valid for comment
            valid_lines.add(current_line)
            current_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            # Removed line - valid for comment (uses old line context)
            # Note: For removed lines, GitHub uses the line number from context
            # We still include it as the LLM might reference it
            valid_lines.add(current_line)
            # Don't increment - removed lines don't exist in new file
        elif not line.startswith("\\"):
            # Context line (unchanged) - increment but not valid for inline comment
            current_line += 1

    return valid_lines


def filter_comments_by_valid_lines(
    comments: list[dict],
    patches: dict[str, str],
) -> tuple[list[dict], list[dict]]:
    """Filter comments to only those with valid line numbers.

    Args:
        comments: List of comment dicts with 'path', 'line', 'message'
        patches: Dict mapping filename to patch content

    Returns:
        Tuple of (valid_comments, invalid_comments)
    """
    # Build valid lines per file
    valid_lines_by_file = {}
    for filename, patch in patches.items():
        valid_lines_by_file[filename] = parse_patch_line_numbers(patch)

    valid = []
    invalid = []

    for comment in comments:
        path = comment.get("path", "")
        line = comment.get("line")

        # Check if line is in the valid set for this file
        file_valid_lines = valid_lines_by_file.get(path, set())

        if isinstance(line, int) and line in file_valid_lines:
            valid.append(comment)
        else:
            invalid.append(comment)

    return valid, invalid
