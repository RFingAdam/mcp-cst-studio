# MCP-CST-Studio Full Agent Test Plan

This is the complete test plan for validating all 107 tools in the MCP-CST-Studio framework against a live CST Studio Suite installation. It is designed to be executed by an AI agent with MCP access to this server.

## Prerequisites

- Windows machine with CST Studio Suite 2024+ installed and licensed
- MCP server running in connected mode (`cst_connection_status` returns `mode: "connected"`)
- Working directory configured (e.g. `C:\cst_projects`)
- CST application closed (the server will control it via the API)

## Execution Notes

- Run tests in order: later phases depend on geometry created in earlier phases
- After each tool call, verify the response contains `"status": "executed"` or `"status": "ok"` (not `"status": "offline"`)
- If any test fails, log the tool name, arguments, response, and any VBA error message
- Tests marked **[REGRESSION]** are verifying fixes for specific bugs: pay extra attention

---

## Phase 1: Connection & Project Management (8 tools)

### Test 1.1: Connection Status
```
Tool: cst_connection_status
Args: {}
PASS if: response.mode == "connected" AND response.cst_available == true
```

### Test 1.2: Create Project
```
Tool: cst_create_project
Args: {
  "path": "C:\\cst_projects\\agent_test.cst",
  "project_type": "MWS"
}
PASS if: status == "created", file exists at path
```

### Test 1.3: Project Info
```
Tool: cst_project_info
Args: {}
PASS if: returns project path and type info
```

### Test 1.4: Save Project
```
Tool: cst_save_project
Args: {}
PASS if: status == "saved"
```

### Test 1.5: Project Tree
```
Tool: cst_project_tree
Args: {}
PASS if: returns tree structure (Components, Materials, etc.)
```

### Test 1.6: Close Project
```
Tool: cst_close_project
Args: {}
PASS if: status == "closed"
```

### Test 1.7: Reopen Project
```
Tool: cst_open_project
Args: {"path": "C:\\cst_projects\\agent_test.cst"}
PASS if: status == "opened"
```

### Test 1.8: Export Project
```
Tool: cst_export_project
Args: {"format": "png"}
PASS if: no error (may require geometry first: acceptable to defer)
```

---

## Phase 2: Geometry Primitives (13 tools)

### Test 2.1: Create Brick
```
Tool: cst_create_brick
Args: {
  "component": "Primitives", "name": "TestBrick", "material": "PEC",
  "x_min": 0, "x_max": 10, "y_min": 0, "y_max": 10, "z_min": 0, "z_max": 5
}
PASS if: VBA executes, brick visible in 3D view
```

### Test 2.2: Create Cylinder (Z-axis)
```
Tool: cst_create_cylinder
Args: {
  "component": "Primitives", "name": "CylZ", "material": "PEC",
  "axis": "z", "outer_radius": 5, "inner_radius": 0,
  "center_x": 25, "center_y": 0, "center_z": 0,
  "range_min": 0, "range_max": 10
}
PASS if: cylinder along Z axis visible
```

### Test 2.3: Create Cylinder (X-axis) [REGRESSION #22]
```
Tool: cst_create_cylinder
Args: {
  "component": "Primitives", "name": "CylX", "material": "PEC",
  "axis": "x", "outer_radius": 3, "inner_radius": 0,
  "center_x": 0, "center_y": 25, "center_z": 0,
  "range_min": 0, "range_max": 15
}
PASS if: cylinder extends along X axis (NOT Z). Verify visually.
FAIL if: cylinder extends along Z despite axis="x"
```

### Test 2.4: Create Cylinder (Y-axis) [REGRESSION #22]
```
Tool: cst_create_cylinder
Args: {
  "component": "Primitives", "name": "CylY", "material": "PEC",
  "axis": "y", "outer_radius": 3, "inner_radius": 0,
  "center_x": 0, "center_y": 0, "center_z": 25,
  "range_min": 0, "range_max": 15
}
PASS if: cylinder extends along Y axis
```

### Test 2.5: Create Cone
```
Tool: cst_create_cone
Args: {
  "component": "Primitives", "name": "TestCone", "material": "PEC",
  "axis": "z", "bottom_radius": 5, "top_radius": 2,
  "center_x": -25, "center_y": 0, "center_z": 0,
  "range_min": 0, "range_max": 10
}
PASS if: cone visible
```

