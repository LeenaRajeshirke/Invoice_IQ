// Presentation/config settings. Thresholds are display settings, NOT model accuracy claims.
export const config = {
  mode: import.meta.env.VITE_API_MODE === 'mock' ? 'mock' : 'live',
  baseUrl: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  maxMB: Number(import.meta.env.VITE_MAX_UPLOAD_MB) || 10,
  high: 90, mid: 70,
}
