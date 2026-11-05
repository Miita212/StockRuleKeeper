import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

import aitDevtools from "@apps-in-toss/devtools/unplugin";

export default defineConfig({
  plugins: [aitDevtools.vite(), react()],
  server: { host: true }, // 에뮬레이터(10.0.2.2)에서 접근하려면 필요
})