### Test 2.6: Create Sphere
```
Tool: cst_create_sphere
Args: {
  "component": "Primitives", "name": "TestSphere", "material": "Vacuum",
  "center_x": 0, "center_y": 0, "center_z": 30, "radius": 5
}
PASS if: sphere visible
```

### Test 2.7: Create Torus
```
Tool: cst_create_torus
Args: {
  "component": "Primitives", "name": "TestTorus", "material": "PEC",
  "axis": "z", "center_x": 0, "center_y": -25, "center_z": 0,
  "outer_radius": 8, "inner_radius": 3
}
PASS if: torus visible
```

### Test 2.8: Create ECylinder
```
Tool: cst_create_ecylinder
Args: {
  "component": "Primitives", "name": "TestECyl", "material": "PEC",
  "axis": "z", "x_radius": 6, "y_radius": 3,
  "center_x": 50, "center_y": 0, "center_z": 0,
  "range_min": 0, "range_max": 8
}
PASS if: elliptical cylinder visible
```

### Test 2.9: Create Wire
```
Tool: cst_create_wire
Args: {
  "component": "Primitives", "name": "TestWire",
  "x1": 0, "y1": 0, "z1": -20,
  "x2": 0, "y2": 0, "z2": -10,
  "radius": 0.5
}
PASS if: wire visible
```

### Test 2.10: Create Polygon3D
```
Tool: cst_create_polygon3d
Args: {
  "name": "TestPoly", "curve": "Curves1",
  "points": [[0,0,0], [10,0,0], [10,10,0], [0,10,0], [0,0,0]]
}
PASS if: polygon curve created
```

### Test 2.11: Create Extrude
```
Tool: cst_create_extrude
Args: {
  "component": "Primitives", "name": "Extruded",
  "curve": "Curves1", "curve_item": "TestPoly",
  "material": "PEC", "height": 3
}
PASS if: extruded solid created from polygon
```

### Test 2.12: Create Analytical Curve
```
Tool: cst_create_analytical_curve
Args: {
  "name": "Helix", "curve": "Curves1",
  "x_expr": "5*cos(t*360)", "y_expr": "5*sin(t*360)", "z_expr": "t*20",
  "t_min": 0, "t_max": 3, "n_points": 100
}
PASS if: helical curve visible
```

### Test 2.13: Create Polygon Extrude
```
Tool: cst_create_polygon_extrude
Args: {
  "component": "Primitives", "name": "PolyExt", "material": "PEC",
  "points": [[-5,-5], [5,-5], [5,5], [-5,5]],
  "height": 2,
  "center_x": -25, "center_y": -25, "center_z": 0
}
PASS if: extruded polygon solid visible
```

---

## Phase 3: Boolean Operations (4 tools)

### Test 3.1: Boolean Add
```
Tool: cst_create_brick (create two overlapping bricks first)
  Args: component="BoolTest", name="A", material="PEC", x=[0,10], y=[0,10], z=[0,5]
  Args: component="BoolTest", name="B", material="PEC", x=[5,15], y=[5,15], z=[0,5]

Tool: cst_boolean_add
Args: {"solid_1": "BoolTest:A", "solid_2": "BoolTest:B"}
PASS if: single merged solid remains
```

### Test 3.2: Boolean Subtract
```
Tool: cst_create_brick (two more bricks)
  Args: component="BoolTest", name="C", material="PEC", x=[20,35], y=[0,15], z=[0,5]
  Args: component="BoolTest", name="D", material="PEC", x=[25,30], y=[5,10], z=[0,5]

Tool: cst_boolean_subtract
Args: {"solid_1": "BoolTest:C", "solid_2": "BoolTest:D"}
PASS if: brick C has rectangular hole from D
```

### Test 3.3: Boolean Intersect
```
Tool: cst_create_brick + cst_create_sphere (overlapping)
  brick: component="BoolTest", name="E", x=[40,55], y=[0,15], z=[0,15]
  sphere: component="BoolTest", name="F", center=(47.5, 7.5, 7.5), radius=10

Tool: cst_boolean_intersect
Args: {"solid_1": "BoolTest:E", "solid_2": "BoolTest:F"}
PASS if: only intersection region remains
```

