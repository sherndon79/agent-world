# AgentWorld Extensions Modernisation Roadmap

Goal: lift the Isaac Sim extension stack to a maintainable, testable shape without breaking the existing MCP/HTTP contract.

## Phase 0 – Baseline
- ✅ Capture review findings and grades (see `mcp_system_review_2025-09-16.md`).
- ✅ Align on scope (internal refactors only, no API surface changes).

## Phase 1 – Make the extensions installable (High priority)
1. Create `pyproject.toml`/`setup.cfg` so the extensions can be installed with `pip install -e`.
2. Normalise package structure (e.g. `agentworld_ext/...`).
3. Replace `sys.path` mutations with standard imports everywhere (`http_handler`, config loaders, queue manager).
4. Update MCP build scripts/Dockerfiles to install the package rather than vendoring paths.

**Outcome:** Clean imports, tooling support, reliable deployments.

## Phase 2 – Unbundle the HTTP handler (High priority)
1. Introduce `http/schemas.py` with module-level Pydantic models (v2-ready).
2. Add `http/controller.py` to map request → service calls → response dict.
3. Extract USD-touching logic into `services/worldbuilder_service.py` (or reuse existing builder modules via a façade).
4. Refactor `http_handler.py` to minimal orchestration.
5. Add focused unit tests for controller/service logic using simple fakes.

**Outcome:** Testable, readable HTTP stack with identical endpoints.

## Phase 3 – Shared utilities & config (Medium priority)
1. Gather USD sanitising, stats formatting, error helpers into `utils.py`.
2. Add a single config loader (`config/loader.py`) that merges JSON defaults + env vars.
3. Inject config objects into services/handlers instead of re-reading files.

**Outcome:** Less duplication, consistent runtime behaviour.

## Phase 4 – Error handling & observability (Medium priority)
1. Define domain exceptions (`StageUnavailable`, `ValidationError`, `AuthFailure`).
2. Standardise logging (structured messages, consistent fields, emoji optional at higher layer).
3. Ensure HTTP/MCP responses include machine-friendly error codes + messages.

**Outcome:** Easier debugging, clearer client behaviour.

## Phase 5 – Testing foundation (High priority once phases 1–3 land)
1. Build fake USD stage/prims to simulate create/remove/batch flows.
2. Write pytest suites covering:
   - Element placement and batch creation
   - Queue manager lifecycle + stats updates
   - Validation failures and exception propagation
3. Integrate into CI script (manual or automated).

**Outcome:** Regression safety net before future features land.

## Phase 6 – Transport parity (Medium priority)
1. Extract shared worldbuilder logic so stdio + streaming MCP servers import the same code.
2. Return structured payloads (not Markdown) from tool methods; move formatting to clients.
3. Add parity contract test comparing tool metadata between transports.

**Outcome:** Reduced duplication and guaranteed protocol consistency.

## Phase 7 – Nice-to-haves / Stretch
- Document thread-handling expectations (main thread vs. workers) and enforce them.
- Add richer metrics (histograms/timers) with consistent naming.
- Evaluate type hints + static analysis once packaging sorted.

## Tracking
- Use git branches per phase (`feature/extensions-phase-1`, etc.).
- Update this roadmap as tasks land; mark ✅ with commit references.

*Prepared: 2025-09-16*
