// API_BASE is empty string in Docker — nginx proxies /api/ to the backend container.
// Set VITE_API_BASE_URL=http://host:8000 in .env only for direct access without proxy.
export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';