### Test 3.4: Boolean Insert
```
Tool: cst_create_brick (two more)
  Args: component="BoolTest", name="G", material="PEC", x=[60,75], y=[0,15], z=[0,5]
  Args: component="BoolTest", name="H", material="Vacuum", x=[65,70], y=[5,10], z=[0,5]

Tool: cst_boolean_insert
Args: {"solid_1": "BoolTest:G", "solid_2": "BoolTest:H"}
PASS if: H inserted into G (different material region)
```

---

## Phase 4: Transforms (4 tools) [REGRESSION #23]

### Test 4.1: Translate
```
Tool: cst_transform_translate
Args: {"solid": "Primitives:TestBrick", "dx": 5, "dy": 0, "dz": 0, "copy": false}
PASS if: brick moves 5mm in X. No VBA error about property names.
```

### Test 4.2: Rotate
```
Tool: cst_transform_rotate
Args: {"solid": "Primitives:CylZ", "axis": "z", "angle": 45, "copy": false}
PASS if: cylinder rotates. VBA uses "OriginX" not "Origin X".
```

### Test 4.3: Mirror
```
Tool: cst_transform_mirror
Args: {"solid": "Primitives:TestSphere", "plane": "xy", "copy": true}
PASS if: mirrored copy created
```

### Test 4.4: Scale
```
Tool: cst_transform_scale
Args: {"solid": "Primitives:TestTorus", "sx": 2, "sy": 2, "sz": 1, "copy": false}
PASS if: torus scaled 2x in X/Y
```

---

## Phase 5: Materials (8 tools)

### Test 5.1: List Materials (metals)
```
Tool: cst_list_materials
Args: {"category": "metals"}
PASS if: returns list with copper, aluminum, gold, etc.
```

### Test 5.2: List Materials (substrates) [REGRESSION #29]
```
Tool: cst_list_materials
Args: {"category": "substrates"}
PASS if: returns substrate data (NOT identical to dielectrics)
```

### Test 5.3: Get Material Info
```
Tool: cst_get_material_info
Args: {"name": "Copper"}
PASS if: returns conductivity ~5.8e7, mu_r=1
```

### Test 5.4: Create Material
```
Tool: cst_create_material
Args: {"name": "TestDielectric", "epsilon": 4.3, "mu": 1, "tan_delta": 0.02}
PASS if: material created in CST
```

### Test 5.5: Create Lossy Metal
```
Tool: cst_create_lossy_metal
Args: {"name": "TestLossy", "conductivity": 1e6}
PASS if: lossy metal material created
```

### Test 5.6: Load Material
```
Tool: cst_load_material
Args: {"name": "Copper"}
PASS if: copper loaded from built-in database
```

### Test 5.7: Assign Material
```
Tool: cst_assign_material
Args: {"solid": "Primitives:TestBrick", "material": "TestDielectric"}
PASS if: brick material changed
```

### Test 5.8: Delete Material
```
Tool: cst_delete_material
Args: {"name": "TestLossy"}
PASS if: material removed
```

---

## Phase 6: Ports & Excitations (7 tools)

First, create a simple test structure: save current project, create new one.

```
Tool: cst_save_project
Tool: cst_close_project
Tool: cst_create_project
Args: {"path": "C:\\cst_projects\\port_test.cst", "project_type": "MWS"}
```

Create a waveguide structure:
```
Tool: cst_create_brick
Args: component="WG", name="Waveguide", material="PEC",
      x_min=-11.43, x_max=11.43, y_min=-5.08, y_max=5.08, z_min=0, z_max=50

Tool: cst_create_brick
Args: component="WG", name="Interior", material="Vacuum",
      x_min=-10.16, x_max=10.16, y_min=-3.81, y_max=3.81, z_min=0, z_max=50

Tool: cst_boolean_subtract
Args: {"solid_1": "WG:Waveguide", "solid_2": "WG:Interior"}
```

### Test 6.1: Waveguide Port
```
Tool: cst_add_waveguide_port
Args: {"port_number": 1, "orientation": "zmin",
       "x_min": -10.16, "x_max": 10.16, "y_min": -3.81, "y_max": 3.81}
PASS if: port visible on zmin face
```

