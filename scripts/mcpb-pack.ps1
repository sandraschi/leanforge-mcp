#Requires -Version 5.1
<#
.SYNOPSIS
Fleet MCPB pack shim for leanforge-mcp.
Delegates to the maintained mcpb/pack.ps1 pipeline (wipe + fresh-copy src,
import/AST/pollution checks, 3-4-100 report, pack, launch-check) so there is
exactly one pack implementation to maintain.
#>
$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "..\mcpb\pack.ps1") @args
