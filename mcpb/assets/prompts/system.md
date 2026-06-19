# leanforge-mcp — MCP Server Capabilities

**Instructions for LLM:** This file must contain 3,000+ words describing the server's complete capabilities.
Include: all tools with parameters, all prompts, all resources, configuration options, environment variables,
data sources, and integration points. Every tool must have its purpose, parameters, and return format documented.

## Server Overview

[Write 2-3 paragraphs describing what this MCP server does, its domain, and key features.]

## Tools

- **__init___queued**: __init__(queued) - **__init___running**: __init__(running) - **__init___complete**: __init__(complete) - **__init___failed**: __init__(failed) - **__init___cancelled**: __init__(cancelled) - **__init___interrupted**: __init__(interrupted) - **cancel_job**: cancel_job - **get_mathlib_search**: get_mathlib_search - **get_proof_status**: get_proof_status - **list_attempts**: list_attempts - **list_jobs**: list_jobs - **validate_lean**: validate_lean - **submit_theorem**: submit_theorem - **submit_lean_file**: submit_lean_file

## Configuration

[Document all environment variables, their defaults, and purposes.]

## Data Sources

[Document any databases, APIs, or files the server reads.]
