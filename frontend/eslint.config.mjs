import { createRequire } from 'node:module'
import { defineConfig, globalIgnores } from 'eslint/config'
import nextVitals from 'eslint-config-next/core-web-vitals'
import nextTs from 'eslint-config-next/typescript'

// eslint-config-next leaves eslint-plugin-react's `version` setting at "detect",
// and the bundled eslint-plugin-react (7.37.5) detects it through
// `context.getFilename()` — removed in ESLint 10, so every React rule throws
// "contextOrFilename.getFilename is not a function" on load. Reading the
// installed React version here does the same job from config, where the removed
// rule API is not involved. Drop this once eslint-config-next ships a
// React plugin that supports ESLint 10.
const require = createRequire(import.meta.url)
const reactVersion = require('react/package.json').version

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    settings: {
      react: { version: reactVersion },
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    '.next/**',
    'out/**',
    'build/**',
    'next-env.d.ts',
    // Static assets — includes the 12.6MB diamonds R notebook HTML
    'public/**',
    'coverage/**',
  ]),
])

export default eslintConfig
