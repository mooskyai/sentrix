import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
export default defineConfig(function (_a) {
    var mode = _a.mode;
    var env = loadEnv(mode, process.cwd(), "");
    return {
        plugins: [react()],
        server: {
            proxy: {
                "/api": {
                    target: env.VITE_DEV_API_PROXY_TARGET || "http://localhost:8000",
                    changeOrigin: true,
                },
            },
        },
        test: {
            environment: "jsdom",
            setupFiles: "./src/test/setup.ts",
        },
    };
});
