const KEY = "nafaiq:redux:v1";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const persistMiddleware = (api: any) => (next: any) => (action: any) => {
  const result = next(action);
  if (typeof window !== "undefined") {
    try {
      const state = api.getState();
      localStorage.setItem(KEY, JSON.stringify(state));
    } catch {
      /* ignore quota errors */
    }
  }
  return result;
};
