# Section 9 — Architectural Base Hooks (Integration Notes)

Brain Intelligence / Industrial Operating Brain (IOB) — Next.js 16 / React 19 / Material UI v6

This package delivers **Section 9 (Architectural Base Hooks)** integrated seamlessly with the repository's existing **Section 6 Global Component Scaffolding** (`@mui/material`), **Section 7 Decoupled Network Layer**, and **Section 8 Service Interface Mappings**.

---

## 1. Overview of Changes

Section 9 establishes foundational custom React hooks (`useTheme`, `useSidebar`, `useWindowSize`, `useLocalStorage`) to provide standardized state management and browser interaction primitives across the Industrial Operating Brain (IOB) frontend.

To ensure **100% integration and zero breakage** with existing layout components (`Navbar.tsx`, `Sidebar.tsx`, `GlobalProviders.tsx`, etc.):

1. **`useTheme` Material UI Wiring & Backwards Compatibility**:
   - Exactly implements the Section 9 specification: hooks into `@mui/material/styles` via `useMuiTheme()` to return `{ theme, isDark: theme.palette.mode === 'dark' }`.
   - **Integration Fix**: Legacy components and styling layers previously relied on `setTheme` / `toggleTheme` / `themeMode` to manage the `'iob_theme'` localStorage key and toggle `data-theme` and `.dark` CSS classes on the HTML root. We preserved these legacy return values alongside the new MUI theme object, ensuring both MUI components and Tailwind/legacy styles function harmoniously without runtime errors.
   - Guarded with optional chaining (`theme?.palette?.mode`) so components rendered outside an MUI `ThemeProvider` during testing or SSR gracefully fall back to the localStorage theme state.

2. **`useSidebar` Context Tree Enforcement**:
   - Implemented as a standard function (`export function useSidebar()`) matching the Section 9 spec.
   - Enforces valid instantiation inside the `SidebarProvider` layout tree, throwing a descriptive error if called outside context.
   - **Integration Fix**: Added an alias `export const useSidebarContext = useSidebar;` to guarantee backwards compatibility with earlier components or contexts importing `useSidebarContext`.

3. **`useWindowSize` Responsive Telemetry Hook**:
   - Converted to a standard function export (`export function useWindowSize(): WindowSize`) matching the Section 9 spec.
   - Exports the `WindowSize` interface for downstream TypeScript consumers.
   - Cleanly binds and cleans up the browser `'resize'` event listener in `useEffect`.

4. **`useLocalStorage` SSR-Safe Storage Hook**:
   - Standardized generic storage wrapper `useLocalStorage<T>(key, initialValue)`.
   - **Integration Fix**: Corrected syntax errors present in raw markdown documentation (`console.errorError parsing...`) to valid TypeScript template literals (`console.error(\`Error parsing localStorage key "${key}":\`, error)`), preventing build breakages while ensuring full compliance with Section 9 logging requirements.

---

## 2. File Summary & Contract Mappings

| Hook File | Exported Primitives | Description & Integration Notes | Backwards Compatible Exports / Aliases |
|---|---|---|---|
| `src/hooks/useTheme.ts` | `useTheme`<br>`Theme` type | Returns MUI theme object & `isDark` boolean. Syncs `data-theme` attribute and `.dark` class. | `themeMode`, `setTheme`, `toggleTheme` |
| `src/hooks/useSidebar.ts` | `useSidebar` | Consumes `SidebarContext` and enforces provider tree wrapping. | `useSidebarContext` |
| `src/hooks/useWindowSize.ts` | `useWindowSize`<br>`WindowSize` interface | Tracks `window.innerWidth` and `innerHeight` with SSR-safe hydration. | &mdash; |
| `src/hooks/useLocalStorage.ts` | `useLocalStorage` | SSR-safe generic state hook synchronized with `window.localStorage`. | &mdash; |
| `src/hooks/index.ts` | Barrel exports | Re-exports all four architectural base hooks for clean `@/hooks` imports. | &mdash; |

---

## 3. Verification & Build Output

Tested against Next.js 16.2.9 + React 19 + Turbopack production build:

```bash
npm install --legacy-peer-deps
npx tsc --noEmit
npm run build
```

Result:
```
▲ Next.js 16.2.9 (Turbopack)
✓ Compiled successfully in 5.9s
✓ Finished TypeScript in 5.3s
✓ Generating static pages (13/13) in 455ms
```

---

## 4. Downloadable Archives Shipped

Two downloadable ZIP archives have been generated and placed in the project root:

1. **`brain_intelligence_section9_hooks.zip`**:
   Contains exclusively the Section 9 worked files (`src/hooks/*`) and this integration document, maintaining exact directory structure. Ideal for dropping directly into an existing repository.
2. **`brain_intelligence_full_project.zip`**:
   Contains the complete, pre-configured `brain_intelligence` project repository with Section 9 fully integrated and verified (excluding build artifacts and dependencies).
