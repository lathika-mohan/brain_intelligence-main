# Section 11 — Strict Shared TypeScript Layouts (Integration Notes)

Brain Intelligence / Industrial Operating Brain (IOB) — Next.js 16 / React 19

This package delivers **Section 11 (Strict Shared TypeScript Layouts)** fully integrated and conformed across the `brain_intelligence` project. All existing mock services, API consumers, and types have been migrated to use these strict domain entities, establishing a single source of truth that is type-safe and compilation-tested.

---

## 1. Overview of Section 11 Changes

Section 11 introduces a set of precise, strict, and enterprise-grade TypeScript shapes for the core domains of the Industrial Operating Brain (IOB) system:

1. **Role & User Layouts**: Enforces system-wide platform roles (`SUPER_ADMIN`, `PLANT_MANAGER`, `CONTROL_ROOM_OPERATOR`, `MAINTENANCE_ENGINEER`) and clearance level checks.
2. **Asset Layout**: Standardizes physical and logical industrial assets, supporting hierarchical modeling with `parentId`.
3. **Alert Layout**: Standardizes telemetry alarms and SCADA triggers with critical severity categories (`INFO`, `WARNING`, `CRITICAL`, `FATAL`).
4. **Prediction Layout**: Standardizes predictive maintenance models, Remaining Useful Life (RUL) estimation, and failure mode analysis.
5. **Knowledge Layout**: Standardizes semantic knowledge graph structures (nodes, dynamic properties, relationships, and target edges).
6. **Chat Layout**: Standardizes operational co-pilot interaction states.
7. **APIResponse Wrapper**: Standardizes synchronous JSON REST API contracts with explicit success flags and error schemas.

---

## 2. Shared Types Baseline (`src/types/index.ts`)

The shared TypeScript layouts are strictly exported matching the specifications exactly:

```typescript
export type Role = 'SUPER_ADMIN' | 'PLANT_MANAGER' | 'CONTROL_ROOM_OPERATOR' | 'MAINTENANCE_ENGINEER';

export interface User {
  id: string;
  username: string;
  email: string;
  role: Role;
  clearanceLevel: number;
}

export interface Asset {
  id: string;
  name: string;
  type: string;
  status: 'OPERATIONAL' | 'DEGRADED' | 'CRITICAL' | 'OFFLINE';
  parentId: string | null;
}

export interface Alert {
  id: string;
  assetId: string;
  severity: 'INFO' | 'WARNING' | 'CRITICAL' | 'FATAL';
  message: string;
  timestamp: string;
  acknowledged: boolean;
}

export interface Prediction {
  id: string;
  assetId: string;
  remainingUsefulLifeDays: number;
  failureProbability: number;
  inferredFaultMechanism: string;
}

export interface Knowledge {
  nodeId: string;
  label: string;
  properties: Record<string, unknown>;
  edges: Array<{ relationship: string; targetId: string }>;
}

export interface Chat {
  messageId: string;
  sender: 'OPERATOR' | 'AI_ENGINE';
  payload: string;
  timestamp: string;
}

export interface APIResponse<T> {
  success: boolean;
  data: T;
  error?: {
    code: string;
    message: string;
    details?: unknown;
  };
}
```

---

## 3. Service Layer Refactoring & Conformity

To ensure the new strict layouts integrate seamlessly and do not break compilation, we have refactored all six foundational Phase 2 API services to use the new strict entities. All legacy alias types (such as `AnomalyAlert`, `PredictionModel`, `KnowledgeNode`, `ChatMessage`, and `UserProfile`) have been superseded by their respective Section 11 replacements:

### `alert.service.ts`
* Conformed `getActiveAlerts()` from `Promise<AnomalyAlert[]>` to `Promise<Alert[]>`.
* Refactored `MOCK_ALERTS` to align exactly with the new `Alert` structure (`severity` of `'INFO' | 'WARNING' | 'CRITICAL' | 'FATAL'` and `message` instead of `description`).

### `asset.service.ts`
* Conformed service interface methods to use `Asset` with statuses `OPERATIONAL`, `DEGRADED`, `CRITICAL`, or `OFFLINE` and support hierarchal parent-child pointers (`parentId`).

### `chat.service.ts`
* Conformed `sendMessage()` to accept `history: Chat[]` and return `Promise<Chat>` instead of the deprecated `ChatMessage` type.
* Refactored client and fallback stubs to return strict `Chat` objects using `messageId`, `sender` (`OPERATOR` / `AI_ENGINE`), and `payload`.

### `knowledge.service.ts`
* Conformed `getGraphContext()` and `getKnowledgeGraph()` to return `Promise<Knowledge[]>` instead of the deprecated `KnowledgeNode[]` type.
* Refactored `MOCK_GRAPH` data to match the strict `Knowledge` layout, properly translating nodes to use `nodeId`, `properties` maps, and explicit directional `edges` arrays.

### `prediction.service.ts`
* Conformed `getPredictions()` and `getModels()` to return strict `Promise<Prediction[]>` instead of `PredictionModel[]`.
* Refactored models metadata stub arrays into the strict Section 11 `Prediction` schema with `remainingUsefulLifeDays`, `failureProbability`, and `inferredFaultMechanism`.

### `user.service.ts`
* Conformed `getProfile()` and `getCurrentUser()` to return strict `Promise<User | null>` and `Promise<User>`.
* Standardized `MOCK_USER` to conform to `User` containing `username`, `role` (`SUPER_ADMIN`), and `clearanceLevel`.

---

## 4. Pre-existing Build and Interceptor Fixes

During integration, we resolved two critical pre-existing repository compilation issues that blocked clean static generation:
1. **`AUTH_TOKEN_KEY` Resolution**: Added the missing token key `AUTH_TOKEN_KEY` to `src/utils/constants.ts` so `src/api/interceptors.ts` can retrieve the Bearer authentication token from a single source of truth.
2. **Generic Storage Wrapper Typing**: Standardized the invocation of the SSR-safe `storage.get` within the request interceptor to correctly align with its static signature, preventing type-parameter exceptions during Next.js build runs.

---

## 5. Verification & Compilation Output

Verified against Next.js 16.2.9 + React 19 + Turbopack production compiler.

```bash
npm install --legacy-peer-deps
npx tsc --noEmit
npm run build
```

Result:
```
▲ Next.js 16.2.9 (Turbopack)
✓ Compiled successfully in 5.6s
✓ Finished TypeScript in 5.5s
✓ Generating static pages (13/13) in 454ms
```

All 13 standard application routes (including the assets, alerts, chats, and predictions panels) compile completely clean.
