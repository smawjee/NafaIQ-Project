# Mobile App — NafaIQ

## Stack (to be chosen by Tayyab)

Recommended: React Native with Expo (shared TypeScript types, same API backend)

## Getting started

```bash
cd apps/mobile
npx create-expo-app@latest . --template blank-typescript
# OR
npx react-native init NafaIQMobile --template react-native-template-typescript
```

## API access

The mobile app calls the same Python FastAPI as the PWA:
```
http://<host>:8000/api/market/snapshot
http://<host>:8000/api/finance/transactions
```

Use the shared types from `packages/shared/`:
```ts
import type { MarketSnapshotItem } from "@nafaiq/shared";
```

## Auth

Same Supabase Auth as the PWA. Use `@supabase/supabase-js`:
```ts
import { createClient } from "@supabase/supabase-js";
const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
```
