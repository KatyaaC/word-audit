"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, setSession } from "./api";
import type { Role, User } from "./types";

interface AuthContextValue {
  user: User | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  hasRole: (...roles: Role[]) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);
const KEY = "wordaudit.session";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) {
        const s = JSON.parse(raw) as { token: string; user: User };
        setSession(s.token, s.user);
        setUser(s.user);
      }
    } catch {
      /* storage blocked: stay signed out */
    }
    setReady(true);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.login(email, password);
    setSession(res.access_token, res.user);
    setUser(res.user);
    try {
      localStorage.setItem(KEY, JSON.stringify({ token: res.access_token, user: res.user }));
    } catch {
      /* ignore */
    }
  }, []);

  const logout = useCallback(() => {
    setSession(null, null);
    setUser(null);
    try {
      localStorage.removeItem(KEY);
    } catch {
      /* ignore */
    }
  }, []);

  const hasRole = useCallback((...roles: Role[]) => !!user && roles.includes(user.role), [user]);

  return <AuthContext.Provider value={{ user, ready, login, logout, hasRole }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
