"""CST Studio connection manager with connected/offline modes."""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

from mcp_cst_studio.config import CSTConfig
from mcp_cst_studio.dialog_handler import DialogWatcher, dismiss_cst_dialogs, find_cst_dialogs
from mcp_cst_studio.rf_fields import parse_complex_vectors, peak_sample
from mcp_cst_studio.rf_metrics import extract_curve, summarize_reflection
from mcp_cst_studio.validators import ValidationError, validate_file_path

logger = logging.getLogger(__name__)

# Try importing the official CST Python library
try:
    import cst.interface  # type: ignore[import-untyped]
    import cst.results  # type: ignore[import-untyped]
    CST_AVAILABLE = True
except ImportError:
    CST_AVAILABLE = False


class CSTClient:
    """Manages CST Studio Suite connection.

    In connected mode (Windows with CST), executes VBA directly.
    In offline mode (any OS), returns generated VBA scripts.
    """

    def __init__(self, config: CSTConfig | None = None) -> None:
        self._config = config or CSTConfig.from_env()
        self._de: Any = None  # cst.interface.DesignEnvironment
        self._project: Any = None  # Active project handle
        self._project_path: str | None = None
        self._solver_lock = threading.Lock()
        self._solver_thread: threading.Thread | None = None
        self._solver_state: dict[str, Any] = {"status": "idle"}

    @property
    def connected(self) -> bool:
        return self._config.connected and CST_AVAILABLE

    @property
    def has_project(self) -> bool:
        return self._project is not None

    @property
    def project_path(self) -> str | None:
        return self._project_path

    @property
    def mode(self) -> str:
        return "connected" if self.connected else "offline"

    def connect(self) -> dict:
        """Connect to CST Design Environment.

        First tries to connect to an already-running instance. If none
        is running, launches a new one.
        """
        if not CST_AVAILABLE:
            return {
                "status": "offline",
                "message": "CST Python library not available. Running in offline mode: "
                "VBA scripts will be generated but not executed.",
            }

        try:
            # Try connecting to an already-running CST instance first
            running = cst.interface.running_design_environments()
            if running:
                self._de = cst.interface.DesignEnvironment.connect(running[0])
                self._config.connected = True
                # Pick up any already-open project
                open_projects = self._de.get_open_projects()
                if open_projects:
                    self._project = open_projects[0]
                    fname = self._project.filename
                    self._project_path = str(fname() if callable(fname) else fname)
                return {
                    "status": "connected",
                    "message": f"Connected to running CST instance (PID {running[0]})",
                    "open_projects": len(open_projects) if open_projects else 0,
                }

            # No running instance: launch a new one
            self._de = cst.interface.DesignEnvironment()
            self._config.connected = True
            return {"status": "connected", "message": "Launched new CST Design Environment"}
        except Exception as e:
            self._config.connected = False
            return {
                "status": "offline",
                "message": f"Failed to connect to CST: {e}. Running in offline mode.",
            }

    def disconnect(self) -> dict:
        """Disconnect from CST."""
        if self._de is not None:
            try:
                self._de.close()
            except Exception:
                pass
            self._de = None
            self._project = None
            self._project_path = None
            self._config.connected = False
        return {"status": "disconnected"}

    # Maps project type codes to DesignEnvironment factory methods
    _PROJECT_FACTORIES: dict[str, str] = {
        "MWS": "new_mws",
        "EMS": "new_ems",
        "PS": "new_ps",
        "MPS": "new_mps",
        "CS": "new_cs",
        "DS": "new_ds",
        "PCB": "new_pcbs",
    }

    def new_project(self, path: str, project_type: str = "MWS") -> dict:
        """Create a new CST project.

        Starts a background dialog watcher before saving because
        ``project.save(path)`` can trigger a blocking modal dialog
        (e.g. overwrite confirmation).  The watcher auto-dismisses it.
        """
        if self.connected and self._de is not None:
            try:
                factory_name = self._PROJECT_FACTORIES.get(
                    project_type.upper(), "new_mws"
                )
                factory = getattr(self._de, factory_name, self._de.new_mws)
                self._project = factory()
                # Start watcher to handle potential save dialog
                self.start_dialog_watcher()
                try:
                    self._project.save(path)
                finally:
                    self.stop_dialog_watcher()
                self._project_path = path
                return {"status": "created", "path": path, "type": project_type}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        return {
            "status": "offline",
            "path": path,
            "type": project_type,
            "message": "Project creation requires connected mode. "
            "Use the generated VBA scripts on a Windows machine with CST.",
        }

    def open_project(self, path: str) -> dict:
        """Open an existing CST project."""
        if self.connected and self._de is not None:
            try:
                self._project = self._de.open_project(path)
                self._project_path = path
                return {"status": "opened", "path": path}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        self._project_path = path
        return {
            "status": "offline",
            "path": path,
            "message": "Project opened in offline reference mode.",
        }

    def save_project(self, path: str | None = None) -> dict:
        """Save the current project.

        Starts a background dialog watcher because ``project.save()``
        can trigger a blocking modal dialog (overwrite confirmation,
        file-in-use warning, etc.).  The watcher auto-dismisses it.
        """
        save_path = path or self._project_path
        if self.connected and self._project is not None:
            try:
                # Start watcher to handle potential save dialog
                self.start_dialog_watcher()
                try:
                    if save_path:
                        self._project.save(save_path)
                    else:
                        self._project.save()
                finally:
                    self.stop_dialog_watcher()
                self._project_path = save_path
                return {"status": "saved", "path": save_path}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        return {"status": "offline", "message": "Save requires connected mode."}

    def close_project(self) -> dict:
        """Close the current project."""
        if self.connected and self._project is not None:
            try:
                self._project.close()
            except Exception:
                pass
            self._project = None
            self._project_path = None
            return {"status": "closed"}

        self._project = None
        self._project_path = None
        return {"status": "closed", "message": "Project reference cleared."}

    _history_counter: int = 0

    def execute_vba(self, vba_code: str, history_label: str | None = None) -> dict:
        """Execute VBA code in CST.

        In connected mode: executes via ``model3d.add_to_history()`` which
        adds the VBA macro to the project history and runs it immediately.
        A background :class:`DialogWatcher` runs during execution to
        auto-dismiss any CST modal dialogs (error, property, frequency-range)
        that would otherwise block the COM call indefinitely.
        Falls back to the schematic interface for Design Studio projects.

        In offline mode: returns the VBA script for manual execution.
        """
        if self.connected and self._project is not None:
            try:
                CSTClient._history_counter += 1
                label = history_label or f"mcp_action_{CSTClient._history_counter}"
                watcher = DialogWatcher(poll_interval=0.5)
                watcher.start()
                try:
                    result = self._project.model3d.add_to_history(label, vba_code)
                finally:
                    watcher.stop()
                response: dict = {
                    "status": "executed",
                    "result": str(result) if result else "ok",
                }
                log = watcher.get_log()
                if log:
                    response["dialogs_dismissed"] = len(log)
                    response["dialog_log"] = log
                return response
            except AttributeError:
                # DS/CS projects may only have the model3d interface;
                # fall back to the schematic interface
                try:
                    result = self._project.schematic.execute_vba_code(vba_code)
                    return {
                        "status": "executed",
                        "result": str(result) if result else "ok",
                    }
                except Exception as e:
                    return {"status": "error", "message": str(e), "vba": vba_code}
            except Exception as e:
                return {"status": "error", "message": str(e), "vba": vba_code}

        return {
            "status": "offline",
            "vba": vba_code,
            "message": "VBA script generated. Execute in CST Studio Suite on Windows.",
        }

    def execute_vba_silent(self, vba_code: str) -> dict:
        """Execute VBA without adding to project history.

        Uses ``schematic.execute_vba_code()`` which runs the macro silently.
        The code must be wrapped in ``Sub Main() ... End Sub``.
        Ideal for optimization loops where dozens of iterations would
        otherwise bloat the history list.

        A background :class:`DialogWatcher` runs during execution to
        auto-dismiss any CST modal dialogs that would block the COM call.

        In offline mode: returns the VBA script for manual execution.
        """
        if self.connected and self._project is not None:
            try:
                watcher = DialogWatcher(poll_interval=0.5)
                watcher.start()
                try:
                    self._project.schematic.execute_vba_code(vba_code)
                finally:
                    watcher.stop()
                response: dict = {"status": "executed"}
                log = watcher.get_log()
                if log:
                    response["dialogs_dismissed"] = len(log)
                    response["dialog_log"] = log
                return response
            except Exception as e:
                return {"status": "error", "message": str(e), "vba": vba_code}

        return {
            "status": "offline",
            "vba": vba_code,
            "message": "VBA script generated (silent). Execute in CST Studio Suite.",
        }

    def is_solver_running(self) -> bool:
        """Check if a solver is currently running."""
        if self.connected and self._project is not None:
            try:
                return bool(self._project.model3d.is_solver_running())
            except Exception:
                return False
        return False

    def wait_for_solver(self, timeout: float = 600, poll_interval: float = 2.0) -> dict:
        """Wait for a running solver to finish.

        Returns immediately if no solver is running.
        """
        if not self.connected or self._project is None:
            return {"status": "offline"}

        deadline = time.monotonic() + timeout
        while self.is_solver_running():
            if time.monotonic() > deadline:
                return {"status": "error", "message": f"Solver still running after {timeout}s"}
            time.sleep(poll_interval)

        return {"status": "ok"}

    def run_solver(self) -> dict:
        """Run the solver via Python API (no VBA, no history entry).

        Uses ``model3d.run_solver()`` which blocks until complete.
        If a solver is already running, waits for it to finish first.
        """
        if self.connected and self._project is not None:
            try:
                # Wait for any in-progress solver before starting
                if self.is_solver_running():
                    logger.info("Solver already running; waiting for it to finish")
                    wait_result = self.wait_for_solver()
                    if wait_result.get("status") == "error":
                        return wait_result

                result = self._project.model3d.run_solver()
                return {"status": "executed", "result": str(result) if result else "ok"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        return {"status": "offline", "message": "Solver requires connected mode."}

    def start_solver_async(self) -> dict:
        """Start ``model3d.run_solver()`` on a daemon thread and return immediately.

        Does not push ``Solver.Start`` into the history list and does not
        open a VBA ``MsgBox``. Poll :meth:`solver_session_status`.
        """
        if not self.connected or self._project is None:
            return {"status": "offline", "message": "Solver requires connected mode."}

        if self._solver_thread is not None and self._solver_thread.is_alive():
            return {"status": "already_running", "message": "Solver thread is still running."}

        if self.is_solver_running():
            return {
                "status": "already_running",
                "message": "CST reports a solver is already running.",
            }

        def _target() -> None:
            with self._solver_lock:
                self._solver_state = {"status": "running", "started_at": time.time()}
            try:
                result = self._project.model3d.run_solver()
                with self._solver_lock:
                    self._solver_state = {
                        "status": "completed",
                        "result": str(result) if result else "ok",
                        "started_at": self._solver_state.get("started_at"),
                        "finished_at": time.time(),
                    }
            except Exception as exc:
                with self._solver_lock:
                    self._solver_state = {
                        "status": "error",
                        "message": str(exc),
                        "started_at": self._solver_state.get("started_at"),
                        "finished_at": time.time(),
                    }

        self._solver_thread = threading.Thread(
            target=_target, name="cst-solver", daemon=True
        )
        self._solver_thread.start()
        return {
            "status": "started",
            "mode": "async",
            "message": "Solver started in the background. Poll cst_get_simulation_status.",
        }

    def solver_session_status(self) -> dict:
        """Non-blocking solver status plus a short log tail. Never shows a dialog."""
        if not self.connected or self._project is None:
            return {"status": "offline", "message": "Status requires connected mode."}

        with self._solver_lock:
            state = dict(self._solver_state)
        thread_alive = self._solver_thread is not None and self._solver_thread.is_alive()
        api_running = self.is_solver_running()
        if thread_alive or api_running:
            state["status"] = "running"
        elif state.get("status") == "running":
            state["status"] = "completed"
        state["thread_alive"] = thread_alive
        state["api_solver_running"] = api_running

        logs = self.read_project_messages()
        tail = logs.get("latest_log")
        if isinstance(tail, str) and tail:
            state["log_tail"] = tail[-1500:]
            state["log_file"] = logs.get("latest_log_file")
        return {"status": "ok", "solver": state}

    def list_result_tree(self, root: str | None = None, limit: int = 200) -> dict:
        """List result-tree paths via the Python API, not a VBA MsgBox."""
        if not self.connected or self._project is None:
            return {
                "status": "offline",
                "message": "Result tree listing requires connected mode.",
            }

        items: list[str] = []
        errors: list[str] = []
        try:
            raw = self._project.model3d.get_tree_items()
            items.extend(_flatten_tree(raw))
        except Exception as exc:
            errors.append(f"model3d.get_tree_items: {exc}")

        if not items and self._project_path:
            try:
                import cst.results as cst_results  # type: ignore[import-not-found]

                project_file = _open_project_file(cst_results, self._project_path)
                module = project_file.get_3d()
                if hasattr(module, "get_tree_items"):
                    items.extend(_flatten_tree(module.get_tree_items()))
            except Exception as exc:
                errors.append(f"cst.results: {exc}")

        if root:
            needle = root.replace("/", "\\")
            items = [item for item in items if needle in item]
        # Preserve order, drop duplicates.
        seen: set[str] = set()
        unique: list[str] = []
        for item in items:
            if item not in seen:
                seen.add(item)
                unique.append(item)
        truncated = unique[: max(limit, 0)]
        return {
            "status": "ok" if truncated else "empty",
            "root": root,
            "count": len(unique),
            "items": truncated,
            "errors": errors,
        }

    def get_result(
        self,
        tree_path: str,
        run_id: str | int | None = None,
        max_points: int = 201,
        f0: float | None = None,
    ) -> dict:
        """Get a result-tree item as a decimated curve plus an RF summary.

        ``data`` stays a short text preview for older callers. Numeric samples
        are under ``curve``. Reflection traces also get ``summary``.
        """
        if self.connected and self._project is not None:
            if not self._project_path:
                return {
                    "status": "error",
                    "message": "No project path is set; cst.results needs the .cst file.",
                    "tree_path": tree_path,
                }
            try:
                import cst.results as cst_results  # type: ignore[import-not-found]
            except ImportError as exc:
                return {
                    "status": "error",
                    "message": f"cst.results is not importable: {exc}",
                    "tree_path": tree_path,
                }
            try:
                project_file = _open_project_file(cst_results, self._project_path)
                module = project_file.get_3d()
                item = _tree_item(module, tree_path, run_id)
                curve = extract_curve(item, max_points=max_points)
                payload: dict[str, Any] = {
                    "status": "ok",
                    "tree_path": tree_path,
                    "data": _brief(item),
                }
                if run_id is not None:
                    payload["run_id"] = run_id
                if curve:
                    payload["curve"] = curve
                    if _looks_like_reflection(tree_path):
                        payload["summary"] = summarize_reflection(
                            curve["x"],
                            curve["y_re"],
                            curve.get("y_im"),
                            f0=f0,
                        )
                return payload
            except Exception as e:
                return {"status": "error", "message": str(e), "tree_path": tree_path}

        return {
            "status": "offline",
            "tree_path": tree_path,
            "message": "Result retrieval requires connected mode with a completed simulation.",
        }

    def sample_farfield(
        self,
        *,
        frequency_hz: float,
        theta_deg: list[float],
        phi_deg: list[float],
        quantity: str = "realized gain",
        component: str = "Abs",
        radius_m: float = 1.0,
        tree_path: str | None = None,
    ) -> dict:
        """Sample the farfield calculator at explicit angles.

        Follows the CST Python farfield workflow: reset, add evaluation
        points, calculate, get the list. Returns an error naming the missing
        attribute when this CST build does not expose the calculator.
        """
        if not self.connected or self._project is None:
            return {
                "status": "offline",
                "message": (
                    "Farfield sampling requires connected mode. "
                    "The live call is model3d farfield calculator: "
                    "reset, add_list_evaluation_points(theta, phi, radius_m, "
                    "'spherical', frequency_hz), calculate_list, get_list."
                ),
                "quantity": quantity,
                "frequency_hz": frequency_hz,
            }
        calc = _lookup_farfield_calculator(self._project.model3d)
        if calc is None:
            return {
                "status": "error",
                "message": (
                    "model3d has no farfield calculator. Looked for "
                    "farfield_calculator, FarfieldCalculator, and "
                    "get_farfield_calculator. Define a farfield monitor and "
                    "use cst_get_farfield, or confirm this CST version exposes "
                    "the Python farfield calculator."
                ),
            }
        try:
            reset = getattr(calc, "reset", None) or getattr(calc, "Reset", None)
            if callable(reset):
                reset()
            add = getattr(calc, "add_list_evaluation_points", None) or getattr(
                calc, "AddListEvaluationPoints", None
            )
            if not callable(add):
                return {
                    "status": "error",
                    "message": "Farfield calculator has no add_list_evaluation_points.",
                }
            try:
                add(theta_deg, phi_deg, radius_m, "spherical", frequency_hz)
            except TypeError:
                add(
                    theta=theta_deg,
                    phi=phi_deg,
                    radius=radius_m,
                    coordinate_system="spherical",
                    frequency=frequency_hz,
                )
            calculate = getattr(calc, "calculate_list", None) or getattr(
                calc, "CalculateList", None
            )
            if callable(calculate):
                source = tree_path or ""
                try:
                    calculate(source, quantity)
                except TypeError:
                    if source:
                        calculate(source)
                    else:
                        calculate()
            getter = getattr(calc, "get_list", None) or getattr(calc, "GetList", None)
            if not callable(getter):
                return {"status": "error", "message": "Farfield calculator has no get_list."}
            try:
                raw = getter(quantity, component)
            except TypeError:
                raw = getter(quantity)
            values = [float(v) for v in list(raw)]
        except Exception as exc:
            return {"status": "error", "message": str(exc), "quantity": quantity}

        peak = max(values) if values else None
        return {
            "status": "ok",
            "quantity": quantity,
            "component": component,
            "frequency_hz": frequency_hz,
            "radius_m": radius_m,
            "theta_deg": theta_deg,
            "phi_deg": phi_deg,
            "values": values,
            "peak": peak,
            "n": len(values),
        }

    def tune_step(
        self,
        params: dict[str, float],
        port: int = 1,
        f0: float | None = None,
        max_points: int = 201,
    ) -> dict:
        """One RF iteration: store, delete results, rebuild, solve, read S.

        Blocking. Use this when the agent is ready to wait for a single solve.
        """
        solved = self.set_params_rebuild_solve(params, export_path=None, port=port)
        if solved.get("status") != "ok":
            return solved
        tree_path = f"1D Results\\S-Parameters\\S{port},{port}"
        curve = self.get_result(tree_path, max_points=max_points, f0=f0)
        return {
            "status": "ok",
            "params": params,
            "port": port,
            "tree_path": tree_path,
            "s_parameter": curve,
            "verdict": (curve.get("summary") or {}).get("verdict"),
        }

    def get_project_units(self) -> dict:
        """Read length and frequency units. Never assume millimeters."""
        if not self.connected or self._project is None:
            return {
                "status": "offline",
                "length": None,
                "frequency": None,
                "message": (
                    "Units are unknown offline. Do not assume millimeters or GHz. "
                    "Geometry tools do not convert units."
                ),
            }
        parsed = _parse_units(getattr(self._project.model3d, "units", None))
        if parsed:
            return {"status": "ok", "source": "model3d.units", **parsed}
        try:
            import cst.units as cst_units  # type: ignore[import-not-found]
        except ImportError:
            cst_units = None
        if cst_units is not None:
            parsed = _parse_units(cst_units)
            if parsed:
                return {"status": "ok", "source": "cst.units", **parsed}
        return {
            "status": "error",
            "length": None,
            "frequency": None,
            "message": "Could not read project units.",
            "looked_for": ["model3d.units", "cst.units"],
        }

    def capture_3d_view(self, filename: str | None = None) -> dict:
        """Write a 3D view image under the work directory. No history entry.

        The image bytes are not returned. Success requires a non-empty file.
        """
        if not self.connected or self._project is None:
            return {
                "status": "offline",
                "message": (
                    "3D view capture requires connected mode. "
                    "Looked-for writers: model3d.export_image, ExportImage, "
                    "save_image, SaveImage, export_screenshot, and the same "
                    "names on model3d.plot."
                ),
                "looked_for": _VIEW_WRITER_NAMES,
            }
        try:
            path = _work_file(self._config.work_dir, filename, ".png", "cst_3d_view.png")
        except (ValidationError, ValueError) as exc:
            return {"status": "error", "message": str(exc)}

        m3d = self._project.model3d
        looked: list[str] = []
        writers: list[Any] = []
        writers.extend(_collect_callables(m3d, _VIEW_METHOD_NAMES, "model3d", looked))
        plot = getattr(m3d, "plot", None)
        if plot is not None:
            writers.extend(_collect_callables(plot, _VIEW_METHOD_NAMES, "model3d.plot", looked))
        last_error = None
        for writer in writers:
            try:
                writer(path)
            except TypeError:
                try:
                    writer(filename=path)
                except Exception as exc:
                    last_error = str(exc)
                    continue
            except Exception as exc:
                last_error = str(exc)
                continue
            if os.path.isfile(path) and os.path.getsize(path) > 0:
                return {
                    "status": "ok",
                    "path": path,
                    "bytes": os.path.getsize(path),
                }
        return {
            "status": "error",
            "message": "3D view export did not write a non-empty file.",
            "looked_for": looked,
            "path": path,
            "last_error": last_error,
        }

    def sample_vector_field(
        self,
        tree_path: str,
        points: list[list[float]],
        max_points: int = 200,
    ) -> dict:
        """Sample a 3D vector monitor at explicit points. Does not return a volume."""
        if len(points) > max_points:
            return {
                "status": "error",
                "message": f"{len(points)} points exceeds the cap of {max_points}.",
            }
        if not self.connected or self._project is None:
            return {
                "status": "offline",
                "message": "Vector field sampling requires connected mode.",
                "call": [
                    "vector_plot_3d.reset()",
                    "vector_plot_3d.set_points([[x, y, z], ...])",
                    "vector_plot_3d.calculate_list(tree_path)",
                    "vector_plot_3d.get_list()  # Re/Im of the three components",
                ],
                "tree_path": tree_path,
                "n_points": len(points),
            }
        plot, looked = _lookup_named(
            self._project.model3d,
            ("vector_plot_3d", "VectorPlot3D", "get_vector_plot_3d"),
        )
        if plot is None:
            return {
                "status": "error",
                "message": "model3d has no 3D vector plot.",
                "looked_for": looked,
            }
        try:
            reset = getattr(plot, "reset", None) or getattr(plot, "Reset", None)
            if callable(reset):
                reset()
            setter = getattr(plot, "set_points", None) or getattr(plot, "SetPoints", None)
            if not callable(setter):
                return {"status": "error", "message": "Vector plot has no set_points."}
            setter(points)
            calculate = getattr(plot, "calculate_list", None) or getattr(
                plot, "CalculateList", None
            )
            if not callable(calculate):
                return {"status": "error", "message": "Vector plot has no calculate_list."}
            calculate(tree_path)
            getter = getattr(plot, "get_list", None) or getattr(plot, "GetList", None)
            if not callable(getter):
                return {"status": "error", "message": "Vector plot has no get_list."}
            raw = getter()
            samples = parse_complex_vectors(raw, n_components=3)
        except Exception as exc:
            return {"status": "error", "message": str(exc), "tree_path": tree_path}
        return {
            "status": "ok",
            "tree_path": tree_path,
            "n": len(samples),
            "samples": samples,
            "peak": peak_sample(samples),
        }

    def export_monitor_hdf5(
        self,
        tree_path: str,
        mode: str,
        filename: str | None = None,
    ) -> dict:
        """Ask CST to write one 3D monitor to HDF5. The volume is not returned."""
        if mode not in ("mesh", "grid"):
            return {"status": "error", "message": "mode must be 'mesh' or 'grid'."}
        if not self.connected or self._project is None:
            return {
                "status": "offline",
                "message": "HDF5 monitor export requires connected mode.",
                "call": [
                    "result_3d.export_hdf5(path, mode)",
                    "mode is 'mesh' (native mesh) or 'grid' (uniform grid)",
                ],
                "tree_path": tree_path,
                "mode": mode,
            }
        result_3d, looked = _lookup_named(
            self._project.model3d,
            ("result_3d", "Result3D", "get_result_3d"),
        )
        if result_3d is None:
            return {
                "status": "error",
                "message": "model3d has no Result3D exporter.",
                "looked_for": looked,
            }
        try:
            path = _work_file(
                self._config.work_dir,
                filename,
                ".h5",
                "cst_monitor.h5",
            )
        except (ValidationError, ValueError) as exc:
            return {"status": "error", "message": str(exc)}
        exporter = (
            getattr(result_3d, "export_hdf5", None)
            or getattr(result_3d, "ExportHDF5", None)
            or getattr(result_3d, "export_to_hdf5", None)
        )
        if not callable(exporter):
            return {
                "status": "error",
                "message": "Result3D has no export_hdf5.",
                "looked_for": ["export_hdf5", "ExportHDF5", "export_to_hdf5"],
            }
        try:
            try:
                exporter(path, mode, tree_path)
            except TypeError:
                exporter(path, mode)
        except Exception as exc:
            return {"status": "error", "message": str(exc), "path": path}
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            return {
                "status": "error",
                "message": "HDF5 export did not write a non-empty file.",
                "path": path,
                "tree_path": tree_path,
                "mode": mode,
            }
        return {
            "status": "ok",
            "path": path,
            "bytes": os.path.getsize(path),
            "tree_path": tree_path,
            "mode": mode,
        }

    def export_result(self, tree_path: str, filepath: str) -> dict:
        """Export a result tree item to CSV via Python API (no history entry).

        Uses ``model3d.SelectTreeItem()`` + ``model3d.ASCIIExport`` Python
        methods directly: avoids VBA and history bloat.  Works regardless of
        the current CST view state.

        Validates that the output file was actually created after export.
        """
        if self.connected and self._project is not None:
            try:
                # Remove stale file if it exists
                safe_path = filepath.replace("\\", "/")
                if os.path.exists(safe_path):
                    os.remove(safe_path)

                m3d = self._project.model3d
                m3d.SelectTreeItem(tree_path)
                ae = m3d.ASCIIExport
                ae.Reset()
                ae.FileName(safe_path)
                ae.SetFileType("csv")
                ae.Execute()

                # Validate the file was actually created
                if not os.path.exists(safe_path):
                    return {
                        "status": "error",
                        "message": (
                            f"Export completed but file not found at "
                            f"'{safe_path}'. The tree item '{tree_path}' "
                            "may not exist or may be empty."
                        ),
                    }

                # Check file is non-empty
                if os.path.getsize(safe_path) == 0:
                    return {
                        "status": "error",
                        "message": (
                            f"Export produced empty file at '{safe_path}'. "
                            f"Tree item '{tree_path}' may have no data."
                        ),
                    }

                return {"status": "exported", "path": filepath}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        return {
            "status": "offline",
            "tree_path": tree_path,
            "message": "Result export requires connected mode.",
        }

    def delete_results(self) -> dict:
        """Delete solver results via ``model3d.DeleteResults()``.

        This is critical before rebuilding with new parameters: without
        deleting results first, the solver may return cached/stale data
        even after a ``Rebuild()``.

        Also dismisses any CST dialogs that may appear.
        """
        if not self.connected or self._project is None:
            return {"status": "offline", "message": "Delete results requires connected mode."}

        try:
            self._project.model3d.DeleteResults()
        except Exception as e:
            logger.warning("DeleteResults error (non-fatal): %s", e)

        # Dismiss any dialogs that may have appeared
        dismissed = self.dismiss_dialogs()
        return {"status": "ok", "method": "python_api", **dismissed}

    def set_params_rebuild_solve(
        self,
        params: dict[str, float],
        export_path: str | None = None,
        port: int = 1,
    ) -> dict:
        """Set parameters, rebuild geometry, solve, and optionally export S11.

        Uses the Python API directly (no VBA, no history entries).  The
        correct sequence to get fresh results after a parameter change is:

        1. ``StoreParameter``: update parameter table
        2. ``DeleteResults``: clear cached solver results
        3. ``Rebuild``: rebuild geometry from history with new values
        4. ``run_solver``. Run a fresh simulation
        5. (optional) ``ASCIIExport``: export S-parameter data

        Without ``DeleteResults`` before ``Rebuild``, the solver returns
        stale cached data even though the parameter values have changed.

        Returns dict with status and optional export path.
        """
        if not self.connected or self._project is None:
            return {"status": "offline", "message": "Requires connected mode."}

        m3d = self._project.model3d

        try:
            # 1. Store parameters
            for name, value in params.items():
                m3d.StoreParameter(name, str(value))

            # 2. Delete old results (critical!)
            m3d.DeleteResults()

            # 3. Dismiss any dialogs
            self.dismiss_dialogs()

            # 4. Rebuild geometry
            m3d.Rebuild()

            # 5. Dismiss any post-rebuild dialogs
            self.dismiss_dialogs()

            # 6. Run solver
            if self.is_solver_running():
                wait_result = self.wait_for_solver()
                if wait_result.get("status") == "error":
                    return wait_result
            m3d.run_solver()

            # 7. Export if requested
            if export_path:
                import os
                if os.path.exists(export_path):
                    os.remove(export_path)
                tree_path = f"1D Results\\S-Parameters\\S{port},{port}"
                m3d.SelectTreeItem(tree_path)
                ae = m3d.ASCIIExport
                ae.Reset()
                ae.FileName(export_path.replace("\\", "/"))
                ae.SetFileType("csv")
                ae.Execute()

            return {"status": "ok", "params": params, "export_path": export_path}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def read_project_messages(self) -> dict:
        """Read solver log and project status information.

        Scans the project results directory for log files and returns
        their contents along with current solver state.
        """
        info: dict[str, Any] = {"solver_running": False}

        if not self.connected or self._project is None:
            return {"status": "offline", "message": "Requires connected mode."}

        info["solver_running"] = self.is_solver_running()
        info["project_path"] = self._project_path

        if not self._project_path:
            return {"status": "ok", **info}

        # CST stores results in a directory alongside the .cst file
        # e.g. "Project.cst" -> "Project/Result/"
        project_base = self._project_path.replace(".cst", "")
        candidate_dirs = [
            os.path.join(project_base, "Result"),
            project_base,
        ]

        log_files: list[str] = []
        for d in candidate_dirs:
            if os.path.isdir(d):
                try:
                    for fname in os.listdir(d):
                        lower = fname.lower()
                        if "log" in lower or "solver" in lower or lower.endswith(".log"):
                            log_files.append(os.path.join(d, fname))
                except OSError:
                    continue

        if log_files:
            info["log_files"] = log_files
            try:
                newest = max(log_files, key=os.path.getmtime)
                with open(newest, "r", errors="replace") as f:
                    content = f.read()
                # Return last 5000 chars to keep response manageable
                info["latest_log"] = content[-5000:] if len(content) > 5000 else content
                info["latest_log_file"] = newest
            except OSError:
                pass

        return {"status": "ok", **info}

    # -- dialog management --

    _dialog_watcher: DialogWatcher | None = None

    def dismiss_dialogs(self) -> dict:
        """Find and dismiss any visible CST dialog windows.

        Returns details of each dialog that was dismissed (title, text,
        action taken).  Uses Win32 API on Windows; no-op on other platforms.
        """
        dismissed = dismiss_cst_dialogs()
        if dismissed:
            return {"status": "dismissed", "count": len(dismissed), "dialogs": dismissed}
        return {"status": "ok", "message": "No CST dialogs found."}

    def read_dialogs(self) -> dict:
        """Read (but don't dismiss) any visible CST dialog windows."""
        dialogs = find_cst_dialogs()
        # Strip hwnd for serialisation
        for d in dialogs:
            d.pop("hwnd", None)
        if dialogs:
            return {"status": "found", "count": len(dialogs), "dialogs": dialogs}
        return {"status": "ok", "message": "No CST dialogs found."}

    def start_dialog_watcher(self) -> dict:
        """Start background thread that auto-dismisses CST dialogs."""
        if CSTClient._dialog_watcher is not None and CSTClient._dialog_watcher.running:
            return {"status": "already_running"}
        CSTClient._dialog_watcher = DialogWatcher(poll_interval=0.5)
        CSTClient._dialog_watcher.start()
        return {"status": "started"}

    def stop_dialog_watcher(self) -> dict:
        """Stop the background dialog watcher and return its log."""
        if CSTClient._dialog_watcher is None or not CSTClient._dialog_watcher.running:
            return {"status": "not_running"}
        log = CSTClient._dialog_watcher.get_log()
        CSTClient._dialog_watcher.stop()
        return {"status": "stopped", "dismissed_count": len(log), "log": log}

    def get_dialog_log(self) -> dict:
        """Get log of dialogs auto-dismissed by the watcher."""
        if CSTClient._dialog_watcher is None:
            return {"status": "not_running", "log": []}
        log = CSTClient._dialog_watcher.get_log()
        return {"status": "ok", "count": len(log), "log": log}

    def status(self) -> dict:
        """Get current client status."""
        return {
            "mode": self.mode,
            "cst_available": CST_AVAILABLE,
            "cst_path": self._config.cst_path,
            "cst_version": self._config.version,
            "work_dir": self._config.work_dir,
            "project_open": self.has_project,
            "project_path": self._project_path,
            "dialog_watcher": (
                CSTClient._dialog_watcher is not None
                and CSTClient._dialog_watcher.running
            ),
        }


def _flatten_tree(raw: Any, depth: int = 0) -> list[str]:
    """Turn a CST tree listing into path strings. Ignore arbitrary objects."""
    if depth > 8 or raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, (list, tuple)):
        out: list[str] = []
        for item in raw:
            out.extend(_flatten_tree(item, depth + 1))
        return out
    text = getattr(raw, "treepath", None) or getattr(raw, "path", None)
    if isinstance(text, str):
        return [text]
    return []


