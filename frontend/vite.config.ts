import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path'

export default defineConfig({
  // Drop vue-i18n's runtime message compiler (which uses `new Function`) from the
  // bundle entirely — we supply a custom messageCompiler in src/i18n. Keeps the
  // app CSP-safe (no 'unsafe-eval' needed).
  define: {
    __VUE_I18N_FULL_INSTALL__: true,
    __VUE_I18N_LEGACY_API__: false,
    __INTLIFY_JIT_COMPILATION__: false,
    __INTLIFY_DROP_MESSAGE_COMPILER__: true,
  },
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      // Runtime-only build has NO message compiler (no `new Function`); messages
      // are resolved by our custom messageCompiler in src/i18n. CSP-safe.
      'vue-i18n': 'vue-i18n/dist/vue-i18n.runtime.esm-bundler.js',
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['vue', 'vue-router', 'pinia', 'axios'],
          editor: ['@tiptap/core', '@tiptap/vue-3', '@tiptap/starter-kit'],
          lucide: ['@lucide/vue'],
        },
      },
    },
  },
})
