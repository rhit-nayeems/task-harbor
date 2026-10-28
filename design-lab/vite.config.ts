import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwind from '@tailwindcss/vite';
import { fileURLToPath } from 'node:url';
export default defineConfig({plugins:[react(),tailwind()],resolve:{alias:{'@tanstack/react-router':fileURLToPath(new URL('./src/router.tsx',import.meta.url)),'@':fileURLToPath(new URL('./src',import.meta.url))}}});
