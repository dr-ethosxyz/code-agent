"""Tests for PR reference parsing."""

from unittest.mock import patch

import pytest

from src.core.pr_parser import PRReference, extract_review_intent, parse_pr_reference


class TestParsePRReference:
    """Tests for parse_pr_reference function."""

    def test_full_github_url(self):
        """Parse full GitHub PR URL."""
        text = "Please review https://github.com/owner/repo/pull/123"
        result = parse_pr_reference(text)

        assert result is not None
        assert result.owner == "owner"
        assert result.repo == "repo"
        assert result.pr_number == 123

    def test_github_url_https(self):
        """Parse HTTPS GitHub URL."""
        result = parse_pr_reference("https://github.com/acme/project/pull/42")

        assert result == PRReference(owner="acme", repo="project", pr_number=42)

    def test_owner_repo_hash_format(self):
        """Parse owner/repo#123 format."""
        result = parse_pr_reference("Check out acme/my-repo#456")

        assert result is not None
        assert result.owner == "acme"
        assert result.repo == "my-repo"
        assert result.pr_number == 456

    def test_owner_repo_with_dots(self):
        """Parse repo names with dots."""
        result = parse_pr_reference("See foo/bar.js#99")

        assert result is not None
        assert result.owner == "foo"
        assert result.repo == "bar.js"
        assert result.pr_number == 99

    @patch("src.core.pr_parser.settings")
    def test_short_hash_format_with_defaults(self, mock_settings):
        """Parse #123 format with default owner/repo."""
        mock_settings.default_repo_owner = "default-owner"
        mock_settings.default_repo_name = "default-repo"

        result = parse_pr_reference("Review #789")

        assert result is not None
        assert result.owner == "default-owner"
        assert result.repo == "default-repo"
        assert result.pr_number == 789

    @patch("src.core.pr_parser.settings")
    def test_short_hash_format_no_defaults(self, mock_settings):
        """Return None for #123 when no defaults configured."""
        mock_settings.default_repo_owner = None
        mock_settings.default_repo_name = None

        result = parse_pr_reference("#123")

        assert result is None

    @patch("src.core.pr_parser.settings")
    def test_review_number_format(self, mock_settings):
        """Parse 'review 123' format."""
        mock_settings.default_repo_owner = "owner"
        mock_settings.default_repo_name = "repo"

        result = parse_pr_reference("please review 55")

        assert result is not None
        assert result.pr_number == 55

    @patch("src.core.pr_parser.settings")
    def test_pr_number_format(self, mock_settings):
        """Parse 'PR 123' format."""
        mock_settings.default_repo_owner = "owner"
        mock_settings.default_repo_name = "repo"

        result = parse_pr_reference("Check PR 77")

        assert result is not None
        assert result.pr_number == 77

    def test_no_match(self):
        """Return None when no PR reference found."""
        result = parse_pr_reference("Just a regular message")

        assert result is None

    def test_empty_string(self):
        """Handle empty string."""
        result = parse_pr_reference("")

        assert result is None


class TestExtractReviewIntent:
    """Tests for extract_review_intent function."""

    @pytest.mark.parametrize(
        "text",
        [
            "Please review this PR",
            "Can you check this?",
            "Look at this code",
            "Examine the changes",
            "Analyze the PR",
            "Inspect the implementation",
        ],
    )
    def test_review_keywords_detected(self, text):
        """Detect various review keywords."""
        assert extract_review_intent(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "REVIEW this",
            "Please CHECK it",
            "LOOK AT this PR",
        ],
    )
    def test_case_insensitive(self, text):
        """Keywords are case-insensitive."""
        assert extract_review_intent(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "Hello world",
            "This is a test",
            "Merge when ready",
            "LGTM",
        ],
    )
    def test_no_review_intent(self, text):
        """Return False when no review keywords."""
        assert extract_review_intent(text) is False

    def test_empty_string(self):
        """Handle empty string."""
        assert extract_review_intent("") is False
