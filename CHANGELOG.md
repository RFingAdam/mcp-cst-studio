# Changelog

All notable changes to **mcp-cst-studio** are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `cst_run_simulation_async` starts `model3d.run_solver()` on a background thread in connected mode and returns immediately.
- `cst_get_simulation_status` polls the solver and the log tail. It no longer injects a VBA `MsgBox`.
- `cst_get_result_curve` returns a decimated numeric curve plus a reflection summary (resonance, bandwidth, Zin, verdict).
- `cst_list_results` uses the Python result tree in connected mode.
- `cst_farfield_sample` samples the farfield calculator on a theta cut.
- `cst_tune_step` runs one StoreParameter → DeleteResults → Rebuild → solve → S-parameter verdict.
- `docs/RF_ENGINEER_LOOP.md` describes the agent design loop.

### Changed
- PyPI publishing runs when a `v<version>` tag on `main` is pushed, instead of on a published GitHub release. It refuses a tag that is not on `main` or does not match the package version, checks the metadata, loads the installed entry point, and publishes through trusted publishing from the `pypi` environment.

### Fixed
- Windows setup docs pointed at `LinuxAMD64`. The library folder on Windows is `AMD64`, and the supported link is the one-time command in CST Help, not `PYTHONPATH` alone.
- Connected-mode test docs used `solver_type="time_domain"` and `cst_configure_time_domain`. The tool enum value is `"Time Domain"` and the tool name is `cst_configure_time_domain_solver`.

## [0.2.0]: 2026-05-13

### Changed
- **License: Apache-2.0 → AGPL-3.0-or-later.** Aligns with the
  eng-mcp-suite toolkit-wide AGPL move. CST Studio Suite itself
  (Dassault Systèmes) is a separate commercial product invoked at
  runtime; this wrapper does not bundle or redistribute it. See the
  [LICENSE_SUMMARY](https://github.com/RFingAdam/eng-mcp-suite/blob/main/LICENSE_SUMMARY.md)
  for the toolkit-wide rationale.

## [0.1.0]

Initial release. MCP server wrapper for CST Studio Suite (Dassault
Systèmes): antenna design, RF simulation, PCB layout. Requires a
licensed CST Studio installation.
