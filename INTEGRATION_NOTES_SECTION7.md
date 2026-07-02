# Section 7 — Decoupled Network Layer (Integration Notes)

Brain Intelligence / Industrial Operating Brain (IOB) — Next.js 16 / React 19

This package wires the spec's decoupled Axios network layer into the
**existing** `src/api/*` module that already ships in
`https://github.com/Anvita09-code/brain_intelligence`, rather than dropping
the spec files in as-is (which would have silently overwritten working code
and broken imports elsewhere in the repo).

## Why a straight drop-in would have broken the build

| Spec file (`interceptors.ts`) | Existing repo file | Conflict |
|---|---|---|
| Reads token from `localStorage.getItem('iob_auth_token')` directly | Reads token via SSR-safe `storage.get('auth_token', null)` util | Different key name **and** the spec version isn't SSR-safe by itself (it does guard with `typeof window`, but bypasses the shared `storage` abstraction the rest of the app uses) |
| Exports `requestInterceptor` / `responseInterceptor` / `errorInterceptor` as free functions | Exports a single `setupInterceptors(axiosInstance)` function that registers them internally | Existing `apiClient.ts` imports `setupInterceptors`, not the three named functions — dropping in the spec file verbatim would break that import |
| `axios.ts` uses `export default instance` | Existing `axios.ts` uses `export const axiosInstance` (named) | `apiClient.ts` and nothing else in the repo imports a default from `./axios` — a pure spec swap would silently desync |
| `apiClient.ts` returns `APIResponse<T>` (capital "API") | Repo's `@/types` defines `ApiResponse<T>` (different casing) and no code anywhere actually wraps responses in that envelope yet | Type wouldn't even resolve — `APIResponse` doesn't exist in `@/types` |

## What was actually changed

