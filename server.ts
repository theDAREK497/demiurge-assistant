import express from "express";
import { createServer as createViteServer } from "vite";
import { initDb } from "./src/db/index.js";
import apiRoutes from "./src/server/api.js";
import path from "path";
import fs from "fs";
import viteConfig from "./vite.config.ts";

async function startServer() {
  const app = express();
  const PORT = 3000;

  app.use(express.json({ limit: '50mb' }));

  // Initialize DB
  initDb();

  // Ensure uploads directory exists
  const uploadDir = path.join(process.cwd(), 'public', 'uploads');
  if (!fs.existsSync(uploadDir)) {
    fs.mkdirSync(uploadDir, { recursive: true });
  }

  // Serve uploads statically
  app.use('/uploads', express.static(uploadDir));

  // API routes
  app.use("/api", apiRoutes);

  // Vite middleware for development
  if (process.env.NODE_ENV !== "production") {
    const configFn = (viteConfig as any).default || viteConfig;
    const config = typeof configFn === 'function' ? configFn({ mode: 'development', command: 'serve' }) : configFn;
    const vite = await createViteServer({
      ...config,
      server: { middlewareMode: true, ...config?.server },
      appType: "spa",
      configFile: false,
    });
    app.use(vite.middlewares);
  } else {
    app.use(express.static("dist"));
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Server running on http://localhost:${PORT}`);
  });
}

startServer();
