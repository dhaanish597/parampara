import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["**/node_modules/**", "**/.next/**", "packages/contracts/src/generated/**", "evals/runs/**"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
);
