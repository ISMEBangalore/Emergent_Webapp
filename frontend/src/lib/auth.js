import { createContext, useCallback, useContext, useEffect, useState } from "react";

const TOKEN_KEY = "leadpulse_token";
const USERNAME_KEY = "leadpulse_username";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const getUsername = () => localStorage.getItem(USERNAME_KEY);

export const setSession = (token, username) => {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USERNAME_KEY, username);
};

export const clearSession = () => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USERNAME_KEY);
};

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(getToken());
  const [username, setUsername] = useState(getUsername());

  // The axios response interceptor clears localStorage directly (it lives
  // outside the React tree); this event lets the app re-render into the
  // logged-out state without a hard page reload.
  useEffect(() => {
    const onUnauthorized = () => {
      setToken(null);
      setUsername(null);
    };
    window.addEventListener("auth:unauthorized", onUnauthorized);
    return () => window.removeEventListener("auth:unauthorized", onUnauthorized);
  }, []);

  const login = useCallback((tok, user) => {
    setSession(tok, user);
    setToken(tok);
    setUsername(user);
  }, []);

  const logout = useCallback(() => {
    clearSession();
    setToken(null);
    setUsername(null);
  }, []);

  return (
    <AuthContext.Provider value={{ token, username, login, logout, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
