export function loadPersistedState<T>(): T | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem("nafaiq:redux:v1");
    if (!raw) return null;
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}
