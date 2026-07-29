# Live E2E failure replay

Run the suite and automatically open the first hard failure in a headed browser:

```bash
pnpm test:e2e:live
```

The replay signs in through the visible NafaIQ form using the demo credentials
already stored in `frontend/packages/web/.env`. Credentials are never placed in
the command line or printed. Replay mode also disables traces and uses only the
console reporter, so the password is not persisted in a Playwright artifact and
the original full-suite report is not overwritten. If the journey fails again,
Playwright pauses with the browser and Inspector open at the failure state. If
it passes, the successful end state remains visible for five seconds before the
browser closes automatically.

Override the success delay when needed:

```bash
E2E_REPLAY_SUCCESS_DELAY_MS=10000 pnpm test:e2e:replay -- 1
```

To choose a failure from the latest JSON report:

```bash
pnpm test:e2e:replay -- --list
pnpm test:e2e:replay -- 2
pnpm test:e2e:replay -- <12-character-fingerprint>
```

Close or resume Playwright Inspector when observation is complete. This is a
local workflow; CI remains headless and does not attempt to open a browser.