### Test 6.2: Waveguide Port (output)
```
Tool: cst_add_waveguide_port
Args: {"port_number": 2, "orientation": "zmax",
       "x_min": -10.16, "x_max": 10.16, "y_min": -3.81, "y_max": 3.81}
PASS if: second port on zmax face
```

### Test 6.3: Plane Wave [REGRESSION #24]
```
Tool: cst_add_plane_wave
Args: {"polarization": "linear", "theta": 0, "phi": 0}
PASS if: VBA contains .Normal "z" AND .Polarization "linear"
FAIL if: VBA contains .Normal "linear"
```

### Test 6.4: Discrete Port
```
Tool: cst_add_discrete_port
Args: {"port_number": 3, "x1": 0, "y1": 0, "z1": 0, "x2": 0, "y2": 0, "z2": 1,
       "impedance": 50}
PASS if: discrete port created
```

### Test 6.5: Lumped Element
```
Tool: cst_add_lumped_element
Args: {"name": "TestR", "type": "R", "value": 50,
       "x1": 5, "y1": 0, "z1": 0, "x2": 5, "y2": 0, "z2": 1}
PASS if: lumped element created
```

### Test 6.6: List Ports
```
Tool: cst_list_ports
Args: {}
PASS if: returns list including ports 1, 2, 3
```

### Test 6.7: Delete Port
```
Tool: cst_delete_port
Args: {"port_number": 3}
PASS if: port 3 removed
```

---

## Phase 7: Boundaries & Background (4 tools)

### Test 7.1: Set Frequency Range
```
Tool: cst_set_frequency_range
Args: {"f_min": 8, "f_max": 12}
PASS if: frequency range updated in CST
```

### Test 7.2: Set Boundary Conditions
```
Tool: cst_set_boundary
Args: {"x_min": "open", "x_max": "open", "y_min": "open", "y_max": "open",
       "z_min": "electric", "z_max": "open"}
PASS if: boundary conditions applied
```

### Test 7.3: Set Background
```
Tool: cst_set_background
Args: {"material": "Vacuum"}
PASS if: background material set
```

### Test 7.4: Set Symmetry
```
Tool: cst_set_symmetry
Args: {"x": "none", "y": "electric", "z": "none"}
PASS if: symmetry plane applied
```

---

## Phase 8: Mesh (5 tools)

### Test 8.1: Set Mesh Type
```
Tool: cst_set_mesh_type
Args: {"mesh_type": "hexahedral"}
PASS if: mesh type set
```

### Test 8.2: Set Mesh Density
```
Tool: cst_set_mesh_density
Args: {"cells_per_wavelength": 15, "min_cells": 10}
PASS if: mesh density configured
```

### Test 8.3: Add Mesh Refinement
```
Tool: cst_add_mesh_refinement
Args: {"solid": "WG:Waveguide", "refinement_factor": 2}
PASS if: local refinement added
```

### Test 8.4: Adaptive Mesh
```
Tool: cst_set_adaptive_mesh
Args: {"enabled": true, "max_passes": 5, "threshold": 0.02}
PASS if: adaptive mesh configured
```

### Test 8.5: Get Mesh Info
```
Tool: cst_get_mesh_info
Args: {}
PASS if: returns mesh statistics
```

---

## Phase 9: Solvers (5 tools)

### Test 9.1: Configure Time Domain Solver
```
Tool: cst_configure_time_domain_solver
Args: {"accuracy": -40, "max_pulses": 20}
PASS if: solver settings applied
```

### Test 9.2: Configure Frequency Domain Solver
```
Tool: cst_configure_frequency_domain_solver
Args: {"f_min": 8, "f_max": 12, "samples": 501}
PASS if: solver configured
```

### Test 9.3: Configure Eigenmode Solver
```
Tool: cst_configure_eigenmode_solver
Args: {"num_modes": 5}
PASS if: eigenmode solver configured
```

### Test 9.4: Configure Integral Equation Solver
```
Tool: cst_configure_integral_equation_solver
Args: {}
PASS if: IE solver configured
```

### Test 9.5: Get Solver Info
```
Tool: cst_get_solver_info
Args: {}
PASS if: returns current solver configuration
```

---

## Phase 10: Simulation (6 tools)

Use the waveguide project from Phase 6 (2 ports, freq range set).

