# CST Studio MCP Server: Development Guide

## Architecture

- **Dual-mode**: Connected (Windows+CST) and Offline (any OS, generates VBA scripts)
- **VBA Builder pattern**: All VBA generated via `vba_builder.py`: never use raw f-strings for VBA
- **Modular tools**: Each `tools/*.py` exports `TOOLS` list + `handle()` function + `register_*_tools()`
- **ToolRegistry**: `tools/__init__.py` collects all tools via `_registry.add_module(TOOLS, handle, client)` and wires single `list_tools`/`call_tool` handlers
- **Offline-first**: Server works fully on Linux/macOS. VBA scripts generated for manual execution in CST

## Key Files

| File | Purpose |
|------|---------|
| `types.py` | Enums and dataclasses (ProjectType, SolverType, MeshType, etc.) |
| `config.py` | Env vars, CST path auto-detection |
| `validators.py` | Input validation, VBA injection prevention |
| `vba_builder.py` | Safe VBA code generation (VBABuilder + VBAScript classes) |
| `cst_client.py` | Session manager (connected/offline modes) |
| `server.py` | MCP entry point, stdio transport |
| `tools/__init__.py` | ToolRegistry aggregator, register_all_tools() |
| `data/` | JSON material databases, antenna templates, VBA reference |

## Tool Categories (170 tools)

| Module | Tools | Description |
|--------|-------|-------------|
| project.py | 8 | Create, open, save, close, export, status |
| geometry.py | 13 | Brick, cylinder, sphere, cone, torus, extrude, loft, wire, polygon |
| boolean.py | 4 | Add, subtract, intersect, insert |
| transforms.py | 4 | Translate, rotate, mirror, scale |
| materials.py | 8 | Create, load, list, assign, lossy metal, anisotropic |
| ports.py | 7 | Waveguide, discrete, lumped, plane wave, Floquet, list, delete |
| boundaries.py | 4 | Boundary conditions, background, symmetry, frequency range |
| mesh.py | 5 | Mesh type, density, refinement, adaptive, info |
| solvers.py | 5 | Time domain, frequency domain, eigenmode, integral equation, info |
| simulation.py | 6 | Run, run_async, status, pause, resume, stop |
| results.py | 10 | S-params, farfield, field monitor, impedance, VSWR, gain, efficiency |
| import_export.py | 5 | CAD import/export, Touchstone, farfield |
| parameters.py | 6 | Set, get, list, delete, sweep, optimize |
| antenna_templates.py | 13 | Parametric designs: patch, dipole, monopole, horn, Yagi, helix, etc. |
| pcb.py | 6 | Stackup, traces, vias, ground planes, Gerber import |
| vba.py | 3 | Raw VBA execution, help reference, object listing |

## Adding a New Tool

1. Add `Tool()` definition to the module's `TOOLS` list with proper inputSchema
2. Add handler in the module's `handle()` function (inside the try/except)
3. Use `VBABuilder` for all VBA generation: never raw f-strings
4. Validate all inputs via `validators.py` functions
5. Return `list[TextContent]` with JSON response
6. Register in `tools/__init__.py` via `register_*_tools()`

### Adding a New Tool Module

1. Create `tools/new_category.py` with `TOOLS`, `handle()`, and `register_*_tools()`
2. Follow the pattern: try/except in handle(), error format `{"status": "error", "message": "..."}`
3. Import and call `register_*_tools()` in `tools/__init__.py:register_all_tools()`
4. Add tests in `tests/test_tools_new_category.py`

## Error Handling Contract

All `handle()` functions return consistent error format:
```json
{"status": "error", "message": "Human-readable error description"}
```

- Every `handle()` must wrap its body in `try/except Exception as e`
- Internal validation errors (e.g., bad enum value) return the same format
- Never raise exceptions from handle(): always return TextContent with error JSON

## Security Rules

- All VBA passes through `validate_vba_input()`: blocks Shell, CreateObject, file I/O, Declare, SendKeys
- All file paths checked for traversal (`..`) via `validate_file_path()`
- All names restricted to `[A-Za-z_][A-Za-z0-9_ .-]*` via `validate_name()`
- Component paths validated via `validate_component_path()`
- VBA strings escaped via `_escape_vba_string()`: blocks concatenation injection
- No hardcoded paths: everything via env vars or auto-detection

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

Tests run in offline mode. No CST installation needed. The offline client returns `{"status": "offline", "vba": code}` for all execute_vba calls.

### Test Pattern
```python
@pytest.mark.asyncio
async def test_tool(client: CSTClient):
    from mcp_cst_studio.tools.module import handle
    result = await handle("cst_tool_name", {args}, client)
    data = json.loads(result[0].text)
    assert "vba" in data or "status" in data
```

## RF Engineering References

- Patch antenna dimensions: Balanis Ch. 14, Hammerstad-Jensen effective permittivity (Eq. 14-1)
- Microstrip impedance: Wheeler synthesis (narrow/wide strip regimes)
- Stripline impedance: Cohn formula (Z0 = 94.25/sqrt(eps_r) * ...)
- Yagi design: reflector 0.20λ spacing, directors 0.25λ spacing
- Helix gain: Kraus formula (C²NS/λ³)
- Horn gain: aperture efficiency formula

## Build & Run

```bash
pip install -e .
mcp-cst-studio  # runs stdio server
```

Environment variables:
- `CST_PATH`: CST installation directory (auto-detected on Windows)
- `CST_WORK_DIR`: Working directory for projects (default: ~/cst_projects)
- `CST_VERSION`: CST version year (default: 2026)
