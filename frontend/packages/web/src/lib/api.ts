const rawApiUrl = import.meta.env.VITE_API_URL || import.meta.env.VITE_PSX_API_URL;

if (!rawApiUrl && import.meta.env.PROD) {
  throw new Error("Missing VITE_API_URL in production build");
}

export const API_BASE_URL = (rawApiUrl || "http://127.0.0.1:8000").replace(/\/$/, "");

export const apiUrl = (path: string) => {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${cleanPath}`;
};
