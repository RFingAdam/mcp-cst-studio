# RF engineer loop

This is the path an agent should take to design, solve, and retune an antenna.
Do not invent extra geometry tools when a step below fails. Read the result,
then change one parameter.

## 0. Units

Call `cst_get_units` before the first brick. Geometry tools do not convert
units. If the call is offline, length is unknown: do not assume millimeters.
CST curves come back in the project frequency unit. A 2.4 that is GHz and a
2.4e9 that is Hz are both valid. `unit_guess` on a curve is a hint, not a
conversion.

After the geometry exists and before the first solve, call
`cst_capture_3d_view`. Check that the PNG path exists and the byte count is
non-zero. The image is not inlined in the tool response. A Boolean that
deleted the radiator shows up here, not in the S-parameters.

## 1. Build

Prefer a template (`cst_antenna_patch` and the others) so the history list is
a rebuildable model. Set boundaries, a port, the frequency range, and a
farfield monitor at the target frequency before the first solve.

## 2. Solve without blocking the agent

1. `cst_configure_time_domain_solver` (or the frequency-domain tool).
2. `cst_run_simulation_async`. Connected mode starts `model3d.run_solver()` on
   a background thread. It does not push `Solver.Start` into the history and
   it does not open a MsgBox.
3. Poll `cst_get_simulation_status` until `solver.status` is `completed` or
   `error`. The log tail is included when CST wrote one.

`cst_run_simulation` is the blocking call. Use it only when the client can
wait. `cst_tune_step` is also blocking: it is one deliberate retune, not a
status poll.

## 3. Read numbers, not a string dump

`cst_get_s_parameters` and `cst_get_result_curve` return a decimated `curve`
(`x`, `y_re`, optional `y_im`) and, for a reflection trace, a `summary`:

- `f_res`, `s_min_db`
- `bandwidth` at -10 dB when the trace crosses it
- `zin_re` / `zin_im` when the samples are complex
- `verdict.code`: `on_target`, `resonance_low`, `resonance_high`,
  `frequency_ok_match_poor`, `poor_match`, `matched`

`resonance_low` means the structure is electrically long: shorten it.
`resonance_high` means it is electrically short: lengthen it.

If the path is unknown, call `cst_list_results` first. Connected mode lists
tree paths from the Python API. Pass `run_id` into `cst_get_result_curve` for
a parametric run.

## 4. One retune

`cst_tune_step` with a parameter object runs the only sequence that produces
fresh data:

1. `StoreParameter`
2. `DeleteResults` (required; otherwise CST returns the previous S-parameters)
3. `Rebuild`
4. `run_solver`
5. Read `S{port},{port}` and return the verdict

Stop length tuning when the verdict is `on_target`. A shallow match at the
right frequency is a feed or matching-network problem (`cst_matching_l_network`
and the other matching tools), not another length change.

## 5. Farfield

After the match is acceptable, `cst_farfield_sample` takes a theta cut
(default phi = 0, 5 degree steps) through the farfield calculator. Radius is
in meters. The response includes the cut and the peak. Do not request a full
sphere through MCP.

For a near field, add the monitor before the solve (`cst_add_field_monitor`),
then `cst_sample_field` at a short point list. Pass `conductivity` only when
you know it; SAR is `0.5 * sigma * |E|^2` and density is not applied. Pass
both the E and H tree paths to get `0.5 * Re(E × H*)`. A whole monitor goes
to disk with `cst_export_field_hdf5` (`mesh` or `grid`). Do not pull the
volume back through MCP.

## 6. Hand off

Export Touchstone with `cst_export_touchstone` when another tool (matching,
chamber comparison, a report) needs the full matrix.
