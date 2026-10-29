import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Desenvolvimento: por padrão a API é a local (uvicorn na 8000).
// Para desenhar telas contra a homologação sem subir o backend:
//   API_ALVO=https://estoque.acokorte.com.br npm run dev
// Se o DNS interno não resolver o nome, use o IP e informe o host:
//   API_ALVO=https://<ip> API_HOST=estoque.acokorte.com.br npm run dev
const alvo = process.env.API_ALVO ?? "http://localhost:8000";
const host = process.env.API_HOST;

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: alvo,
        changeOrigin: !host,
        secure: !host,
        headers: host ? { host, origin: `https://${host}` } : undefined,
      },
    },
  },
});
