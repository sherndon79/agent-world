# World* Transport Parity & Testing Roadmap

This document captures the sequence we just walked through on WorldBuilder so we can replicate it across the remaining World* extensions (Viewer, Surveyor, Recorder, Streamer RTMP/SRT).

## Goals

- Shared transport helpers and error contracts so HTTP + MCP stdio/streaming behave identically.
- Optional headless unit tests that exercise queue/service logic via Isaac's Python interpreter.
- Installer/launcher consistency (precompile, default auth toggles, enablement). 

### Completed On WorldBuilder (reference state)

- HTTP controller now delegates through `normalize_transport_response` and emits structured error codes.
- MCP streaming server returns JSON payloads using the same helper, giving parity with HTTP responses.
- Service layer routes read-only queries through `api_interface` helpers (scene status, object search, bounds, ground level).
- Base modules extracted (`config/loader.py`, `errors.py`, `utils.py`, `transport/*`).
- Headless pytest suite lives under `tests/worldbuilder/*`; wrappers (`scripts/test_worldbuilder.*`) invoke Isaac's Python and auto-install pytest.
- Installers/launchers precompile linked extensions, link the streamer MCP code, and enable SRT + auth by default (Surveyor remains unauthenticated).
- This roadmap doc records the sequence so we can restore context after conversation compaction.

### In Progress: WorldViewer (Phase 2–4)

- Shared `agentworld_core.transport.normalize_transport_response` now powers both HTTP and MCP layers; the parity contract lives in `transport/contract.py`.
- HTTP handler refactored to controller/service/schemas structure with validation parity and centralized error responses.
- MCP stdio server returns JSON payloads via the shared normalizer, replacing Markdown formatting.
- Added lightweight unit coverage (`tests/worldviewer/test_controller.py`) to guard controller/service error paths ahead of USD-backed tests.

#### Current Clean-up Targets
- **WorldViewer**: the HTTP handler still instantiates the controller lazily and lets some routes bypass validation. Move controller/service creation into `api_interface.initialize()` and funnel every route through controller helpers so validation/error codes stay consistent. The MCP stdio server now emits JSON, but each tool wraps responses manually—extract a shared helper so the HTTP contract remains the single source of truth.
- **WorldBuilder**: queue processing returns stats without an explicit `success` flag and mixes emoji logging with structured errors. Align on `error_response`/`normalize_transport_response` so downstream clients don’t need special cases. Scene helpers rely on direct `omni.usd`/`pxr` calls everywhere; an adapter layer would make unit testing easier and reduce the stubbing footprint we just added.

### In Progress: WorldSurveyor (Phase 2–4)

- HTTP handler now routes through `WorldSurveyorController`/`WorldSurveyorService`, sharing the transport contract and JSON normalisation with the other extensions.
- MCP stdio server is contract-driven, returning normalized payloads via `normalize_transport_response` instead of Markdown.
- Added headless regression coverage under `tests/worldsurveyor/*`, reusing the shared stubs for Isaac-only modules.
- Next clean-ups: extract queue/camera helpers from the service into an adapter, and align group/waypoint validation with the database layer to avoid duplicated checks.

### Completed: WorldRecorder (Phase 2–4)

- Introduced `WorldRecorderService`/`WorldRecorderController` so HTTP + MCP share validation, error handling, and transport contracts.
- Both stdio and streaming MCP servers now enumerate tools from `transport/contract.py`, returning JSON payloads through `normalize_transport_response`.
- Added light controller unit tests (`tests/worldrecorder/test_worldrecorder_controller.py`) covering the critical validation failures without requiring Isaac bindings.
- HTTP routes now perform shared output-path validation and reuse the cleanup helpers, eliminating the inconsistent error shapes that previously surfaced as foreign-key crashes via the MCP tools.

### Completed: WorldStreamer RTMP/SRT (Phase 2–4)

- Added controller/service layers to both protocols so streaming, status, URL, and environment endpoints share the same validation + error scaffolding.
- Stdio and streaming MCP servers now rely on the shared transport contract and deliver JSON responses, with auto-detection still reporting the active protocol in response details.
- Introduced parity unit coverage (`tests/worldstreamer/test_worldstreamer_controller.py`) that exercises the RTMP/SRT controllers against stub streaming interfaces.
- Cleaned up the HTTP handlers to route exclusively through the controller stack, dropping bespoke logic and ensuring health/metrics flow through the shared `WorldHTTPHandler`.

## Repeatable Sequence

1. **Survey + Diff**
   - List existing HTTP endpoints + MCP tools.
   - Capture response shapes and error handling gaps.
   - Note extension-specific helper methods we rely on in `api_interface`.

2. **Shared Transport Utilities**
   - Ensure `errors.py` + `transport/shared.py` are reusable (no extension-specific assumptions).
   - Add/update transport contract entries (HTTP route → MCP tool).
   - Create parity unit test to assert controller methods exist.

3. **Service Layer Alignment**
   - Audit `services/<ext>_service.py` for calls into `SceneBuilder` or helpers that no longer exist.
   - Route read-only queries through `api_interface` helpers, wrapping results with `error_response` + `normalize_transport_response`.
   - Add missing helpers (e.g. statistics snapshots) to `SceneBuilder` if truly needed.

4. **MCP Transport Update**
   - Import shared transport helpers with try/except fallbacks (for containerised usage).
   - Convert each `_tool` method to return structured dicts rather than Markdown strings.
   - Normalize connection errors with consistent codes.

5. **Testing Harness**
   - Stub omni/pxr dependencies in `tests/conftest.py` if not already present.
   - Add focused unit tests covering queue/service behaviour that doesn’t require USD (`tests/<ext>/test_*.py`).
   - Provide `scripts/test_<ext>.sh/.ps1` wrappers that run pytest via Isaac’s `python.sh` / `python.bat`.

6. **Installer / Launcher Parity**
   - Update symlink/precompile lists to include the extension.
   - Decide on default `--enable` / `auth_enabled` flags in launch scripts.
   - Document any auth nuance in the installer prompts.

7. **Validation Checklist**
   - `python3 -m compileall` on updated modules.
   - Run new pytest suite via the helper script.
   - Smoke test HTTP + MCP endpoints (health, metrics, main CRUD operations).

## Extension Order & Notes

- **WorldViewer**: heavy scene/state helpers—expect more API-interface fallbacks needed.
- **WorldSurveyor**: keep auth disabled in launch scripts; ensure waypoint helpers return structured payloads.
- **WorldRecorder**: focus on queue + recording status responses; check MCP streaming outputs for text vs dict.
- **WorldStreamer RTMP/SRT**: share metrics and status responses; only SRT is enabled by default in launchers.

## Reference Artifacts (WorldBuilder)

- Shared helpers: `omni/agent/worldbuilder/{errors.py, utils.py, transport/}`
- MCP parity implementation: `docker/mcp-servers/worldbuilder/src/mcp_agent_worldbuilder.py`
- Headless tests: `agentworld-extensions/tests/worldbuilder/*`
- Installer/launcher changes: `scripts/install_agent_world.*`, `scripts/launch_agent_world.*`, `scripts/test_worldbuilder.*`
- Test invocation: `scripts/test_worldbuilder.sh` (Linux) / `.ps1` (Windows) calls Isaac's `python`.

## Open Questions

- Do we want a consolidated `scripts/test_world*.sh` wrapper that runs each suite sequentially?
- Should we promote the transport contract to shared `agentworld_core.http` for runtime enforcement?
- Investigate automated doc generation of MCP tool metadata once transports are aligned.

*Document prepared: 2025-09-18*
