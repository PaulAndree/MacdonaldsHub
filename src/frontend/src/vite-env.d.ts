/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "true" only in the example build; a build-time constant (see vite.config.ts). */
  readonly VITE_EXAMPLE_MODE: "true" | "false";
  /** The design version tag, or an empty string when the build was not made from a tag. */
  readonly VITE_DESIGN_VERSION: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