### Test 10.1: Run Simulation
```
Tool: cst_configure_time_domain_solver
Args: {"accuracy": -30}

Tool: cst_run_simulation
Args: {"solver_type": "Time Domain"}
PASS if: simulation starts and completes
```

### Test 10.2: Get Simulation Status
```
Tool: cst_get_simulation_status
Args: {}
PASS if: solver.status is running or completed, and the response contains no MsgBox
```

### Test 10.3: Run Async Simulation
```
Tool: cst_run_simulation_async
Args: {}
PASS if: returns immediately with status "started" (connected) and the MCP session is not blocked
```

### Test 10.4: Pause Simulation
```
Tool: cst_pause_simulation
Args: {}
PASS if: simulation pauses (or returns appropriate status if already done)
```

### Test 10.5: Resume Simulation
```
Tool: cst_resume_simulation
Args: {}
PASS if: simulation resumes
```

### Test 10.6: Stop Simulation
```
Tool: cst_stop_simulation
Args: {}
PASS if: simulation stops
```

---

## Phase 11: Results (10 tools)

Requires a completed simulation from Phase 10.

### Test 11.1: Get S-Parameters
```
Tool: cst_get_s_parameters
Args: {}
PASS if: returns S11, S21, S12, S22 data with frequency arrays
```

### Test 11.2: Get Impedance
```
Tool: cst_get_impedance
Args: {"port": 1}
PASS if: returns impedance vs frequency
```

### Test 11.3: Get VSWR [REGRESSION #41]
```
Tool: cst_get_vswr
Args: {"port": 1}
PASS if: returns VSWR data, no division-by-zero errors
```

### Test 11.4: Add Field Monitor
```
Tool: cst_add_field_monitor
Args: {"name": "efield_10ghz", "field_type": "Efield", "frequency": 10}
PASS if: field monitor added (NOTE: VBA must NOT contain "Dimension" property)
```

### Test 11.5: Get Farfield
```
Tool: cst_get_farfield
Args: {"frequency": 10}
PASS if: returns farfield data (may require farfield monitor + re-simulation)
```

### Test 11.6: Get Gain
```
Tool: cst_get_gain
Args: {"frequency": 10}
PASS if: returns gain value in dBi
```

### Test 11.7: Get Efficiency
```
Tool: cst_get_efficiency
Args: {}
PASS if: returns radiation efficiency data
```

### Test 11.8: List Results
```
Tool: cst_list_results
Args: {}
PASS if: returns result tree items
```

### Test 11.9: Export Result (Touchstone)
```
Tool: cst_export_result
Args: {
  "result_path": "1D Results\\S-Parameters\\S1,1",
  "format": "touchstone",
  "output_file": "C:\\cst_projects\\waveguide_test.s2p"
}
PASS if: .s2p file created
```

### Test 11.10: Export Result (CSV) [REGRESSION #25]
```
Tool: cst_export_result
Args: {
  "result_path": "1D Results\\S-Parameters\\S1,1",
  "format": "csv",
  "output_file": "C:\\cst_projects\\s11_data.csv"
}
PASS if: CSV file created. Must use ASCIIExport (not blocked by VBA validator).
FAIL if: error about VBA security validation blocking file I/O
```

### Test 11.11: Get Result Summary
```
Tool: cst_get_result_summary
Args: {}
PASS if: returns summary of all available results
```

---

## Phase 12: Import/Export (5 tools)

### Test 12.1: Export CAD
```
Tool: cst_export_cad
Args: {"format": "step", "output_file": "C:\\cst_projects\\waveguide.step"}
PASS if: STEP file exported
```

### Test 12.2: Export Touchstone
```
Tool: cst_export_touchstone
Args: {"output_file": "C:\\cst_projects\\waveguide.s2p", "impedance": 50}
PASS if: Touchstone file exported
```

### Test 12.3: Import CAD (if STEP file exists)
```
Tool: cst_import_cad
Args: {"file_path": "C:\\cst_projects\\waveguide.step"}
PASS if: geometry imported
```

### Test 12.4: Import Touchstone
```
Tool: cst_import_touchstone
Args: {"file_path": "C:\\cst_projects\\waveguide.s2p"}
PASS if: touchstone data imported
```