def _open_project_file(cst_results: Any, path: str) -> Any:
    try:
        return cst_results.ProjectFile(path, allow_interactive=True)
    except TypeError:
        return cst_results.ProjectFile(path)


def _tree_item(module: Any, tree_path: str, run_id: str | int | None) -> Any:
    getter = module.get_tree_item
    if run_id is None:
        return getter(tree_path)
    try:
        return getter(tree_path, run_id)
    except TypeError:
        return getter(tree_path)


def _brief(item: Any) -> str:
    text = str(item)
    if len(text) > 500:
        return text[:500] + "..."
    return text


def _looks_like_reflection(tree_path: str) -> bool:
    lowered = tree_path.lower()
    return "s-parameter" in lowered or "vswr" in lowered


def _lookup_farfield_calculator(model3d: Any) -> Any | None:
    for name in ("farfield_calculator", "FarfieldCalculator"):
        obj = getattr(model3d, name, None)
        if obj is not None:
            return obj
    factory = getattr(model3d, "get_farfield_calculator", None)
    if callable(factory):
        try:
            return factory()
        except Exception:
            return None
    return None


_VIEW_METHOD_NAMES = (
    "export_image",
    "ExportImage",
    "save_image",
    "SaveImage",
    "export_screenshot",
)
_VIEW_WRITER_NAMES = [f"model3d.{name}" for name in _VIEW_METHOD_NAMES] + [
    f"model3d.plot.{name}" for name in _VIEW_METHOD_NAMES
]


