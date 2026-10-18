# leanforge-mcp — GitHub Copilot instructions

## Session Context

Before starting work in this repo, load tool awareness:

- MCP server: `leanforge-mcp` (stdio: `uv run python -m leanforge_mcp`).
  Web backend FastAPI on :10867, frontend Vite on :10868.
- Read `AGENTS.md` and `docs/ONBOARDING.md` before changing behavior.
- Gates: `uv run ruff check src/ webapp/backend/`, `uv run pytest tests/ -q`,
  and in `webapp/frontend`: `bun run check`, `bun run biome:ci`.
- Venv: `uv sync --extra dev --extra web` (bare `uv sync` prunes dev+web).
- All MCP tools return `success` + `message` on every path.
- Never commit `.env`, `config.toml`, `data/`, or `*.mcpb`.
- Lean compiles via `lake env lean` in the workspace, never bare `lean`.
