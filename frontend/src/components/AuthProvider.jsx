import { createContext, useContext, useMemo, useState } from "react";
const AuthContext = createContext(null);
export function AuthProvider({ children }) {
  const [user,setUser] = useState(() => { try { return JSON.parse(localStorage.getItem("ripple-user")); } catch { return null; } });
  const value = useMemo(() => ({ user,login(email){const next={email};localStorage.setItem("ripple-user",JSON.stringify(next));setUser(next);},logout(){localStorage.removeItem("ripple-user");setUser(null);} }),[user]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
export const useAuth = () => useContext(AuthContext);