def _parse_units(raw: Any) -> dict[str, str | None] | None:
    if raw is None or isinstance(raw, (str, bytes, int, float)):
        return None
    if isinstance(raw, dict):
        length = _as_unit_text(raw.get("length") or raw.get("geometry") or raw.get("Length"))
        frequency = _as_unit_text(raw.get("frequency") or raw.get("Frequency"))
        if length or frequency:
            return {"length": length, "frequency": frequency}
        return None
    length = _unit_attr(raw, ("geometry", "length", "Geometry", "Length"))
    frequency = _unit_attr(raw, ("frequency", "Frequency"))
    if length is None and frequency is None:
        getter = (
            getattr(raw, "get_unit", None)
            or getattr(raw, "GetUnit", None)
            or getattr(raw, "get", None)
        )
        if callable(getter):
            length = _call_unit(getter, ("length", "Length", "geometry", "Geometry"))
            frequency = _call_unit(getter, ("frequency", "Frequency"))
    if length or frequency:
        return {"length": length, "frequency": frequency}
    return None


def _unit_attr(raw: Any, names: tuple[str, ...]) -> str | None:
    for name in names:
        text = _as_unit_text(getattr(raw, name, None))
        if text:
            return text
    return None


def _call_unit(getter: Any, names: tuple[str, ...]) -> str | None:
    for name in names:
        try:
            text = _as_unit_text(getter(name))
        except Exception:
            continue
        if text:
            return text
    return None


