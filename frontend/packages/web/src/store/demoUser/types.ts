export interface DemoUserState {
  // ISO timestamp of when the current demo session first became active.
  // Null when no demo session has been started (or after a reset).
  sessionStartedAt: string | null;
}
