import { Outlet, useLocation } from "react-router-dom";
import { useState } from "react";
import BottomNav from "./BottomNav.jsx";
import ScanSheet from "./ScanSheet.jsx";
export default function AppShell(){const[scanOpen,setScanOpen]=useState(false);const location=useLocation();return <div className="mx-auto min-h-screen max-w-3xl bg-linen pb-32 text-ink"><div key={location.pathname} className="page-enter"><Outlet/></div><BottomNav onScan={()=>setScanOpen(true)}/><ScanSheet open={scanOpen} onClose={()=>setScanOpen(false)}/></div>}
