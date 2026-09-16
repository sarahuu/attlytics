// Central, env-driven config. No hardcoded URLs in components/pages.
const rawBase = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const API_BASE_URL = rawBase.replace(/\/+$/, "");
export const API_PREFIX = "/api/v1";

/** Base URL for all API calls, e.g. http://localhost:8000/v1 */
export const API_URL = `${API_BASE_URL}${API_PREFIX}`;

/** Where a user lands after logging in. */
export const DEFAULT_REDIRECT = "/";
