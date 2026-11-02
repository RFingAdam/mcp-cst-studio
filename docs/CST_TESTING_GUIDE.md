# CST Studio Connected Mode Testing Guide

This guide is for testing the MCP server with a live CST Studio Suite installation on Windows.

## Environment Setup

### 1. Install Python and the MCP Server

```powershell
# Python 3.10+ required
python --version

# Clone and install
git clone https://github.com/RFingAdam/mcp-cst-studio.git
cd mcp-cst-studio
pip install -e ".[dev]"
```

### 2. Configure CST Python Libraries

CST ships its own Python libraries. Add them to your Python path:

```powershell
# Find your CST installation (adjust version year)
$CST_PATH = "C:\Program Files\CST Studio Suite 2026"

# The Windows libraries live here (LinuxAMD64 is the Linux installer layout):
$env:PYTHONPATH = "$CST_PATH\AMD64\python_cst_libraries;$env:PYTHONPATH"

# Verify CST is importable
python -c "import cst.interface; print('OK')"
```

If `cst.interface` fails to import, check:
- CST is installed and licensed
- You ran the one-time link command from Help → Automation and Scripting → Python
  (PYTHONPATH alone is not the supported setup)
- The folder `AMD64\python_cst_libraries` exists in your CST installation
- Your Python version matches CST's (CST 2026 ships Python 3.12)

### 3. Environment Variables

```powershell
$env:CST_PATH = "C:\Program Files\CST Studio Suite 2026"
$env:CST_WORK_DIR = "C:\cst_projects"
$env:CST_VERSION = "2026"
```

### 4. Verify Server Starts

```powershell
mcp-cst-studio
# Should start without errors. Ctrl+C to stop.
```

## Test Sequence

Run these tests in order. Each builds on the previous.

### Phase 1: Connection and Project Management

```
Test 1.1: Check status
  Tool: cst_connection_status
  Expected: mode="connected", cst_available=True

Test 1.2: Create project
  Tool: cst_create_project
  Args: path="C:\cst_projects\test_project.cst", project_type="MWS"
  Expected: Project created, file exists on disk

Test 1.3: Save project
  Tool: cst_save_project
  Expected: Saves without error

Test 1.4: Close and reopen
  Tool: cst_close_project, then cst_open_project with same path
  Expected: Project reopens successfully
```

### Phase 2: Geometry Primitives

```
Test 2.1: Create brick
  Tool: cst_create_brick
  Args: component="component1", name="TestBrick", material="PEC",
        x_min=0, x_max=10, y_min=0, y_max=10, z_min=0, z_max=5
  Expected: Brick visible in CST 3D view

Test 2.2: Create cylinder (Z-axis)
  Tool: cst_create_cylinder
  Args: component="component1", name="CylZ", material="PEC",
        axis="z", outer_radius=5, inner_radius=0,
        center_x=20, center_y=0, center_z=0, range_min=0, range_max=10
  Expected: Cylinder along Z axis

Test 2.3: Create cylinder (X-axis): REGRESSION for issue #22
  Tool: cst_create_cylinder
  Args: component="component1", name="CylX", material="PEC",
        axis="x", outer_radius=5, inner_radius=0,
        center_x=0, center_y=20, center_z=0, range_min=0, range_max=10
  Expected: Cylinder along X axis (NOT Z axis)

Test 2.4: Create sphere
  Tool: cst_create_sphere
  Args: component="component1", name="TestSphere", material="Vacuum",
        center_x=0, center_y=0, center_z=20, radius=5
  Expected: Sphere visible
```

### Phase 3: Transforms: REGRESSION for issue #23

```
Test 3.1: Translate
  Tool: cst_transform_translate
  Args: solid="component1:TestBrick", dx=5, dy=0, dz=0, copy=false
  Expected: Brick moves 5mm in X. VBA uses "Vector" not "Vector X".

Test 3.2: Rotate
  Tool: cst_transform_rotate
  Args: solid="component1:CylZ", axis="z", angle=45
  Expected: Cylinder rotates 45°. VBA uses "OriginX" not "Origin X".

Test 3.3: Mirror
  Tool: cst_transform_mirror
  Args: solid="component1:TestSphere", plane="xy", copy=true
  Expected: Mirrored copy created
```