### Test 12.5: Export Farfield
```
Tool: cst_export_farfield
Args: {"frequency": 10, "output_file": "C:\\cst_projects\\farfield.txt"}
PASS if: farfield data exported (may fail if no farfield data available)
```

---

## Phase 13: Parameters (6 tools)

### Test 13.1: Set Parameter
```
Tool: cst_set_parameter
Args: {"name": "wg_length", "value": "50", "description": "Waveguide length in mm"}
PASS if: parameter created in CST parameter list
```

### Test 13.2: Get Parameter
```
Tool: cst_get_parameter
Args: {"name": "wg_length"}
PASS if: returns value 50
```

### Test 13.3: List Parameters
```
Tool: cst_list_parameters
Args: {}
PASS if: returns list including wg_length
```

### Test 13.4: Parameter Sweep [REGRESSION #30]
```
Tool: cst_parameter_sweep
Args: {
  "parameter": "wg_length", "start": 40, "stop": 60, "steps": 5,
  "simulation_type": "Transient"
}
PASS if: sweep configured. VBA uses provided simulation_type, not hardcoded.
```

### Test 13.5: Optimizer [REGRESSION #31]
```
Tool: cst_optimizer
Args: {
  "goal_type": "minimize", "result_path": "1D Results\\S-Parameters\\S1,1",
  "parameters": [{"name": "wg_length", "min": 40, "max": 60}],
  "method": "trust_region", "max_evaluations": 20
}
PASS if: VBA uses SelectParameter/SetParameterMin/SetParameterMax/AddSelectedParameter
FAIL if: VBA uses AddParameter (old invalid API)
```

### Test 13.6: Delete Parameter
```
Tool: cst_delete_parameter
Args: {"name": "wg_length"}
PASS if: parameter removed
```

---

## Phase 14: Antenna Templates (13 tools)

Create a new project for each antenna to avoid conflicts.

### Test 14.1: Patch Antenna
```
Tool: cst_create_project → {"path": "C:\\cst_projects\\antenna_patch.cst"}
Tool: cst_antenna_patch
Args: {"frequency_ghz": 2.4, "substrate_er": 4.3, "substrate_height_mm": 1.6}
PASS if: complete model with substrate, ground, patch, feed, port, monitors
Verify: inset feed slots are boolean-subtracted from patch
```

### Test 14.2: Patch Antenna (air substrate) [REGRESSION #38]
```
Tool: cst_antenna_patch
Args: {"frequency_ghz": 5.8, "substrate_er": 1.0, "substrate_height_mm": 3.0}
PASS if: no ZeroDivisionError, model builds successfully
FAIL if: error about division by zero in R_edge calculation
```

### Test 14.3: Dipole Antenna
```
Tool: cst_create_project → {"path": "C:\\cst_projects\\antenna_dipole.cst"}
Tool: cst_antenna_dipole
Args: {"frequency_ghz": 1.0}
PASS if: two arm dipole with discrete port at feed gap
```

### Test 14.4: Monopole Antenna
```
Tool: cst_create_project → {"path": "C:\\cst_projects\\antenna_monopole.cst"}
Tool: cst_antenna_monopole
Args: {"frequency_ghz": 0.9}
PASS if: monopole over ground plane with port
```

### Test 14.5: Horn Antenna [REGRESSION #2, #27]
```
Tool: cst_create_project → {"path": "C:\\cst_projects\\antenna_horn.cst"}
Tool: cst_antenna_horn
Args: {"frequency_ghz": 10, "gain_dbi": 15}
PASS if:
  - Waveguide section present
  - Horn flare with lofted interior
  - Loft rear profile at z=0, front profile at z=horn_length (NOT both at z=0)
  - Horn length ~3-4λ for 15 dBi
VERIFY: Check "horn_length_mm" in response calc data: should be ~90-130 mm
```

### Test 14.6: Yagi Antenna [REGRESSION #3]
```
Tool: cst_create_project → {"path": "C:\\cst_projects\\antenna_yagi.cst"}
Tool: cst_antenna_yagi
Args: {"frequency_ghz": 0.3, "num_directors": 5}
PASS if: reflector, driven element, 5 directors visible
VERIFY: reflector spacing should be ~0.20λ from driven (not 0.25λ)
  At 300 MHz, λ=1000mm, so reflector ~200mm behind driven element
```