def _as_unit_text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _work_file(work_dir: str, filename: str | None, suffix: str, default_name: str) -> str:
    if not work_dir:
        raise ValueError("CST_WORK_DIR is not set, so the file has nowhere safe to go.")
    name = filename or default_name
    if name != os.path.basename(name.replace("\\", "/")):
        raise ValueError("filename must be a base name, not a path")
    if ".." in name:
        raise ValueError("Path traversal ('..') is not allowed")
    if not name.lower().endswith(suffix):
        name += suffix
    path = os.path.join(work_dir, name)
    return validate_file_path(path, work_dir)


def _collect_callables(obj: Any, names: tuple[str, ...], prefix: str, looked: list[str]) -> list[Any]:
    found: list[Any] = []
    for name in names:
        looked.append(f"{prefix}.{name}")
        fn = getattr(obj, name, None)
        if callable(fn):
            found.append(fn)
    return found


def _lookup_named(model3d: Any, names: tuple[str, ...]) -> tuple[Any | None, list[str]]:
    looked = [f"model3d.{name}" for name in names]
    for name in names:
        obj = getattr(model3d, name, None)
        if obj is None:
            continue
        if name.startswith("get_") and callable(obj):
            try:
                return obj(), looked
            except Exception:
                continue
        return obj, looked
    return None, looked

