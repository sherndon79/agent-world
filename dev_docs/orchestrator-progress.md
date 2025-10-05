# Orchestrator Integration Progress

## Completed
- DAG runner (validation, retries, status tracking)
- Orchestrator manager with default type handlers
- Scene reset stage and MCP cleanup pipeline
- Mock responders for `audio` and generic `mcp`
- `sample-adventure` auto-start support via `START_SAMPLE_DAG`
- Music responder now powered by MusicGen with auto-duck + phase-out syncing across channels
- `OrchestratorLLMResponder` subscribed to `orchestrator:llm:request` with provider routing (Claude/GPT/Gemini)
- LLM responder lifecycle hooked into `AdventuresPlatform` startup/shutdown with surfaced error reporting
- `OrchestratorMCPResponder` executing `orchestrator:mcp:request` via configured Isaac Sim MCP clients
- `OrchestratorAudioResponder` bridged to narration/commentary/ambient/music channels with control command routing

## Next Steps
1. Stand up validation console skeleton
   - Minimal UI/back-end to trigger DAG stages and canned checks
   - OBS WebSocket bridge integration hooks
2. Add coverage for new responders
   - DAG happy-path + failure-path tests with LLM/MCP responders toggled
   - Stage reset verification with live MCP clearing logic
   - Audio responder mocks for success/error flows once implemented

## Notes
- Set `ORCHESTRATOR_LLM_RESPONDER=true` (requires at least one LLM API key)
- Set `ORCHESTRATOR_AUDIO_RESPONDER=true` (auto-enabled when mock handlers disabled)
- Disable mocks via `ORCHESTRATOR_MOCK_HANDLERS=false` when real responders are active
- `START_SAMPLE_DAG=true` auto-launches `sample-adventure`
- Restart services with `npm run service:restart` after responder changes
