"""Units, 3D view capture, and field sampling. No CST install."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_cst_studio.config import CSTConfig
from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.rf_fields import (
    parse_complex_vectors,
    poynting_vector,
    sar,
)


def test_parse_vector_and_peak():
    samples = parse_complex_vectors([3.0, 0.0, 4.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    assert samples[0]["magnitude"] == pytest.approx(5.0)
    assert samples[0]["components"]["x"] == {"re": 3.0, "im": 0.0}
    assert samples[1]["magnitude"] == 0.0


def test_poynting_and_sar():
    # E = x-hat, H = y-hat -> E × H* = z-hat, half is 0.5 z
    power = poynting_vector([1 + 0j, 0j, 0j], [0j, 1 + 0j, 0j])
    assert power["z"] == pytest.approx(0.5)
    assert power["magnitude"] == pytest.approx(0.5)
    assert sar(2.0, 4.0) == pytest.approx(8.0)


def test_sar_rejects_negative_conductivity():
    with pytest.raises(ValueError):
        sar(1.0, -1.0)


@pytest.fixture
def live_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> CSTClient:
    monkeypatch.setattr("mcp_cst_studio.cst_client.CST_AVAILABLE", True)
    client = CSTClient(config=CSTConfig(connected=True, work_dir=str(tmp_path)))
    client._project = type("Project", (), {})()
    client._project.model3d = type("Model", (), {})()
    client._project_path = str(tmp_path / "job.cst")
    return client


def test_units_from_mapping(live_client: CSTClient):
    live_client._project.model3d.units = {"length": "mm", "frequency": "GHz"}
    result = live_client.get_project_units()
    assert result["status"] == "ok"
    assert result["length"] == "mm"
    assert result["frequency"] == "GHz"


def test_units_offline_does_not_assume_mm():
    client = CSTClient(config=CSTConfig(connected=False))
    result = client.get_project_units()
    assert result["status"] == "offline"
    assert result["length"] is None
    assert "millimeters" in result["message"]


def test_capture_writes_png_without_history(live_client: CSTClient, tmp_path: Path):
    history: list[str] = []
    live_client._project.model3d.add_to_history = history.append

    def export_image(path: str) -> None:
        Path(path).write_bytes(b"\x89PNG")

    live_client._project.model3d.export_image = export_image
    result = live_client.capture_3d_view("patch.png")
    assert result["status"] == "ok"
    assert result["bytes"] > 0
    assert Path(result["path"]).name == "patch.png"
    assert history == []


def test_capture_reports_missing_writer(live_client: CSTClient):
    result = live_client.capture_3d_view()
    assert result["status"] == "error"
    assert "model3d.export_image" in result["looked_for"]


def test_sample_field_and_hdf5(live_client: CSTClient, tmp_path: Path):
    class Plot:
        def __init__(self) -> None:
            self.points = None
            self.tree = None

        def reset(self) -> None:
            return None

        def set_points(self, points) -> None:
            self.points = points

        def calculate_list(self, tree_path: str) -> None:
            self.tree = tree_path

        def get_list(self):
            if self.tree and "H" in self.tree:
                return [0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
            return [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    class Result3D:
        def export_hdf5(self, path: str, mode: str, tree_path: str) -> None:
            assert mode == "grid"
            assert "e-field" in tree_path
            Path(path).write_bytes(b"hdf5")

    live_client._project.model3d.vector_plot_3d = Plot()
    live_client._project.model3d.result_3d = Result3D()
    live_client._project.model3d.add_to_history = lambda *_args, **_kwargs: None

    sampled = live_client.sample_vector_field(r"2D/3D Results\E", [[0.0, 0.0, 1.0]])
    assert sampled["status"] == "ok"
    assert sampled["peak"]["magnitude"] == pytest.approx(1.0)
    assert "hdf5" not in json.dumps(sampled)

    exported = live_client.export_monitor_hdf5(r"2D/3D Results\e-field", "grid", "e.h5")
    assert exported["status"] == "ok"
    assert exported["bytes"] == 4
    assert "hdf5" not in json.dumps({k: v for k, v in exported.items() if k != "path"})
    assert Path(exported["path"]).read_bytes() == b"hdf5"


@pytest.mark.asyncio
async def test_tools_units_capture_and_field(live_client: CSTClient):
    from mcp_cst_studio.tools.project import handle as project_handle
    from mcp_cst_studio.tools.results import handle as result_handle

    live_client._project.model3d.units = {"length": "m", "frequency": "Hz"}
    units = json.loads((await project_handle("cst_get_units", {}, live_client))[0].text)
    assert units["length"] == "m"

    def export_image(path: str) -> None:
        Path(path).write_bytes(b"png")

    live_client._project.model3d.export_image = export_image
    shot = json.loads((await project_handle("cst_capture_3d_view", {}, live_client))[0].text)
    assert shot["status"] == "ok"
    assert shot["bytes"] > 0
    assert "image" not in shot

    class Plot:
        def set_points(self, points) -> None:
            return None

        def calculate_list(self, tree_path: str) -> None:
            return None

        def get_list(self):
            return [3.0, 0.0, 4.0, 0.0, 0.0, 0.0]

    live_client._project.model3d.vector_plot_3d = Plot()
    field = json.loads((await result_handle(
        "cst_sample_field",
        {
            "tree_path": r"2D/3D Results\e-field",
            "points": [[0, 0, 0]],
            "conductivity": 1.0,
        },
        live_client,
    ))[0].text)
    assert field["samples"][0]["magnitude"] == pytest.approx(5.0)
    assert field["samples"][0]["sar"] == pytest.approx(12.5)


@pytest.mark.asyncio
async def test_field_tools_offline_do_not_invent_numbers():
    from mcp_cst_studio.tools.results import handle

    client = CSTClient(config=CSTConfig(connected=False))
    result = await handle(
        "cst_sample_field",
        {"tree_path": r"2D/3D Results\e-field", "points": [[0, 0, 0]]},
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "offline"
    assert "samples" not in data
    assert "set_points" in " ".join(data["call"])

    exported = await handle(
        "cst_export_field_hdf5",
        {"tree_path": r"2D/3D Results\e-field", "mode": "mesh"},
        client,
    )
    payload = json.loads(exported[0].text)
    assert payload["status"] == "offline"
    assert "bytes" not in payload


@pytest.mark.asyncio
async def test_field_point_cap():
    from mcp_cst_studio.tools.results import handle

    client = CSTClient(config=CSTConfig(connected=False))
    points = [[0, 0, 0]] * 3
    result = await handle(
        "cst_sample_field",
        {"tree_path": "E", "points": points, "max_points": 2},
        client,
    )
    data = json.loads(result[0].text)
    assert data["status"] == "error"
    assert "cap" in data["message"]
