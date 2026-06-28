"""
Shared pytest fixtures for the URL Shortener Service test suite.

Fixture inventory (mirrors the `fixtures` key in the test-generator
output_schema):

  - name: reset_state
    scope: function
    autouse: true
    purpose: >
      Wipe the in-memory store and rate-limiter buckets before and after
      every test so no state leaks between test functions.
"""
import pytest

from src import limiter, store


@pytest.fixture(autouse=True)
def reset_state():
    store.clear()
    limiter.clear()
    yield
    store.clear()
    limiter.clear()
