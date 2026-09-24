import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    rules: {
      // The fetch-on-mount pattern (async data loading in an effect) legitimately
      // sets loading/data state; turning off this strict rule avoids cascading
      // re-render noise on standard data-loading pages.
      "react-hooks/set-state-in-effect": "off",
    },
  },
]);

export default eslintConfig;
