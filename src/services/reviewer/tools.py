"""GitHub tools for the code review agent."""

import re
from typing import Callable

from langchain_core.tools import tool

from src.services.github.service import get_file_contents, list_directory, search_code


def create_github_tools(owner: str, repo: str) -> list[Callable]:
    """Create GitHub tools bound to a specific repository.

    Tools are created with owner/repo pre-bound so the agent
    doesn't need to specify them on each call.
    """

    @tool
    def get_file(path: str, ref: str = "HEAD") -> str:
        """Fetch full contents of a file from the repository.

        Use this when:
        - The patch diff doesn't provide enough context
        - You need to see the complete file structure
        - You want to understand how a function/class is defined

        Args:
            path: File path relative to repo root (e.g. "src/utils/helper.py")
            ref: Git ref (branch/commit/tag), defaults to HEAD
        """
        try:
            content = get_file_contents(owner, repo, path, ref)
            # Truncate very large files
            if len(content) > 50000:
                return content[:50000] + "\n\n... [truncated, file too large]"
            return content
        except Exception as e:
            return f"Error fetching file: {e}"

    @tool
    def list_files(path: str = "") -> str:
        """List files and directories at a path in the repository.

        Use this to:
        - Understand project structure
        - Find related files (tests, configs, types)
        - Navigate the codebase

        Args:
            path: Directory path relative to repo root, empty for root
        """
        try:
            contents = list_directory(owner, repo, path)
            lines = []
            for item in contents:
                type_indicator = "📁" if item["type"] == "dir" else "📄"
                lines.append(f"{type_indicator} {item['path']}")
            return "\n".join(lines) if lines else "Empty directory"
        except Exception as e:
            return f"Error listing directory: {e}"

    @tool
    def search_codebase(query: str) -> str:
        """Search the repository for code matching a query.

        Use this to:
        - Find where a function/class is used
        - Locate related implementations
        - Find patterns in the codebase

        Args:
            query: Search query (supports GitHub code search syntax)
        """
        try:
            results = search_code(owner, repo, query)
            if not results:
                return "No results found"
            lines = []
            for item in results[:10]:
                lines.append(f"- {item['path']}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error searching code: {e}"

    @tool
    def get_imports(path: str) -> str:
        """Extract import statements from a file to understand dependencies.

        Use this to:
        - Understand what a file depends on
        - Find related modules
        - Check for circular dependencies

        Args:
            path: File path relative to repo root
        """
        try:
            content = get_file_contents(owner, repo, path, "HEAD")

            # Python imports
            if path.endswith(".py"):
                import_lines = []
                for line in content.split("\n"):
                    line = line.strip()
                    if line.startswith("import ") or line.startswith("from "):
                        import_lines.append(line)
                    elif line and not line.startswith("#") and import_lines:
                        # Stop after imports section
                        if not line.startswith("import ") and not line.startswith("from "):
                            break
                return "\n".join(import_lines) if import_lines else "No imports found"

            # TypeScript/JavaScript imports
            if path.endswith((".ts", ".tsx", ".js", ".jsx")):
                import_pattern = r'^import\s+.*?[\'"].*?[\'"];?$'
                imports = re.findall(import_pattern, content, re.MULTILINE)
                return "\n".join(imports) if imports else "No imports found"

            return "Unsupported file type for import extraction"
        except Exception as e:
            return f"Error extracting imports: {e}"

    @tool
    def find_related_files(path: str) -> str:
        """Find files that might be related to the given file.

        Looks for:
        - Test files (test_*.py, *.test.ts)
        - Type definitions (*.types.ts, types.py)
        - Config files with similar names

        Args:
            path: File path to find related files for
        """
        try:
            # Extract filename without extension
            parts = path.rsplit("/", 1)
            directory = parts[0] if len(parts) > 1 else ""
            filename = parts[-1]
            name_without_ext = filename.rsplit(".", 1)[0]

            related = []

            # Look for test files
            test_patterns = [
                f"test_{name_without_ext}",
                f"{name_without_ext}_test",
                f"{name_without_ext}.test",
                f"{name_without_ext}.spec",
            ]

            # Search for each pattern
            for pattern in test_patterns:
                try:
                    results = search_code(owner, repo, f"filename:{pattern}")
                    for item in results[:3]:
                        if item["path"] not in related:
                            related.append(item["path"])
                except Exception:
                    pass

            # Look for type files
            type_patterns = [
                f"{name_without_ext}.types",
                f"{name_without_ext}Types",
            ]
            for pattern in type_patterns:
                try:
                    results = search_code(owner, repo, f"filename:{pattern}")
                    for item in results[:3]:
                        if item["path"] not in related:
                            related.append(item["path"])
                except Exception:
                    pass

            if related:
                return "Related files found:\n" + "\n".join(f"- {f}" for f in related)
            return "No related files found"
        except Exception as e:
            return f"Error finding related files: {e}"

    return [get_file, list_files, search_codebase, get_imports, find_related_files]