### Phase 4: Materials

```
Test 4.1: List built-in materials
  Tool: cst_list_materials
  Args: category="metals"
  Expected: Returns copper, aluminum, gold, etc.

Test 4.2: List substrates: REGRESSION for issue #29
  Tool: cst_list_materials
  Args: category="substrates"
  Expected: Returns substrate materials (NOT dielectrics)

Test 4.3: Create custom material
  Tool: cst_create_material
  Args: name="FR4", epsilon=4.3, tan_delta=0.025
  Expected: Material appears in CST material list
```

### Phase 5: Antenna Templates

```
Test 5.1: Patch antenna
  Tool: cst_antenna_patch
  Args: frequency_ghz=2.4, substrate_er=4.3, substrate_height_mm=1.6
  Expected: Complete patch antenna model in CST with:
    - Substrate, ground plane, patch, feed line
    - Waveguide port configured
    - Frequency range set
    - Far-field monitor added

Test 5.2: Horn antenna: REGRESSION for issues #2, #27
  Tool: cst_antenna_horn
  Args: frequency_ghz=10, gain_dbi=15
  Expected:
    - Waveguide section + flared horn
    - Loft interior uses 3D profiles at different Z positions (not both at z=0)
    - Horn length ~3-4λ (reasonable for 15 dBi)

Test 5.3: Yagi antenna: REGRESSION for issue #3
  Tool: cst_antenna_yagi
  Args: frequency_ghz=0.3, num_directors=5
  Expected: Reflector spacing ~0.20λ behind driven element (NOT 0.25λ)

Test 5.4: Slot antenna: REGRESSION for issue #26
  Tool: cst_antenna_slot
  Args: frequency_ghz=5.8
  Expected: Ground plane with slot CUT OUT (Solid.Subtract must execute)
```

### Phase 6: Ports and Excitations

```
Test 6.1: Waveguide port
  Tool: cst_add_waveguide_port
  Args: port_number=1, orientation="zmin", x_min=-5, x_max=5, y_min=-5, y_max=5
  Expected: Port visible on boundary

Test 6.2: Plane wave: REGRESSION for issue #24
  Tool: cst_add_plane_wave
  Args: polarization="linear", theta=0, phi=0
  Expected: VBA sets .Normal "z" and .Polarization "linear" (NOT .Normal "linear")
```

### Phase 7: Simulation

```
Test 7.1: Configure solver
  Tool: cst_configure_time_domain_solver
  Args: accuracy=-40, max_time_steps=20000
  Expected: Solver settings applied

Test 7.2: Run simulation
  Tool: cst_run_simulation
  Args: solver_type="Time Domain"
  Expected: Simulation starts and completes

Test 7.2b: Non-blocking run
  Tool: cst_run_simulation_async
  Args: {}
  Expected: returns immediately with status started. Then cst_get_simulation_status
  returns solver.status running or completed and does not open a MsgBox.

Test 7.3: Get S-parameters
  Tool: cst_get_s_parameters
  Expected: Returns S11 data with frequency/magnitude arrays
```

### Phase 8: Export: REGRESSION for issue #25

```
Test 8.1: Export Touchstone
  Tool: cst_export_result
  Args: result_path="1D Results\\S-Parameters\\S1,1", format="touchstone",
        output_file="C:\\cst_projects\\test.s1p"
  Expected: .s1p file created

Test 8.2: Export CSV
  Tool: cst_export_result
  Args: result_path="1D Results\\S-Parameters\\S1,1", format="csv",
        output_file="C:\\cst_projects\\test.csv"
  Expected: CSV file created using ASCIIExport (NOT blocked by VBA validator)
```

## Known Limitations

- **Issue #16**: Connected mode code paths have no automated tests. This guide IS the test
- VBA execution depends on CST version; some API methods may differ between 2024/2025/2026
- `cst.interface.DesignEnvironment()` requires CST to not already have a running instance in some versions

## Reporting Issues

If a test fails:
1. Note the exact tool name, arguments, and error message
2. Copy the VBA script from the response (`"vba"` field)
3. Try running the VBA manually in CST: Macros > Edit/Run VBA Macro
4. File an issue at https://github.com/RFingAdam/mcp-cst-studio/issues with the above info
