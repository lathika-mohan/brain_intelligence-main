# Enterprise Providers & Global Shell Isolation - Integration Pack

Brain Intelligence / Industrial Operating Brain (IOB) - Next.js 16 / React 19

This ZIP contains the enterprise-hardened `GlobalProviders` and `SidebarContext` files, wired for the existing IOB codebase at https://github.com/Anvita09-code/brain_intelligence

## What changed

### 1. `src/providers/GlobalProviders.tsx`
Merged the spec version with the existing Telemetry wiring.

**Added (from spec):**
- `@tanstack/react-query` – `QueryClientProvider` with enterprise defaults:
  - `refetchOnWindowFocus: false`
  - `retry: 1`
  - `staleTime: 5 * 60 * 1000`
  - `gcTime: 10 * 60 * 1000`
- MUI dark theme with full Industrial palette:
  - `primary.main: '#007ACC'`
  - `secondary.main: '#64748B'`
  - `background.default: '#0B0F19'`
  - `background.paper: '#111827'`
  - `divider: '#1F2937'`
  - `MuiButton` overrides: `textTransform: 'none', borderRadius: '4px'`

**Retained (from existing repo):**
- `TelemetryProvider` wrapping – critical for Digital Twin / GraphRAG / SHAP panels
- `MuiCssBaseline` industrial body overrides
- Named export `export const GlobalProviders` **and** `export default GlobalProviders` for compatibility with `src/app/layout.tsx`
- Scrollbar styling, Drawer/AppBar theme overrides

Provider order (enterprise isolation):
```
QueryClientProvider
 └─ ThemeProvider
     └─ CssBaseline
         └─ TelemetryProvider
             └─ SidebarProvider
                 └─ {children}
```

This guarantees: React Query is global, MUI theme is isolated, telemetry stream is singleton, sidebar state is shell-scoped.

### 2. `src/contexts/SidebarContext.tsx`
Enterprise Global Shell Isolation context – **backwards compatible with existing IOB Sidebar/Navbar**.

**Spec API (new):**
```ts
isOpen: boolean
toggle: () => void
setIsOpen: (open: boolean) => void
```

**Existing IOB API (retained):**
```ts
isOpen: boolean
isCollapsed: boolean
toggleSidebar: () => void
toggleCollapse: () => void
closeMobileSidebar: () => void
```

Both APIs point at the same state – `toggle === toggleSidebar`.

**Behavior:**
- Initial: `isOpen = true`, `isCollapsed = false`
- Responsive auto-isolation at **1200px** (spec):
  - `< 1200px → setIsOpen(false)`
  - `>= 1200px → setIsOpen(true)`
- Exports:
  - `SidebarContext`
  - `SidebarProvider`
  - `useSidebarContext()`
  - `useSidebar()` – alias, matches `@/hooks/useSidebar`

Existing components work unchanged:
- `src/components/layout/Navbar.tsx` → `toggleSidebar()`
- `src/components/layout/Sidebar.tsx` → `isOpen, isCollapsed, toggleCollapse, closeMobileSidebar`

### 3. `src/hooks/useSidebar.ts`
Unchanged thin re-export – still works because the context now provides the full enterprise shape.

### 4. `src/app/(auth)/layout.tsx` – bugfix
Fixed a pre-existing TypeScript build error that blocked `npm run build`:
- Removed invalid `<Container maxWidth="sm">` prop (custom `Container` doesn't accept MUI props)
- Replaced with `<Container className="max-w-sm">`
- Build now passes: `✓ Compiled successfully`

---

## Installation

Copy the folders into your repo root, preserving paths:

```
brain_intelligence/
├─ src/
│  ├─ providers/
│  │  └─ GlobalProviders.tsx      <-- overwrite
│  ├─ contexts/
│  │  └─ SidebarContext.tsx       <-- overwrite
│  ├─ hooks/
│  │  └─ useSidebar.ts            <-- optional, same as repo
│  └─ app/
│     └─ (auth)/
│        └─ layout.tsx            <-- bugfix, recommended
```

No package.json changes – `@tanstack/react-query@^5`, `@mui/material@^6`, `next@16.2.9` are already in the repo.

Run:
```bash
npm install
npm run build
npm run dev
```

Build output (verified):
```
Route (app)
┌ ○ /
├ ○ /_not-found
├ ○ /alerts
├ ○ /assets
├ ○ /chat
├ ○ /dashboard
├ ○ /knowledge
├ ○ /login
├ ○ /predictions
├ ○ /profile
└ ○ /settings
○  (Static)  prerendered as static content
```

## Usage examples

Simple spec API:
```tsx
import { useSidebar } from '@/contexts/SidebarContext'
const { isOpen, toggle, setIsOpen } = useSidebar()
```

Enterprise IOB API:
```tsx
import { useSidebar } from '@/hooks/useSidebar'
const { isOpen, isCollapsed, toggleSidebar, toggleCollapse, closeMobileSidebar } = useSidebar()
```

React Query:
```tsx
import { useQuery } from '@tanstack/react-query'
// QueryClient is already provided globally
```

## Notes

- Removed duplicate `src/context/TelemetryContext.tsx` – canonical source is now `src/contexts/TelemetryContext.tsx` only.
- `GlobalProviders` is a Client Component (`'use client'`), safe to use in `src/app/layout.tsx` with `AppRouterCacheProvider`.
- Theme font uses CSS variable `--font-inter` from `next/font/google` in RootLayout.
- Sidebar responsive breakpoint is 1200px as per spec, not 1024px.

All integration is verified with `npm run build` – TypeScript clean.
