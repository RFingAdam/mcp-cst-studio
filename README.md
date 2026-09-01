<div align="center">

<img src="assets/logo-banner.svg" alt="mcp-cst-studio: CST Studio Suite automation for antenna, RF and PCB" width="100%"/>

</div>

# MCP Server for CST Studio Suite

A Model Context Protocol (MCP) server providing AI-driven access to [CST Studio Suite](https://www.3ds.com/products/simulia/cst-studio-suite) for antenna design, RF/microwave simulation, and PCB layout.

## Features

- **170 tools** across 20 categories: geometry, materials, ports, boundaries, mesh, solvers, simulation, results, parameters, antenna templates, arrays, matching networks, diagnostics, optimization, PCB, and more
- **Dual-mode operation**: Connected mode (direct CST execution on Windows) and Offline mode (VBA script generation on any OS)
- **13 parametric antenna templates**: Patch, dipole, monopole, horn, Yagi, helix, Vivaldi, slot, IFA, PIFA, spiral, bowtie: with automatic dimension calculations from target frequency
- **PCB/SI tools**: Stackup creation, trace routing with impedance calculation, via modeling, ground planes
- **Material database**: 30+ metals, dielectrics, and RF substrates with accurate electromagnetic properties
- **VBA injection prevention**: All generated VBA passes through security validation
- **CST VBA reference**: Built-in help system for CST VBA objects and methods

## Installation

```bash
git clone https://github.com/RFingAdam/mcp-cst-studio.git
cd mcp-cst-studio
pip install -e ".[dev]"
```

## Configuration

### Claude Code (`.mcp.json`)

```json
{
  "mcpServers": {
    "cst-studio": {
      "command": "mcp-cst-studio",
      "env": {
        "CST_PATH": "C:\\Program Files\\CST Studio Suite 2026",
        "CST_WORK_DIR": "C:\\cst_projects"
      }
    }
  }
}
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CST_PATH` | CST installation directory | Auto-detected on Windows |
| `CST_WORK_DIR` | Project working directory | `~/cst_projects` |
| `CST_VERSION` | CST version year | `2026` |

## Usage

### Offline Mode (Any OS)

Works without CST installed. Tools generate VBA scripts that can be executed in CST Studio Suite.

```
"Design a 2.4 GHz rectangular patch antenna on FR-4 substrate"
→ Returns calculated dimensions + complete VBA script for CST
```

### Connected Mode (Windows with CST)

When the CST Python library is available, tools execute directly:

```
"Create the antenna, run the time-domain simulation, and show me the S-parameters"
→ Builds geometry, configures solver, runs simulation, extracts results
```

## Tool Categories

| Category | Tools | Description |
|----------|-------|-------------|
| Project | 8 | Create, open, save, close, export projects |
| Geometry | 13 | Brick, cylinder, sphere, cone, torus, extrude, loft, wire, polygon |
| Boolean | 4 | Add, subtract, intersect, insert operations |
| Transforms | 4 | Translate, rotate, mirror, scale |
| Materials | 15 | Create, load, assign materials; built-in material database; lossy metals; anisotropic |
| Ports | 8 | Waveguide, discrete, lumped, plane wave, Floquet ports |
| Boundaries | 6 | Boundary conditions, background, symmetry, frequency range |
| Mesh | 8 | Mesh type, density, refinement, adaptive meshing, hex/tet controls |
| Solvers | 8 | Time domain, frequency domain, eigenmode, integral equation, asymptotic |
| Simulation | 6 | Run, status, pause, resume, stop simulations |
| Results | 22 | S-parameters, far-field, near-field, impedance, VSWR, gain, efficiency, Smith chart |
| Import/Export | 5 | CAD import/export, Touchstone, far-field export |
| Parameters | 11 | Parametric design, sweeps, expressions, dependencies |
| Antenna Templates | 13 | Parametric antenna designs with RF calculations |
| Arrays | 8 | Linear / planar / circular array synthesis, element factors, beamforming |
| Matching | 8 | L / Pi / T networks, Smith-chart matching, stub matching |
| PCB | 12 | Stackup, traces, vias, ground planes, Gerber import, differential pairs |
| Diagnostics | 5 | Connection status, model integrity, mesh quality, solver convergence |
| Optimization | 3 | Goal-driven sweeps, genetic / gradient optimizers |
| VBA | 3 | Raw VBA execution, help reference, object listing |

## Antenna Templates

Each template calculates dimensions from target frequency and generates a complete, simulatable CST model:

| Template | Type | Typical Gain | Bandwidth |
|----------|------|-------------|-----------|
| Patch | Planar | 5-8 dBi | 1-5% |
| Dipole | Wire | 2.15 dBi | 10-20% |
| Monopole | Wire | 2-5 dBi | 10-20% |
| Horn | Aperture | 10-25 dBi | 50%+ |
| Yagi | Array | 7-15 dBi | 3-5% |
| Helix | Wire | 8-15 dBi | 50%+ |
| Vivaldi | Planar | 5-12 dBi | 100%+ |
| IFA/PIFA | Planar | 1-3 dBi | 5-10% |

## Connected Mode Setup (Windows)

To use with a live CST Studio installation:

### Prerequisites

- Windows 10/11 with CST Studio Suite 2024+ installed
- CST Python libraries on your Python path (typically `C:\Program Files\CST Studio Suite 20XX\LinuxAMD64\python_cst_libraries`)
- Python 3.10+

### Setup

```bash
# 1. Clone and install
git clone https://github.com/RFingAdam/mcp-cst-studio.git
cd mcp-cst-studio
pip install -e .

# 2. Set environment (or let auto-detect find CST)
set CST_PATH=C:\Program Files\CST Studio Suite 2026
set CST_WORK_DIR=C:\cst_projects

# 3. Add CST Python libs to PYTHONPATH
set PYTHONPATH=%CST_PATH%\LinuxAMD64\python_cst_libraries;%PYTHONPATH%

# 4. Verify
python -c "import cst.interface; print('CST available')"
mcp-cst-studio  # starts stdio server
```

### Claude Code / Claude Desktop

Add to your `.mcp.json` or Claude Desktop config:

```json
{
  "mcpServers": {
    "cst-studio": {
      "command": "mcp-cst-studio",
      "env": {
        "CST_PATH": "C:\\Program Files\\CST Studio Suite 2026",
        "CST_WORK_DIR": "C:\\cst_projects",
        "PYTHONPATH": "C:\\Program Files\\CST Studio Suite 2026\\LinuxAMD64\\python_cst_libraries"
      }
    }
  }
}
```

### Validation Checklist

Once connected, verify with these prompts:

1. **Connection**: "What is the CST connection status?": should show `connected` mode
2. **Geometry**: "Create a brick from (0,0,0) to (10,10,5) in component1": should appear in CST
3. **Antenna**: "Design a 2.4 GHz patch antenna on FR-4": should build full model
4. **Simulation**: "Run a time-domain simulation": should start solver
5. **Results**: "Show me the S-parameters": should extract S11 data

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v          # 215 tests, all offline
ruff check src/ tests/    # linting
mypy src/mcp_cst_studio/  # type checking
```

## License

[AGPL-3.0-or-later](LICENSE). Relicensed from Apache-2.0 in v0.2.0 to
align with the eng-mcp-suite toolkit-wide AGPL move. CST Studio Suite
itself (Dassault Systèmes) is a separate commercial product invoked
at runtime; this wrapper does not bundle or redistribute it.
