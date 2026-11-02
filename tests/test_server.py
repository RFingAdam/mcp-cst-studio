"""Tests for ToolRegistry and register_all_tools() in the MCP server."""

from __future__ import annotations

import pytest

from mcp_cst_studio.config import CSTConfig
from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.tools import ToolRegistry

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def offline_client() -> CSTClient:
    return CSTClient(config=CSTConfig(connected=False))


@pytest.fixture
def fresh_registry() -> ToolRegistry:
    """A brand-new ToolRegistry that is independent of the module singleton."""
    return ToolRegistry()


# ---------------------------------------------------------------------------
# ToolRegistry: basic behaviour
# ---------------------------------------------------------------------------

class TestToolRegistryBasic:
    def test_new_registry_has_no_tools(self, fresh_registry: ToolRegistry):
        assert len(fresh_registry._tools) == 0

    def test_new_registry_has_no_handlers(self, fresh_registry: ToolRegistry):
        assert len(fresh_registry._handlers) == 0

    def test_clear_removes_tools(self, fresh_registry: ToolRegistry, offline_client: CSTClient):
        from mcp_cst_studio.tools.project import TOOLS, handle
        fresh_registry.add_module(TOOLS, handle, offline_client)
        assert len(fresh_registry._tools) > 0
        fresh_registry.clear()
        assert len(fresh_registry._tools) == 0

    def test_clear_removes_handlers(self, fresh_registry: ToolRegistry, offline_client: CSTClient):
        from mcp_cst_studio.tools.project import TOOLS, handle
        fresh_registry.add_module(TOOLS, handle, offline_client)
        assert len(fresh_registry._handlers) > 0
        fresh_registry.clear()
        assert len(fresh_registry._handlers) == 0

    def test_clear_on_empty_registry_is_safe(self, fresh_registry: ToolRegistry):
        fresh_registry.clear()  # Must not raise
        assert len(fresh_registry._tools) == 0


# ---------------------------------------------------------------------------
# ToolRegistry: add_module
# ---------------------------------------------------------------------------

class TestToolRegistryAddModule:
    def test_add_module_registers_project_tools(
        self, fresh_registry: ToolRegistry, offline_client: CSTClient
    ):
        from mcp_cst_studio.tools.project import TOOLS, handle
        fresh_registry.add_module(TOOLS, handle, offline_client)
        assert len(fresh_registry._tools) == len(TOOLS)

    def test_add_module_registers_handlers_for_every_tool(
        self, fresh_registry: ToolRegistry, offline_client: CSTClient
    ):
        from mcp_cst_studio.tools.project import TOOLS, handle
        fresh_registry.add_module(TOOLS, handle, offline_client)
        for tool in TOOLS:
            assert tool.name in fresh_registry._handlers

    def test_multiple_add_module_calls_accumulate(
        self, fresh_registry: ToolRegistry, offline_client: CSTClient
    ):
        from mcp_cst_studio.tools.geometry import TOOLS as geo_tools
        from mcp_cst_studio.tools.geometry import handle as gh
        from mcp_cst_studio.tools.project import TOOLS as project_tools
        from mcp_cst_studio.tools.project import handle as ph
        fresh_registry.add_module(project_tools, ph, offline_client)
        fresh_registry.add_module(geo_tools, gh, offline_client)
        assert len(fresh_registry._tools) == len(project_tools) + len(geo_tools)


# ---------------------------------------------------------------------------
# register_all_tools: total count
# ---------------------------------------------------------------------------

