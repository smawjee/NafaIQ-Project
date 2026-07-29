# Testing NafaIQ Mobile on a Phone

## Prerequisites
- Node 22+, this repo cloned, deps installed (`npm install`).
- Copy env: `cp .env.example .env.local` and fill in the Supabase values
  (use the project that has Google OAuth configured to test Google sign-in).

## Option A — Expo Go (fastest, no build)
All native modules used here are bundled in Expo Go, so this just works.

1. Install **Expo Go** (App Store / Play Store).
2. Start the dev server:
   ```
   npm start            # = expo start
   ```
3. Same Wi-Fi as the laptop, then scan the QR:
   - **iPhone**: Camera app → tap the banner.
   - **Android**: Expo Go → "Scan QR code".
4. Restricted Wi-Fi? Use a tunnel: `npx expo start --tunnel`.

**Notes**
- Email/password auth works in Expo Go.
- **Google OAuth does NOT work in Expo Go** (it uses the `exp://` scheme, not our
  `nafaiqmobile://` deep link). Use a dev build (Option B) for Google sign-in.
- Requires an Expo Go version that supports SDK 56.

## Option B — Dev / Preview build via EAS (cloud, no Mac/Android SDK needed)
Needed for Google OAuth (custom scheme) and standalone installs.

```
npm i -g eas-cli
eas login                 # your Expo account
eas init                  # creates the EAS project + writes extra.eas.projectId

# Android: installable APK (dev client)
eas build --profile development --platform android

# Android: standalone preview APK (no dev server)
eas build --profile preview --platform android

# iOS: requires an Apple account + your iPhone's UDID registered
eas build --profile development --platform ios
```
- After a **development** build installs, run `npm start` and open it from the
  dev client (it scans the same QR / connects to Metro).
- `eas.json` already defines `development`, `preview`, `production` profiles with
  the public `EXPO_PUBLIC_*` vars (so cloud builds have Supabase config even
  though `.env.local` is gitignored).

## App identifiers
- iOS bundle id / Android package: `com.nafaiq.mobile`
- Deep-link scheme: `nafaiqmobile://`
- For Google OAuth, add the Supabase auth redirect and allow
  `nafaiqmobile://auth/callback` in the Supabase project's URL config.
