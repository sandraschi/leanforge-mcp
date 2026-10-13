# Per-repo fleet start config for leanforge-mcp
# Edit ports/backend target here - start.ps1 is fleet-standard.
@{
    Name         = 'leanforge-mcp'
    BackendPort  = 10867
    FrontendPort = 10868
    HealthPath   = '/api/health'
    WebRoot      = 'webapp\frontend'
    Backend = @{
        Kind          = 'uvicorn-web-app'
        UvicornTarget = 'webapp.backend.main:app'
        WorkDir       = '.'
        PythonPath    = 'webapp\backend;src'
        SyncExtras    = @('dev')
        SyncOnStart  = $true
        Env           = @{ WEB_PORT = '10867' }
    }
    Frontend = @{
        Kind           = 'vite-npm'
        PackageManager = 'npm'
        PortEnvVar     = 'VITE_PORT'
        ApiTargetEnv   = 'VITE_API_TARGET'
    }
}
