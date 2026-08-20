import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { clearToken, getToken, onUnauthorized, setToken } from "../api/client";

interface Auth {
  token: string;
  signIn: (value: string) => void;
  signOut: () => void;
}

const AuthContext = createContext<Auth | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState(getToken);

  // A rejected request anywhere in the app drops straight back to the gate —
  // an expired token should not leave five panels showing "unauthorized".
  useEffect(
    () =>
      onUnauthorized(() => {
        clearToken();
        setTokenState("");
      }),
    [],
  );

  const signIn = useCallback((value: string) => {
    setToken(value);
    setTokenState(value.trim());
  }, []);

  const signOut = useCallback(() => {
    clearToken();
    setTokenState("");
  }, []);

  const value = useMemo(() => ({ token, signIn, signOut }), [token, signIn, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): Auth {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
