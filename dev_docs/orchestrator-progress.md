# Orchestrator Integration Progress

## Completed
- DAG runner (validation, retries, status tracking)
- Orchestrator manager with default type handlers
- Scene reset stage and MCP cleanup pipeline
- Mock responders for `llm`, `audio`, and generic `mcp`
-`sample-adventure` auto-start support via `START_SAMPLE_DAG`

## Next Steps
1. Implement real LLM responder
   - Subscribe to `orchestrator:llm:request`
   - Build prompt from `stage.payload`
   - Call configured LLM provider (Anthropic / OpenAI / Gemini)
   - Emit `orchestrator:llm:result`
2. Implement MCP responder
   - Listen to `orchestrator:mcp:request`
   - Route to specific MCP client based on `mcpService`
   - Emit `orchestrator:mcp:result`
3. Implement audio responder
   - Subscribe to `orchestrator:audio:request`
   - Call audio microservices (narration/commentary/etc.)
   - Emit `orchestrator:audio:result`
4. Validation console skeleton
   - Basic UI/back-end to trigger DAG and individual checks
   - OBS WebSocket bridge integration

## Notes
- `START_SAMPLE_DAG=true` in `.env`
- Restart service via `npm run service:restart` after changes