### Test 14.7: Helix Antenna
```
Tool: cst_create_project → {"path": "C:\\cst_projects\\antenna_helix.cst"}
Tool: cst_antenna_helix
Args: {"frequency_ghz": 1.5, "num_turns": 8}
PASS if: helical antenna with ground plane
```

### Test 14.8: Vivaldi Antenna
```
Tool: cst_create_project → {"path": "C:\\cst_projects\\antenna_vivaldi.cst"}
Tool: cst_antenna_vivaldi
Args: {"frequency_ghz": 5.0}
PASS if: tapered slot Vivaldi with substrate
```

### Test 14.9: Slot Antenna [REGRESSION #26]
```
Tool: cst_create_project → {"path": "C:\\cst_projects\\antenna_slot.cst"}
Tool: cst_antenna_slot
Args: {"frequency_ghz": 5.8}
PASS if: ground plane with slot CUT OUT (Solid.Subtract executed)
FAIL if: slot shape overlaid but not subtracted from ground plane
```

### Test 14.10: IFA
```
Tool: cst_create_project → {"path": "C:\\cst_projects\\antenna_ifa.cst"}
Tool: cst_antenna_ifa
Args: {"frequency_ghz": 2.4}
PASS if: inverted-F antenna on ground plane
```

### Test 14.11: PIFA
```
Tool: cst_create_project → {"path": "C:\\cst_projects\\antenna_pifa.cst"}
Tool: cst_antenna_pifa
Args: {"frequency_ghz": 1.8}
PASS if: PIFA with shorting wall and feed
```

### Test 14.12: Spiral Antenna
```
Tool: cst_create_project → {"path": "C:\\cst_projects\\antenna_spiral.cst"}
Tool: cst_antenna_spiral
Args: {"frequency_ghz": 3.0}
PASS if: spiral antenna visible
```

### Test 14.13: Bowtie Antenna [REGRESSION #40]
```
Tool: cst_create_project → {"path": "C:\\cst_projects\\antenna_bowtie.cst"}
Tool: cst_antenna_bowtie
Args: {"frequency_ghz": 3.0, "flare_angle": 60}
PASS if: bowtie visible. flare_angle=60 means 60° full angle (not halved again).
```

### Test 14.14: List Antenna Templates
```
Tool: cst_list_antenna_templates
Args: {}
PASS if: returns all 12 antenna types with descriptions
```

---

## Phase 15: PCB Tools (6 tools)

```
Tool: cst_create_project → {"path": "C:\\cst_projects\\pcb_test.cst"}
```

### Test 15.1: List Stackup Templates
```
Tool: cst_pcb_list_stackup_templates
Args: {}
PASS if: returns available stackup templates
```

### Test 15.2: Create Stackup
```
Tool: cst_pcb_create_stackup
Args: {
  "layers": [
    {"name": "Top", "type": "signal", "thickness": 0.035, "material": "Copper"},
    {"name": "Prepreg", "type": "dielectric", "thickness": 0.2, "material": "FR4"},
    {"name": "Ground", "type": "signal", "thickness": 0.035, "material": "Copper"},
    {"name": "Core", "type": "dielectric", "thickness": 0.8, "material": "FR4"},
    {"name": "Power", "type": "signal", "thickness": 0.035, "material": "Copper"},
    {"name": "Prepreg2", "type": "dielectric", "thickness": 0.2, "material": "FR4"},
    {"name": "Bottom", "type": "signal", "thickness": 0.035, "material": "Copper"}
  ]
}
PASS if: 4-layer stackup created
```

### Test 15.3: Create Trace
```
Tool: cst_pcb_create_trace
Args: {
  "layer": "Top", "name": "Signal1",
  "points": [[0,0], [10,0], [10,5], [20,5]],
  "width": 0.15, "impedance_target": 50
}
PASS if: trace routed on top layer, impedance info returned
```

### Test 15.4: Create Ground Plane
```
Tool: cst_pcb_create_ground_plane
Args: {
  "layer": "Ground", "name": "GND",
  "x_min": -5, "x_max": 25, "y_min": -5, "y_max": 10
}
PASS if: ground plane created
```

