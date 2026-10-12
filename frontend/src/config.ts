// The FastAPI backend from Problem 7. Override with VITE_API_BASE if it runs elsewhere.
export const API_BASE: string = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

// How often the dashboard refreshes (ms).
export const POLL_LIVE_MS = 1200 // while a car is in the pit
export const POLL_IDLE_MS = 5000 // otherwise
