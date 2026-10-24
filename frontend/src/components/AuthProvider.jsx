import { createContext, useContext, useMemo, useState } from "react";
const AuthContext = createContext(null);
export function AuthProvider({ children }) {
  const [user,setUser] = useState(() => { try { const saved=JSON.parse(localStorage.getItem("ripple-user")); if(!saved?.token){localStorage.removeItem("ripple-user");return null;} return saved; } catch { return null; } });
  const value = useMemo(() => ({ user, async login(email,password,mode="login") { const response=await fetch(`${import.meta.env.VITE_API_BASE_URL||"http://127.0.0.1:8000"}/api/auth/${mode}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email,password})}); const data=await response.json(); if(!response.ok) throw new Error(data.detail||"Could not sign in."); const next={...data.user,token:data.access_token}; localStorage.setItem("ripple-user",JSON.stringify(next)); setUser(next); }, logout(){localStorage.removeItem("ripple-user");setUser(null);} }),[user]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
export const useAuth = () => useContext(AuthContext);