### Test 15.5: Create Via
```
Tool: cst_pcb_create_via
Args: {
  "name": "Via1",
  "x": 20, "y": 5,
  "drill_diameter": 0.3,
  "pad_diameter": 0.6,
  "start_layer": "Top", "end_layer": "Bottom"
}
PASS if: via barrel created
```

### Test 15.6: Import Gerber [REGRESSION #33]
```
Tool: cst_pcb_import_gerber
Args: {
  "file_path": "C:\\cst_projects\\test.gbr",
  "layer_name": "TopCopper"
}
PASS if: validates file path (no traversal). Imports if file exists, clear error if not.
FAIL if: accepts paths like "..\\..\\etc\\passwd" without validation
```

---

## Phase 16: VBA Tools (3 tools)

### Test 16.1: Execute VBA
```
Tool: cst_execute_vba
Args: {"code": "MsgBox \"Hello from MCP\""}
PASS if: executes VBA in CST (message box appears or equivalent)
```

### Test 16.2: VBA Help
```
Tool: cst_vba_help
Args: {"object_name": "Brick"}
PASS if: returns Brick VBA object methods and properties
```

### Test 16.3: List VBA Objects
```
Tool: cst_list_vba_objects
Args: {}
PASS if: returns categorized list of CST VBA objects
```

---

## Phase 17: Security Validation

### Test 17.1: VBA Injection Blocked [REGRESSION #28]
```
Tool: cst_set_parameter
Args: {"name": "test", "value": "10\" & Shell(\"calc.exe\") & \""}
PASS if: error about dangerous pattern detected
FAIL if: VBA executes with injected Shell command
```

### Test 17.2: Path Traversal Blocked [REGRESSION #33, #34]
```
Tool: cst_pcb_import_gerber
Args: {"file_path": "..\\..\\Windows\\System32\\config\\SAM", "layer_name": "test"}
PASS if: error about path traversal

Tool: cst_pcb_import_gerber
Args: {"file_path": "C:\\Windows\\System32\\config\\SAM", "layer_name": "test"}
PASS if: error about path outside work directory
```

### Test 17.3: VBA Execution Blocked
```
Tool: cst_execute_vba
Args: {"code": "Shell \"calc.exe\""}
PASS if: error about blocked VBA pattern
```

---

## Results Summary Template

```
Phase  1: Connection & Project  [  /8  passed]
Phase  2: Geometry Primitives   [  /13 passed]
Phase  3: Boolean Operations    [  /4  passed]
Phase  4: Transforms            [  /4  passed]
Phase  5: Materials             [  /8  passed]
Phase  6: Ports & Excitations   [  /7  passed]
Phase  7: Boundaries            [  /4  passed]
Phase  8: Mesh                  [  /5  passed]
Phase  9: Solvers               [  /5  passed]
Phase 10: Simulation            [  /6  passed]
Phase 11: Results               [  /11 passed]
Phase 12: Import/Export         [  /5  passed]
Phase 13: Parameters            [  /6  passed]
Phase 14: Antenna Templates     [  /14 passed]
Phase 15: PCB Tools             [  /6  passed]
Phase 16: VBA Tools             [  /3  passed]
Phase 17: Security              [  /3  passed]

TOTAL:                          [  /112 passed]

Regression tests (specific bug fixes):
  #2  Horn R_H/R_E:           [PASS/FAIL]
  #3  Yagi spacing:           [PASS/FAIL]
  #22 Cylinder axis:          [PASS/FAIL]
  #23 Transform props:        [PASS/FAIL]
  #24 Plane wave Normal:      [PASS/FAIL]
  #25 Export CSV:             [PASS/FAIL]
  #26 Slot subtract:          [PASS/FAIL]
  #27 Horn loft Z:            [PASS/FAIL]
  #28 VBA injection:          [PASS/FAIL]
  #29 Substrates load:        [PASS/FAIL]
  #30 Sweep sim type:         [PASS/FAIL]
  #31 Optimizer API:          [PASS/FAIL]
  #33 Gerber path:            [PASS/FAIL]
  #34 Windows paths:          [PASS/FAIL]
  #38 Patch eps_r=1:          [PASS/FAIL]
  #40 Bowtie flare:           [PASS/FAIL]
  #41 VSWR div/0:             [PASS/FAIL]
```
