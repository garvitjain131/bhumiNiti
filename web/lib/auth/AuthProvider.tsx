import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, setAuthToken } from "@/lib/api/client";
import type { Language } from "@/lib/i18n/strings";

export type User = { id: number | null; email: string | null; name: string; role: string; institution?: string | null };

export const ROLE_ORDER = ["public", "researcher", "institution_admin", "reviewer", "official", "admin"] as const;
export const ROLE_LABELS: Record<string, string> = {
  public: "Public", researcher: "Researcher", institution_admin: "Institution admin", reviewer: "Reviewer",
  official: "Government official", admin: "Administrator",
};

const PUBLIC_USER: User = { id: null, email: null, name: "Public", role: "public" };
const SESSION_KEY = "lpip.session";
const LANGUAGE_KEY = "lpip.lang";

type AuthContextValue = {
  user: User;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, name: string, password: string, institution?: string) => Promise<void>;
  logout: () => void;
  hasRole: (minimumRole: string) => boolean;
  language: Language;
  setLanguage: (l: Language) => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function saveSession(token: string | null) {
  try {
    if (token) sessionStorage.setItem(SESSION_KEY, token);
    else sessionStorage.removeItem(SESSION_KEY);
  } catch {
    /* storage unavailable: the session lasts for this page only */
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User>(PUBLIC_USER);
  const [ready, setReady] = useState(false);
  const [language, setLanguageState] = useState<Language>("en");

  useEffect(() => {
    let saved: string | null = null;
    try {
      saved = sessionStorage.getItem(SESSION_KEY);
      const l = localStorage.getItem(LANGUAGE_KEY);
      if (l === "hi" || l === "en") setLanguageState(l);
    } catch {
      /* ignore */
    }
    if (!saved) {
      setReady(true);
      return;
    }
    setAuthToken(saved);
    api
      .get("/api/v1/auth/me")
      .then((r) => setUser(r.user))
      .catch(() => {
        setAuthToken(null);
        saveSession(null);
      })
      .finally(() => setReady(true));
  }, []);

  const acceptSession = (r: { token: string; user: User }) => {
    setAuthToken(r.token);
    saveSession(r.token);
    setUser(r.user);
  };

  const login = useCallback(async (email: string, password: string) => {
    acceptSession(await api.post("/api/v1/auth/login", { email, password }));
  }, []);

  const register = useCallback(async (email: string, name: string, password: string, institution?: string) => {
    acceptSession(await api.post("/api/v1/auth/register", { email, name, password, institution }));
  }, []);

  const logout = useCallback(() => {
    setAuthToken(null);
    saveSession(null);
    setUser(PUBLIC_USER);
  }, []);

  const hasRole = useCallback(
    (minimumRole: string) => ROLE_ORDER.indexOf(user.role as never) >= ROLE_ORDER.indexOf(minimumRole as never),
    [user.role],
  );

  const setLanguage = (l: Language) => {
    setLanguageState(l);
    try {
      localStorage.setItem(LANGUAGE_KEY, l);
    } catch {
      /* ignore */
    }
  };

  return (
    <AuthContext.Provider value={{ user, ready, login, register, logout, hasRole, language, setLanguage }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
