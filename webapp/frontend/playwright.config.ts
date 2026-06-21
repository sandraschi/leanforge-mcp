import { defineConfig } from '@playwright/test';
export default defineConfig({
    testDir: './e2e', timeout: 60000, retries: 1,
    use: { baseURL: 'http://localhost:10856', headless: true, screenshot: 'only-on-failure' },
    webServer: {
        command: 'uv run python -m leanforge_mcp.server --port 10855',
        port: 10855, timeout: 30000, reuseExistingServer: false
    }
});
