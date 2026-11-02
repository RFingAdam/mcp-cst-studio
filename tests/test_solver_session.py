"""Solver session and result-tool tests that do not need a CST install."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from mcp_cst_studio.config import CSTConfig
from mcp_cst_studio.cst_client import CSTClient


@pytest.fixture
def live_client(monkeypatch: pytest.MonkeyPatch) -> CSTClient:
    monkeypatch.setattr("mcp_cst_studio.cst_client.CST_AVAILABLE", True)
    client = CSTClient(config=CSTConfig(connected=True, work_dir="/tmp/cst_test"))
    project = MagicMock()
    project.model3d.is_solver_running.return_value = False
    project.model3d.run_solver.return_value = "solver-ok"
    client._project = project
    client._project_path = r"C:\test\project.cst"
    return client


def test_async_solver_completes_without_history(live_client: CSTClient):
    started = live_client.start_solver_async()
    assert started["status"] == "started"
    assert live_client._solver_thread is not None
    live_client._solver_thread.join(timeout=2)
    status = live_client.solver_session_status()
    assert status["status"] == "ok"
    assert status["solver"]["status"] == "completed"
    assert status["solver"]["result"] == "solver-ok"
    live_client._project.model3d.add_to_history.assert_not_called()
    text = json.dumps(status)
    assert "MsgBox" not in text


def test_second_start_while_running_does_not_block(live_client: CSTClient):
    live_client._project.model3d.is_solver_running.return_value = True
    again = live_client.start_solver_async()
    assert again["status"] == "already_running"
    assert live_client._solver_thread is None


@pytest.mark.asyncio
async def test_status_tool_does_not_emit_msgbox(live_client: CSTClient):
    from mcp_cst_studio.tools.simulation import handle

    result = await handle("cst_get_simulation_status", {}, live_client)
    data = json.loads(result[0].text)
    assert data["status"] == "ok"
    assert "MsgBox" not in result[0].text
    live_client._project.model3d.add_to_history.assert_not_called()


@pytest.mark.asyncio
async def test_async_tool_uses_thread_not_vba(live_client: CSTClient):
    from mcp_cst_studio.tools.simulation import handle

    result = await handle("cst_run_simulation_async", {}, live_client)
    data = json.loads(result[0].text)
    assert data["status"] == "started"
    assert data["mode"] == "async"
    assert "vba" not in data
    live_client._solver_thread.join(timeout=2)


@pytest.mark.asyncio
async def test_tune_step_offline_describes_sequence():
    from mcp_cst_studio.tools.optimization import handle

    client = CSTClient(config=CSTConfig(connected=False))
    result = await handle(
        "cst_tune_step",
        {"parameters": {"patch_length": 28.0}, "f0_ghz": 2.4},
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "offline"
    assert "DeleteResults" in data["sequence"]


@pytest.mark.asyncio
async def test_result_curve_offline():
    from mcp_cst_studio.tools.results import handle

    client = CSTClient(config=CSTConfig(connected=False))
    result = await handle(
        "cst_get_result_curve",
        {"tree_path": r"1D Results\S-Parameters\S1,1"},
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "offline"
    assert "get_xdata" in data["message"]


def test_sample_farfield_uses_calculator(live_client: CSTClient):
    calc = MagicMock()
    calc.get_list.return_value = [1.0, 3.5, 2.0]
    live_client._project.model3d.farfield_calculator = calc
    # MagicMock auto-creates other attributes; pin the one we look up first.
    result = live_client.sample_farfield(
        frequency_hz=2.4e9,
        theta_deg=[0.0, 90.0, 180.0],
        phi_deg=[0.0, 0.0, 0.0],
        tree_path=r"Farfields\farfield (f=2.4)",
    )
    assert result["status"] == "ok"
    assert result["peak"] == 3.5
    assert result["n"] == 3
    calc.reset.assert_called_once()
    calc.add_list_evaluation_points.assert_called_once()
