# leanforge-mcp (MCPB Bundle)

MCP server for AI-driven formal proof search in Lean 4

## Usage

Add to \claude_desktop_config.json\:
\\\json
{
  "mcpServers": {
    "leanforge-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "\D:\Dev\repos", "python", "-m", "leanforge_mcp"],
      "env": { "PYTHONPATH": "\D:\Dev\repos/src" }
    }
  }
}
\\\

## Tools

- **cancel_job**: cancel_job
- **get_mathlib_search**: get_mathlib_search
- **get_proof_status**: get_proof_status
- **list_attempts**: list_attempts
- **list_jobs**: list_jobs
- **validate_lean**: validate_lean
- **submit_theorem**: submit_theorem
- **submit_lean_file**: submit_lean_file

## Requirements

- Python 3.12+
- uv
