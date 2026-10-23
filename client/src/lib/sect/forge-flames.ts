// Temporary shim: the running dev server (Turbopack) still holds the old forge-flames.tsx, which
// imports this path. Nothing in the source imports it. Delete it after the next dev-server restart.
export * from "./flames";
