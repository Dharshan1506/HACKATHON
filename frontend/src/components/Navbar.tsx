import React from 'react';
import { ShieldCheck, Camera, UploadCloud, FileText, CheckCircle2 } from 'lucide-react';

interface NavbarProps {
  activeTab: 'home' | 'scan' | 'upload' | 'reports';
  setActiveTab: (tab: 'home' | 'scan' | 'upload' | 'reports') => void;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, setActiveTab }) => {
  return (
    <header className="sticky top-0 z-50 glass-card border-b border-slate-800/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Brand */}
          <div 
            onClick={() => setActiveTab('home')}
            className="flex items-center gap-3 cursor-pointer group"
          >
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 via-blue-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-cyan-500/20 group-hover:scale-105 transition-transform">
              <ShieldCheck className="w-6 h-6 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-xl tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white via-slate-100 to-slate-300">
                  PackSure <span className="text-cyan-400 font-black">AI</span>
                </span>
                <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                  LM Rules 2011
                </span>
              </div>
              <p className="text-[11px] text-slate-400 -mt-0.5 hidden sm:block">
                Legal Metrology Compliance Checker
              </p>
            </div>
          </div>

          {/* Navigation Links requested by user */}
          <nav className="flex items-center gap-1 sm:gap-2">
            <button
              onClick={() => setActiveTab('home')}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'home'
                  ? 'bg-slate-800 text-cyan-400 border border-cyan-500/30 shadow-sm'
                  : 'text-slate-300 hover:text-white hover:bg-slate-850'
              }`}
            >
              <ShieldCheck className="w-4 h-4" />
              <span>PackSure AI</span>
            </button>

            <button
              onClick={() => setActiveTab('scan')}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'scan'
                  ? 'bg-slate-800 text-cyan-400 border border-cyan-500/30 shadow-sm'
                  : 'text-slate-300 hover:text-white hover:bg-slate-850'
              }`}
            >
              <Camera className="w-4 h-4 text-cyan-400" />
              <span>Scan Product</span>
            </button>

            <button
              onClick={() => setActiveTab('upload')}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'upload'
                  ? 'bg-slate-800 text-cyan-400 border border-cyan-500/30 shadow-sm'
                  : 'text-slate-300 hover:text-white hover:bg-slate-850'
              }`}
            >
              <UploadCloud className="w-4 h-4 text-indigo-400" />
              <span>Upload Product</span>
            </button>

            <button
              onClick={() => setActiveTab('reports')}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'reports'
                  ? 'bg-slate-800 text-cyan-400 border border-cyan-500/30 shadow-sm'
                  : 'text-slate-300 hover:text-white hover:bg-slate-850'
              }`}
            >
              <FileText className="w-4 h-4 text-emerald-400" />
              <span>View Reports</span>
            </button>
          </nav>

          {/* System Status */}
          <div className="hidden lg:flex items-center gap-2 text-xs text-slate-400 border border-slate-800 bg-slate-900/60 px-3 py-1.5 rounded-full">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
            <span>Rules Engine v1.0 Active</span>
          </div>
        </div>
      </div>
    </header>
  );
};
