import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { Token } from "../types/auth";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  setTokens: (token: Token | null) => void;
  clear: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      setTokens: (token) =>
        set(
          token
            ? { accessToken: token.access_token, refreshToken: token.refresh_token }
            : { accessToken: null, refreshToken: null },
        ),
      clear: () => set({ accessToken: null, refreshToken: null }),
      isAuthenticated: () => Boolean(get().accessToken),
    }),
    {
      name: "attlytics-auth",
      // Only tokens are persisted — actions/derived state never touch storage.
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
      }),
    },
  ),
);

