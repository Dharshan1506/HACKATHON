import React from 'react';
import { Shield, ExternalLink, Scale, CheckCircle } from 'lucide-react';

export const Footer: React.FC = () => {
  return (
    <footer className="border-t border-slate-800 bg-slate-950 text-slate-400 py-10 mt-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-8">
          <div className="space-y-3 md:col-span-2">
            <div className="flex items-center gap-2 text-white font-bold text-lg">
              <Shield className="w-5 h-5 text-cyan-400" />
              <span>PackSure AI – Legal Metrology Compliance Checker</span>
            </div>
            <p className="text-sm text-slate-400 max-w-md leading-relaxed">
              Automated computer vision and AI engine for verifying 7 mandatory packaging declarations
              mandated under Section 36 of Legal Metrology Act, 2009 & Packaged Commodities Rules 2011.
            </p>
          </div>

          <div>
            <h4 className="text-white font-semibold text-sm mb-3 flex items-center gap-2">
              <Scale className="w-4 h-4 text-cyan-400" />
              Mandatory Clauses
            </h4>
            <ul className="space-y-2 text-xs">
              <li className="hover:text-slate-200 transition-colors">Rule 6(1)(a): Manufacturer Address</li>
              <li className="hover:text-slate-200 transition-colors">Rule 6(1)(b): Generic Commodity Name</li>
              <li className="hover:text-slate-200 transition-colors">Rule 6(1)(c): Net Quantity & Unit</li>
              <li className="hover:text-slate-200 transition-colors">Rule 6(1)(d): Month & Year of Mfg</li>
              <li className="hover:text-slate-200 transition-colors">Rule 6(1)(e): MRP Inclusive of Taxes</li>
              <li className="hover:text-slate-200 transition-colors">Rule 6(1)(f): Consumer Care Contact</li>
            </ul>
          </div>

          <div>
            <h4 className="text-white font-semibold text-sm mb-3 flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-emerald-400" />
              Compliance Standard
            </h4>
            <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 text-xs space-y-2">
              <div className="flex justify-between">
                <span>Metric Standard:</span>
                <span className="text-slate-200 font-mono">Rule 7 / SI Units</span>
              </div>
              <div className="flex justify-between">
                <span>Unit Sale Price:</span>
                <span className="text-slate-200 font-mono">Amendment 2021</span>
              </div>
              <div className="flex justify-between">
                <span>Inspection Pass Rate:</span>
                <span className="text-emerald-400 font-bold">85%+ Required</span>
              </div>
            </div>
          </div>
        </div>

        <div className="pt-6 border-t border-slate-800/80 text-xs flex flex-col sm:flex-row items-center justify-between gap-4">
          <p>© {new Date().getFullYear()} PackSure AI. Enforcing Legal Metrology Compliance for Packaged Commodities.</p>
          <div className="flex items-center gap-4">
            <a href="https://consumeraffairs.nic.in" target="_blank" rel="noreferrer" className="flex items-center gap-1 hover:text-cyan-400 transition-colors">
              <span>Department of Consumer Affairs</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
};
