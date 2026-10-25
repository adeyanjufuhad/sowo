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
    // Third-party components copied in from the React Bits registry (reactbits.dev).
    "components/BlurText.tsx",
    "components/CurvedLoop.tsx",
    "components/LogoLoop.tsx",
    "components/RotatingText.tsx",
  ]),
]);

export default eslintConfig;
