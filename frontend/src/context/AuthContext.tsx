import { createContext, useContext, useState, useEffect } from "react";
import type { ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { getMe, logout as apiLogout } from "../api/auth";
import type { User } from "../api/auth";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  setUser: (u: User | null) => void;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  setUser: () => {},
  signOut: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const location = useLocation();
  const pathname = location.pathname;
  const shouldCheckSession = !(
    pathname === "/login" ||
    pathname.startsWith("/login/") ||
    pathname === "/register" ||
    pathname.startsWith("/register/")
  );
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(shouldCheckSession);

  useEffect(() => {
    if (!shouldCheckSession) {
      return;
    }

    getMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, [pathname, shouldCheckSession]);

  async function signOut() {
    await apiLogout().catch(() => {});
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, setUser, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  return useContext(AuthContext);
}
