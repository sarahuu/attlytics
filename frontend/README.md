# Attlytics Frontend

Production-oriented React app (Vite + TypeScript) for the Attlytics API.

## Stack
- **Vite + React 18 + TypeScript**
- **React Router** — routing + auth redirects
- **TanStack Query** — server-state/data fetching
- **Zustand** — auth session (tokens in memory)
- **Axios** — single API client with a **refresh-on-401 interceptor**

## Layout
```
src/
├── config.ts                 # env-driven config (VITE_API_BASE_URL)
├── lib/
│   ├── api.ts                # axios instance + endpoints + refresh interceptor
│   ├── errors.ts             # API error → readable message
│   ├── jwt.ts                # decode JWT payload (client-side)
│   └── queryClient.ts        # TanStack Query defaults
├── store/auth.ts             # auth tokens (memory) + actions
├── components/RequireAuth.tsx# guards routes, redirects to /login
├── pages/
│   ├── LoginPage.tsx
│   ├── RegisterPage.tsx
│   ├── DeviceRegisterPage.tsx  # /device/register?token=…
│   └── HomePage.tsx
└── App.tsx / main.tsx / index.css
```

## Run
```bash
npm install
cp .env.example .env      # set VITE_API_BASE_URL if the API isn't on :8000
npm run dev               # http://localhost:5173
```

## Behavior
- **Register / Login** call `POST /v1/auth/register`, `/login`. Login stores
  the token pair in memory and the axios client attaches `Authorization:
  Bearer <access>` automatically.
- **Automatic refresh** — on a 401 the client calls `POST /v1/auth/refresh`
  once (single-flight), retries the original request; if refresh fails it
  clears the session and sends the user to `/login`.
- **/device/register?token=…** — if you're not logged in you're sent to
  `/login?redirect=<this page incl. token>`, then returned here after login.
  The page decodes the enrollment JWT client-side and shows basic device info.
  The **Confirm** button is intentionally disabled — the confirm endpoint is
  built later.

## Notes
- Tokens are kept in memory (not localStorage) to reduce XSS exposure; a page
  reload therefore requires a fresh login until refresh persistence is added.
- No API URLs are hardcoded — everything is derived from `VITE_API_BASE_URL`.
