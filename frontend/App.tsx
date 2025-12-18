import React from 'react';
import { HashRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom';
import { Home, ListChecks, BellRing, BookOpen, Settings, ShieldCheck } from 'lucide-react';

import Dashboard from './pages/Dashboard';
import Transactions from './pages/Transactions';
import Alerts from './pages/Alerts';
import Simulator from './pages/Simulator';

const Sidebar = () => {
  const location = useLocation();
  
  const navClass = (path: string) => `
    flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200
    ${location.pathname === path 
      ? 'bg-blue-600/10 text-blue-400 border border-blue-600/20' 
      : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'}
  `;

  return (
    <div className="w-64 h-screen bg-[#0F172A] border-r border-slate-800 flex flex-col fixed left-0 top-0 z-50">
      <div className="p-6 flex items-center gap-3 mb-4">
        <div className="bg-blue-600 p-2 rounded-lg shadow-lg shadow-blue-900/20">
           <ShieldCheck size={24} className="text-white" />
        </div>
        <div>
            <h1 className="font-bold text-lg text-slate-100 tracking-tight">Sentinel</h1>
            <p className="text-[10px] text-slate-500 font-medium">Gestion des Risques</p>
        </div>
      </div>
      
      <nav className="flex flex-col gap-1 px-4">
        <NavLink to="/" className={navClass('/')}>
          <Home size={18} />
          Accueil
        </NavLink>
        <NavLink to="/transactions" className={navClass('/transactions')}>
          <ListChecks size={18} />
          Transactions
        </NavLink>
        <NavLink to="/alerts" className={navClass('/alerts')}>
          <BellRing size={18} />
          Alertes
        </NavLink>
        <NavLink to="/simulator" className={navClass('/simulator')}>
          <BookOpen size={18} />
          Démo
        </NavLink>
      </nav>

      <div className="mt-auto p-4 border-t border-slate-800">
        <button className="flex items-center gap-3 px-4 py-3 w-full text-slate-400 hover:text-white hover:bg-slate-800/50 rounded-lg text-sm transition-colors mb-2">
            <Settings size={18} />
            Paramètres
        </button>
        <div className="flex items-center gap-3 px-4 py-2 bg-slate-900 rounded-lg border border-slate-800">
            <div className="w-8 h-8 rounded-full bg-blue-900/50 text-blue-400 border border-blue-800 flex items-center justify-center text-xs font-bold">JD</div>
            <div className="flex flex-col">
                <span className="text-xs text-slate-200 font-medium">Jean Dupont</span>
                <span className="text-[10px] text-slate-500">Analyste Junior</span>
            </div>
        </div>
      </div>
    </div>
  );
};

const App = () => {
  return (
    <HashRouter>
      <div className="flex min-h-screen bg-[#0B1120] text-slate-200 font-sans selection:bg-blue-500/30">
        <Sidebar />
        <main className="ml-64 flex-1 overflow-y-auto h-screen">
          <div className="max-w-6xl mx-auto p-8">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/transactions" element={<Transactions />} />
              <Route path="/alerts" element={<Alerts />} />
              <Route path="/simulator" element={<Simulator />} />
            </Routes>
          </div>
        </main>
      </div>
    </HashRouter>
  );
};

export default App;