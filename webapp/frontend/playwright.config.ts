import { defineConfig } from '@playwright/test';
export default defineConfig({
    testDir: './e2e', timeout: 60000, retries: 1,
    use: { baseURL: 'http://localhost:10868', headless: true, screenshot: 'only-on-failure' },
    webServer: {
        command: 'uv run python -m leanforge_mcp.server --port 10867',
        port: 10867, timeout: 30000, reuseExistingServer: false
    }
});
