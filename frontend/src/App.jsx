import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./components/AuthProvider.jsx";
import AppShell from "./components/AppShell.jsx";
import Auth from "./pages/Auth.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Home from "./pages/Home.jsx";
import Predict from "./pages/Predict.jsx";

function Protected({ children }) {
  const { user } = useAuth();
  const location = useLocation();
  return user ? children : <Navigate to="/auth" replace state={{ from: location.pathname }} />;
}
function AppRoutes() {
  const { user } = useAuth();
  return <Routes>
    <Route path="/auth" element={user ? <Navigate to="/home" replace /> : <Auth />} />
    <Route element={<Protected><AppShell /></Protected>}><Route path="/home" element={<Home />} /><Route path="/dashboard" element={<Dashboard />} /><Route path="/predict" element={<Predict />} /></Route>
    <Route path="*" element={<Navigate to={user ? "/home" : "/auth"} replace />} />
  </Routes>;
}
export default function App() { return <AuthProvider><AppRoutes /></AuthProvider>; }
