// MSW node server shared by every test. Lifecycle is wired in src/setup-tests.ts.
// Per-test overrides go through `server.use(...)`, which setup-tests resets
// between tests so one spec can never leak a handler into the next.
import { setupServer } from "msw/node";

import { handlers } from "./handlers";

export const server = setupServer(...handlers);
