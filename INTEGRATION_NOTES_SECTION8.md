# Section 8 — Service Interface Mappings (Integration Notes)

Brain Intelligence / Industrial Operating Brain (IOB) — Next.js 16 / React 19

This package delivers Section 8 (**Service Interface Mappings**) integrated seamlessly with the repository's existing **Section 7 Decoupled Network Layer** (`src/api/apiClient.ts`) and domain types (`src/types/index.ts`).

---

## 1. Overview of Changes

Section 8 establishes standardized domain service objects (`AssetService`, `AlertService`, `PredictionService`, `KnowledgeService`, `ChatService`, `UserService`) with targeted Phase 2 API binding stubs.

To ensure **100% integration and zero breakage** with existing code across the application:

1. **Dual Exports (PascalCase & camelCase)**:
   Every service module now exports both the exact PascalCase interface required by Section 8 (`export const AssetService = ...`) and the camelCase alias required by earlier integration layers (`export const assetService = AssetService;`).

2. **Network Wiring (`apiClient` Integration)**:
   Instead of static stubs that return hardcoded empty arrays without network execution, every Section 8 method is wired through the decoupled `apiClient`. If the real industrial backend API (`/api/v1/...`) is reachable during Phase 2 execution, real telemetry and predictive data are fetched. When running offline, in demo mode, or during testing, network fallback blocks cleanly return the exact Section 8 return specifications (`[]` or `null`).

3. **Domain Type Aliases**:
   Added Section 8 domain type aliases in `src/types/index.ts` (`Alert`, `Prediction`, `Knowledge`, `Chat`, `User`) mapped directly to the repository's concrete domain interfaces (`AnomalyAlert`, `PredictionModel`, `KnowledgeNode`, `ChatMessage`, `UserProfile`).

---

## 2. File Summary & Contract Mappings

| Service Module | Section 8 Export | Methods & Phase 2 Endpoint Bindings | Backwards Compatible Alias |
|---|---|---|---|
| `src/services/asset.service.ts` | `AssetService` | `getAssets()` &rarr; `/api/v1/assets`<br>`getAssetById(id)` &rarr; `/api/v1/assets/:id` | `assetService` |
| `src/services/alert.service.ts` | `AlertService` | `getActiveAlerts()` &rarr; `/api/v1/alerts`<br>`acknowledgeAlert(id)` &rarr; `/api/v1/alerts/:id/acknowledge` | `alertService` |
| `src/services/prediction.service.ts` | `PredictionService` | `getPredictions()` &rarr; `/api/v1/predictions`<br>`getModels()` &rarr; `/api/v1/predictions/models` | `predictionService` |
| `src/services/knowledge.service.ts` | `KnowledgeService` | `getGraphContext()` &rarr; `/api/v1/knowledge/context`<br>`getKnowledgeGraph()` &rarr; `/api/v1/knowledge/graph` | `knowledgeService` |
| `src/services/chat.service.ts` | `ChatService` | `submitQuery(prompt, history)` &rarr; `/api/v1/chat/query`<br>`sendMessage(prompt, history)` &rarr; `/api/v1/chat` | `chatService` |
| `src/services/user.service.ts` | `UserService` | `getProfile()` &rarr; `/api/v1/users/profile`<br>`getCurrentUser()` &rarr; `/api/v1/users/me` | `userService` |
| `src/services/index.ts` | Re-exports | Standard barrel export for all six service modules | &mdash; |

---

## 3. Verification & Build Output

Tested against Next.js 16.2.9 + React 19 production build:

```bash
npm install --legacy-peer-deps
npx tsc --noEmit
npm run build
```

Result:
```
✓ Compiled successfully
✓ Finished TypeScript
✓ Generating static pages (13/13)
```

---

## 4. Installation

Unzip `section8_service_mappings.zip` directly into your project root. It will overwrite existing files under `src/services/` and `src/types/index.ts` while preserving all existing directory structures and behaviors.
