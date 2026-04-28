"""
Tests for AppContext container.
"""
import pytest
from common.context import AppContext, init_app_context, get_app_context


def test_init_and_get():
    """Test basic init/get cycle."""
    ctx = init_app_context(config={}, db_engine=None)
    assert get_app_context() is ctx


def test_uninitialized_raises():
    """Test that get_app_context raises before init."""
    import common.context as ctx_module
    original = ctx_module._container
    ctx_module._container = None
    try:
        with pytest.raises(RuntimeError, match="not initialized"):
            get_app_context()
    finally:
        ctx_module._container = original


def test_context_immutable():
    """Test that AppContext is frozen."""
    ctx = init_app_context(config={"key": "value"}, db_engine=None)
    with pytest.raises(AttributeError):
        ctx.config = {}