class TestRegisterAllTools:
    def test_register_all_tools_registers_162_tools(self, offline_client: CSTClient):
        """register_all_tools() must register exactly 173 tools."""
        from mcp.server import Server

        from mcp_cst_studio.tools import _registry, register_all_tools

        server = Server("test-server")
        register_all_tools(server, offline_client)

        assert len(_registry._tools) == 173

    def test_register_all_tools_clears_before_registering(self, offline_client: CSTClient):
        """Calling register_all_tools twice must not double the count."""
        from mcp.server import Server

        from mcp_cst_studio.tools import _registry, register_all_tools

        server = Server("test-server")
        register_all_tools(server, offline_client)
        first_count = len(_registry._tools)

        server2 = Server("test-server-2")
        register_all_tools(server2, offline_client)
        second_count = len(_registry._tools)

        assert first_count == second_count == 173

    def test_all_tool_names_are_unique(self, offline_client: CSTClient):
        """No two tools may share the same name."""
        from mcp.server import Server

        from mcp_cst_studio.tools import _registry, register_all_tools

        server = Server("test-server")
        register_all_tools(server, offline_client)

        names = [tool.name for tool in _registry._tools]
        assert len(names) == len(set(names)), "Duplicate tool names detected"

    def test_all_tools_have_non_empty_names(self, offline_client: CSTClient):
        from mcp.server import Server

        from mcp_cst_studio.tools import _registry, register_all_tools

        server = Server("test-server")
        register_all_tools(server, offline_client)

        for tool in _registry._tools:
            assert tool.name, f"Tool with empty name detected: {tool!r}"

    def test_all_tools_have_descriptions(self, offline_client: CSTClient):
        from mcp.server import Server

        from mcp_cst_studio.tools import _registry, register_all_tools

        server = Server("test-server")
        register_all_tools(server, offline_client)

        for tool in _registry._tools:
            assert tool.description, f"Tool '{tool.name}' has no description"

    def test_every_tool_has_a_handler(self, offline_client: CSTClient):
        from mcp.server import Server

        from mcp_cst_studio.tools import _registry, register_all_tools

        server = Server("test-server")
        register_all_tools(server, offline_client)

        for tool in _registry._tools:
            assert tool.name in _registry._handlers, (
                f"No handler registered for tool '{tool.name}'"
            )


# ---------------------------------------------------------------------------
# tool_names: enumerate names via _tools list
# ---------------------------------------------------------------------------

class TestToolNames:
    def test_tool_names_are_accessible(self, offline_client: CSTClient):
        from mcp.server import Server

        from mcp_cst_studio.tools import _registry, register_all_tools

        server = Server("test-server")
        register_all_tools(server, offline_client)

        names = [tool.name for tool in _registry._tools]
        assert isinstance(names, list)
        assert len(names) == 173

    def test_tool_names_contain_expected_entries(self, offline_client: CSTClient):
        from mcp.server import Server

        from mcp_cst_studio.tools import _registry, register_all_tools

        server = Server("test-server")
        register_all_tools(server, offline_client)

        names = {tool.name for tool in _registry._tools}
        expected = {
            "cst_create_project",
            "cst_open_project",
            "cst_save_project",
            "cst_close_project",
            "cst_connection_status",
            "cst_execute_vba",
        }
        missing = expected - names
        assert not missing, f"Expected tools not found: {missing}"

    def test_tool_names_all_start_with_cst_prefix(self, offline_client: CSTClient):
        from mcp.server import Server

        from mcp_cst_studio.tools import _registry, register_all_tools

        server = Server("test-server")
        register_all_tools(server, offline_client)

        for tool in _registry._tools:
            assert tool.name.startswith("cst_"), (
                f"Tool '{tool.name}' does not start with 'cst_'"
            )


# ---------------------------------------------------------------------------
# create_server() integration
# ---------------------------------------------------------------------------

class TestCreateServer:
    def test_create_server_returns_server_and_client(self):
        from mcp.server import Server

        from mcp_cst_studio.server import create_server

        server, client = create_server()

        assert isinstance(server, Server)
        assert isinstance(client, CSTClient)

    def test_create_server_client_is_offline_without_cst(self):
        from mcp_cst_studio.server import create_server

        _, client = create_server()

        # On CI without CST the client must always be in offline mode
        assert client.mode == "offline"
