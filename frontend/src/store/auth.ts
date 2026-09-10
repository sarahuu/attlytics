import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { Token } from "../types/auth";

interface AuthState {
  accessToken: string | null;
  setTokens: (token: Token | null) => void;
  clear: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      setTokens: (token) =>
        set({ accessToken: token ? token.access_token : null }),
      clear: () => set({ accessToken: null }),
      isAuthenticated: () => Boolean(get().accessToken),
    }),
    {
      name: "attlytics-auth",
      // Only the short-lived access token is persisted. The refresh token
      // lives in an HttpOnly cookie, so XSS cannot exfiltrate it.
      partialize: (state) => ({ accessToken: state.accessToken }),
    },
  ),
);