### 1. `src/utils/constants.ts`
Added one new exported constant:
```ts
export const AUTH_TOKEN_KEY = "iob_auth_token";
```
This is now the **single source of truth** for the token's localStorage key
(matches the spec's `iob_auth_token`, superseding the old `auth_token` key).

### 2. `src/api/interceptors.ts`
- Added the three spec-named exports `requestInterceptor`, `responseInterceptor`,
  `errorInterceptor` so any code/docs referencing them by name work.
- `requestInterceptor` reads the token through the repo's existing SSR-safe
  `storage` utility (`@/utils/storage`) + the new `AUTH_TOKEN_KEY`, instead of
  calling `localStorage` directly — keeps working during SSR/prerender.
- `errorInterceptor` merges both behaviors:
  - Spec: normalizes into a real `Error` using `error.response.data.message`,
    falling back to `"Industrial backend connection timeout or failure."`.
  - Existing: keeps the `console.warn`/`console.error` diagnostics for
    `401` / `5xx` responses.
- Kept `setupInterceptors(axiosInstance)` as a **backwards-compatible
  adapter** — it now just attaches the three named interceptors internally,
  so nothing else in the repo needs to change.

### 3. `src/api/axios.ts`
- Kept the existing named export `axiosInstance` (everything in the repo
  imports this).
- Added `export default axiosInstance` too, so the spec's
  `import instance from './axios'` style also resolves.
- Bumped `timeout` from `10000` → `30000` (spec value) — industrial telemetry
  batch pulls / SHAP / GraphRAG calls can legitimately take longer.
- Interceptors are now attached **once, here**, directly on `axiosInstance`
  at module init (previously `apiClient.ts` called `setupInterceptors()` on
  import — moved to avoid double-registration now that `apiClient.ts` no
  longer needs to know about interceptor wiring at all).

### 4. `src/api/apiClient.ts`
- Removed the `setupInterceptors(axiosInstance)` call here (now handled
  in `axios.ts`) to prevent interceptors being registered twice on the
  shared instance.
- Kept the existing calling convention: methods resolve to `response.data`
  directly (`Promise<T>`), matching every consumer under
  `src/services/*.service.ts`, instead of switching to the spec's
  `Promise<APIResponse<T>>` wrapper shape, which doesn't match any backend
  contract actually used in this repo yet and isn't defined in `@/types`.
- Added a `patch` method (not in the original stub) for completeness.

### 5. `src/api/index.ts`
Unchanged barrel shape — still re-exports `./axios`, `./interceptors`,
`./apiClient`.

### 6. `src/services/*.service.ts` (all six services)
Every service previously returned **hardcoded mock data only** — there was
no real network wiring anywhere in the app. Each service now:
```ts
try {
  return await apiClient.get<T>('/endpoint');
} catch {
  return MOCK_DATA; // same fixture data as before
}
```
This means:
- The app **keeps working exactly as before** with zero backend (demo mode) —
  every dashboard/page that currently renders placeholder UI is unaffected.
- The moment `NEXT_PUBLIC_API_URL` points at a real backend and it returns
  `200`s, real data flows through automatically with the auth header already
  attached by the interceptor.
- No page/component currently calls these services yet (all
  `src/app/(dashboard)/**/page.tsx` routes are still placeholder stubs per
  the existing repo state) — so this introduces zero risk to the current
  build/prerender.

### 7. `.env.example`
Added a comment documenting the `iob_auth_token` localStorage key convention
(no new env var required — the token is set client-side, e.g. after login).

## Provider/import chain (unchanged, verified)

```
src/services/*.service.ts
   └─ apiClient (src/api/apiClient.ts)
        └─ axiosInstance (src/api/axios.ts)
             ├─ requestInterceptor  ─┐
             ├─ responseInterceptor ─┼─ src/api/interceptors.ts
             └─ errorInterceptor    ─┘
                  └─ storage.get(AUTH_TOKEN_KEY) — src/utils/storage.ts + constants.ts
```

## Verification

```bash
npm install --legacy-peer-deps   # pre-existing repo quirk: @mui/material-nextjs@6.5.0
                                  # peers on next@^13-15, repo pins next@^16.2.9
npx tsc --noEmit                 # ✅ clean
npm run build                    # ✅ Compiled successfully, all 11 routes prerender
```

Build output (verified against this package):
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

> Note: `npm run lint` fails on a pre-existing, unrelated issue in this repo
> (`next lint` / Next 16.2.9 CLI argument handling issue — "Invalid project
> directory provided, no such directory: .../lint"). This is not caused by,
> or related to, the Section 7 changes and was present before this patch.

## Installation

Unzip into the project root, preserving paths — this **overwrites**:

```
brain_intelligence/
└─ src/
   ├─ api/
   │  ├─ interceptors.ts   <-- overwrite
   │  ├─ axios.ts          <-- overwrite
   │  ├─ apiClient.ts      <-- overwrite
   │  └─ index.ts          <-- unchanged, included for completeness
   ├─ services/
   │  ├─ asset.service.ts       <-- overwrite
   │  ├─ alert.service.ts       <-- overwrite
   │  ├─ chat.service.ts        <-- overwrite
   │  ├─ knowledge.service.ts   <-- overwrite
   │  ├─ prediction.service.ts  <-- overwrite
   │  └─ user.service.ts        <-- overwrite
   └─ utils/
      └─ constants.ts     <-- overwrite (adds AUTH_TOKEN_KEY only)
└─ .env.example            <-- overwrite (adds a comment only)
```

Then:
```bash
npm install --legacy-peer-deps
npm run build
npm run dev
```

## Usage example

```ts
import { apiClient } from '@/api';
import { assetService } from '@/services';

// Anywhere under the app — the Authorization header is attached
// automatically if a token exists at localStorage['iob_auth_token'].
const assets = await assetService.getAssets();

// Or call the client directly for a new endpoint:
const raw = await apiClient.get<{ ok: boolean }>('/health');
```

To set the token after a login call:
```ts
import { storage } from '@/utils/storage';
import { AUTH_TOKEN_KEY } from '@/utils/constants';

storage.set(AUTH_TOKEN_KEY, response.token);
```
