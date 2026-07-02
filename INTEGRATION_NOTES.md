# Section 6 — Global Component Scaffolding (Integration Notes)

This package contains the **UI** and **Layout** component scaffolding for the
`brain_intelligence` (IOB Frontend) project.

## Files shipped

```
src/
└── components/
    ├── ui/
    │   ├── Button.tsx        (MuiButton wrapper + clsx)
    │   ├── Card.tsx          (industrial surface card)
    │   ├── Container.tsx     (MuiContainer wrapper)
    │   ├── Typography.tsx    (MuiTypography wrapper)
    │   └── Logo.tsx          (Cpu icon + IOB wordmark)
    └── layout/
        ├── Navbar.tsx        (uses useSidebar().toggle)
        ├── Sidebar.tsx       (uses useSidebar().isOpen + usePathname)
        └── Footer.tsx
```

## ⚠️ Integration fix applied (IMPORTANT)

The existing dashboard wiring imports these as **named** exports:

```tsx
// src/app/(dashboard)/layout.tsx
import { Sidebar } from '@/components/layout/Sidebar';
import { Navbar } from '@/components/layout/Navbar';
import { Footer } from '@/components/layout/Footer';
```

…while the Section 6 spec wrote each component with only a **default** export.
Naively dropping in `export default` files would break those imports.

**Fix:** every component below exports BOTH forms, so the spec style *and* the
existing named-import wiring both resolve with zero changes elsewhere:

```tsx
export function Navbar() { /* … */ }
export default Navbar;
```

No other files need editing.

## Wiring verification (done against your repo)

| Integration point                                       | Status |
|---------------------------------------------------------|:------:|
| `@/hooks/useSidebar` → `SidebarContext` exposes `isOpen` + `toggle` | ✅ |
| `SidebarProvider` present in `GlobalProviders.tsx`      | ✅ |
| `industrial-surface / border / blue / slate` colors in `tailwind.config.ts` | ✅ |
| `clsx`, `lucide-react`, `@mui/material`, `next/link`, `next/navigation` | ✅ |
| Named imports in `(dashboard)/layout.tsx`               | ✅ compatible |

### Provider chain (already in place — no change needed)
`RootLayout` → `AppRouterCacheProvider` → `GlobalProviders` →
`QueryClientProvider` → `ThemeProvider` → `CssBaseline` →
**`SidebarProvider`** → `TelemetryProvider` → children

Because `SidebarProvider` wraps the whole tree, `Navbar` and `Sidebar`
can safely call `useSidebar()` anywhere under the dashboard route group.

## Installation

1. Unzip into the **project root** (so `src/components/...` merges over the
   existing `src/components/` folder).
2. These files replace the existing stub `Button.tsx`, `Card.tsx`,
   `Container.tsx`, `Typography.tsx`, `Logo.tsx`, `Navbar.tsx`, `Sidebar.tsx`,
   `Footer.tsx`.
3. Run:

```bash
npm install      # if dependencies not yet installed
npm run lint
npm run dev
```

## Notes on conventions

- `Logo.tsx` and `Footer.tsx` are intentionally **server components**
  (no `'use client'`) — they hold no client hooks/state.
- `Navbar`/`Sidebar` are `'use client'` because they consume
  `useSidebar()` / `usePathname()`.
- `Button`, `Card`, `Container`, `Typography` are `'use client'` to match the
  MUI interactive baseline already configured in `GlobalProviders`.
