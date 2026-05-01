"""Shared test configuration."""

import pytest


def pytest_collection_modifyitems(items):
    """Add slow marker to integration tests that hit real APIs."""
    for item in items:
        if "search_providers" in str(item.fspath) or "fetch_providers" in str(item.fspath):
            item.add_marker(pytest.mark.slow)
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.slow)
