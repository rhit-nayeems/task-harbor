import { defineConfig } from "cf/config";

export default defineConfig({
  worker: {
    "name": "task-harbor",
    "compatibilityDate": "2026-10-06",
    "observability": {
      "enabled": false
    }
  }
});
