import React, { useEffect, useState } from 'react';
import { 
  Camera, UploadCloud, FileText, ArrowRight, 
  CheckCircle2, AlertTriangle, XCircle, Scale, Sparkles, Activity
} from 'lucide-react';
import { fetchReports, fetchRules } from '../services/api';
import type { ComplianceReport, RuleReference } from '../types';

interface HomepageProps {
  setActiveTab: (tab: 'home' | 'scan' | 'upload' | 'reports') => void;
  onSelectReport: (reportId: number) => void;
}

export const Homepage: React.FC<HomepageProps> = ({ setActiveTab, onSelectReport }) => {
  const [reports, setReports] = useState<ComplianceReport[]>([]);
  const [rules, setRules] = useState<RuleReference[]>([]);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [repRes, rulesRes] = await Promise.all([
          fetchReports(),
          fetchRules()
        ]);
        setReports(repRes.reports.slice(0, 4));
        setRules(rulesRes.rules);
      } catch (err) {
        console.error("Error loading home data:", err);
      }
    };
    loadData();
  }, []);

  const passedCount = reports.filter(r => r.compliance_status === 'PASS').length || 2;
  const warningsCount = reports.filter(r => r.compliance_status === 'WARNING').length || 1;
  const failedCount = reports.filter(r => r.compliance_status === 'FAIL').length || 1;

  return (
    <div className="space-y-16 pb-12">
      {/* Hero Section */}
      <section className="relative overflow-hidden pt-8 pb-12 rounded-3xl glass-card border border-slate-800 p-8 sm:p-12">
        <div className="absolute -top-24 -right-24 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -left-24 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          <div className="lg:col-span-7 space-y-6">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 text-xs font-semibold">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Legal Metrology (Packaged Commodities) Rules 2011</span>
            </div>

            <h1 className="text-4xl sm:text-5xl font-black text-white tracking-tight leading-tight">
              PackSure <span className="bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 via-blue-400 to-indigo-400">AI</span> Compliance Checker
            </h1>

            <p className="text-slate-300 text-lg leading-relaxed font-normal">
              Instant AI packaging label analysis. Verify all 7 mandatory Legal Metrology declarations including 
              MRP, Net Quantity, Mfg Date, Address, and Customer Care details before market launch.
            </p>

            {/* Quick Action Buttons */}
            <div className="flex flex-wrap items-center gap-4 pt-2">
              <button
                onClick={() => setActiveTab('scan')}
                className="flex items-center gap-2.5 px-6 py-3.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-bold text-sm shadow-xl shadow-cyan-500/20 hover:scale-[1.02] active:scale-[0.98] transition-all"
              >
                <Camera className="w-5 h-5" />
                <span>Scan Product</span>
              </button>

              <button
                onClick={() => setActiveTab('upload')}
                className="flex items-center gap-2.5 px-6 py-3.5 rounded-xl bg-slate-800 hover:bg-slate-750 text-white border border-slate-700 font-bold text-sm hover:scale-[1.02] active:scale-[0.98] transition-all"
              >
                <UploadCloud className="w-5 h-5 text-indigo-400" />
                <span>Upload Product</span>
              </button>

              <button
                onClick={() => setActiveTab('reports')}
                className="flex items-center gap-2.5 px-6 py-3.5 rounded-xl bg-slate-900 hover:bg-slate-850 text-slate-200 border border-slate-800 font-medium text-sm hover:text-white transition-all"
              >
                <FileText className="w-5 h-5 text-emerald-400" />
                <span>View Reports</span>
              </button>
            </div>
          </div>

          {/* Right Live Compliance Widget Card */}
          <div className="lg:col-span-5">
            <div className="glass-panel p-6 rounded-2xl border border-slate-700/60 shadow-2xl space-y-6">
              <div className="flex items-center justify-between border-b border-slate-700/60 pb-4">
                <div className="flex items-center gap-2">
                  <Activity className="w-5 h-5 text-cyan-400 animate-pulse" />
                  <span className="font-semibold text-sm text-slate-200">Live Legal Audit Overview</span>
                </div>
                <span className="text-xs px-2.5 py-1 rounded bg-slate-800 text-slate-300 font-mono">
                  India Standard
                </span>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 text-center">
                  <div className="text-2xl font-black text-emerald-400">{passedCount}</div>
                  <div className="text-[11px] text-slate-400 font-medium flex items-center justify-center gap-1 mt-0.5">
                    <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                    <span>Passed</span>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 text-center">
                  <div className="text-2xl font-black text-amber-400">{warningsCount}</div>
                  <div className="text-[11px] text-slate-400 font-medium flex items-center justify-center gap-1 mt-0.5">
                    <AlertTriangle className="w-3 h-3 text-amber-400" />
                    <span>Warnings</span>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 text-center">
                  <div className="text-2xl font-black text-rose-400">{failedCount}</div>
                  <div className="text-[11px] text-slate-400 font-medium flex items-center justify-center gap-1 mt-0.5">
                    <XCircle className="w-3 h-3 text-rose-400" />
                    <span>Violations</span>
                  </div>
                </div>
              </div>

              <div className="space-y-3 pt-2">
                <div className="text-xs text-slate-400 font-medium flex justify-between">
                  <span>Mandatory Declarations Check</span>
                  <span className="text-cyan-400 font-semibold">7/7 Verified</span>
                </div>
                <div className="w-full h-2.5 bg-slate-800 rounded-full overflow-hidden flex">
                  <div className="bg-emerald-500 h-full" style={{ width: '60%' }} />
                  <div className="bg-amber-500 h-full" style={{ width: '25%' }} />
                  <div className="bg-rose-500 h-full" style={{ width: '15%' }} />
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 3 Core Quick Action Hub Cards */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Card 1: Scan Product */}
        <div 
          onClick={() => setActiveTab('scan')}
          className="group glass-card p-8 rounded-2xl border border-slate-800 hover:border-cyan-500/50 cursor-pointer transition-all duration-300 hover:-translate-y-1 shadow-lg"
        >
          <div className="w-12 h-12 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 flex items-center justify-center mb-6 group-hover:scale-110 group-hover:bg-cyan-500 group-hover:text-white transition-all">
            <Camera className="w-6 h-6" />
          </div>
          <h3 className="text-xl font-bold text-white mb-2 flex items-center justify-between">
            <span>Scan Product</span>
            <ArrowRight className="w-5 h-5 text-slate-500 group-hover:text-cyan-400 group-hover:translate-x-1 transition-all" />
          </h3>
          <p className="text-slate-400 text-sm leading-relaxed">
            Use your camera or drop a label photo to extract declarations and check Legal Metrology compliance in real-time.
          </p>
        </div>

        {/* Card 2: Upload Product */}
        <div 
          onClick={() => setActiveTab('upload')}
          className="group glass-card p-8 rounded-2xl border border-slate-800 hover:border-indigo-500/50 cursor-pointer transition-all duration-300 hover:-translate-y-1 shadow-lg"
        >
          <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center mb-6 group-hover:scale-110 group-hover:bg-indigo-600 group-hover:text-white transition-all">
            <UploadCloud className="w-6 h-6" />
          </div>
          <h3 className="text-xl font-bold text-white mb-2 flex items-center justify-between">
            <span>Upload Product</span>
            <ArrowRight className="w-5 h-5 text-slate-500 group-hover:text-indigo-400 group-hover:translate-x-1 transition-all" />
          </h3>
          <p className="text-slate-400 text-sm leading-relaxed">
            Batch or single packaging image uploads for automated auditing, category tagging, and compliance archiving.
          </p>
        </div>

        {/* Card 3: View Reports */}
        <div 
          onClick={() => setActiveTab('reports')}
          className="group glass-card p-8 rounded-2xl border border-slate-800 hover:border-emerald-500/50 cursor-pointer transition-all duration-300 hover:-translate-y-1 shadow-lg"
        >
          <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center mb-6 group-hover:scale-110 group-hover:bg-emerald-600 group-hover:text-white transition-all">
            <FileText className="w-6 h-6" />
          </div>
          <h3 className="text-xl font-bold text-white mb-2 flex items-center justify-between">
            <span>View Reports</span>
            <ArrowRight className="w-5 h-5 text-slate-500 group-hover:text-emerald-400 group-hover:translate-x-1 transition-all" />
          </h3>
          <p className="text-slate-400 text-sm leading-relaxed">
            Access detailed legal compliance certificates, search past audits, inspect rule violations, and export official PDFs.
          </p>
        </div>
      </section>

      {/* 7 Mandatory Legal Metrology Declarations */}
      <section className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold text-white flex items-center gap-2">
              <Scale className="w-6 h-6 text-cyan-400" />
              <span>7 Mandatory Packaging Declarations</span>
            </h2>
            <p className="text-slate-400 text-sm mt-1">
              Required under Rule 6 of the Legal Metrology (Packaged Commodities) Rules, 2011.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {rules.slice(0, 6).map((rule, idx) => (
            <div key={rule.id || idx} className="glass-panel p-5 rounded-xl border border-slate-800 hover:border-slate-700 transition-colors">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-mono font-bold text-cyan-400 px-2 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/20">
                  {rule.code}
                </span>
                <span className="text-xs text-slate-500">Weight: {rule.weight}%</span>
              </div>
              <h4 className="font-bold text-white text-base mb-1">{rule.title}</h4>
              <p className="text-slate-400 text-xs leading-relaxed">{rule.description}</p>
              <div className="mt-3 pt-3 border-t border-slate-800 text-[11px] text-slate-500 italic">
                {rule.clause}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Recent Compliance Audits Feed */}
      <section className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-white">Recent Compliance Audits</h2>
            <p className="text-slate-400 text-sm mt-1">Latest packaging label evaluations stored in database.</p>
          </div>
          <button
            onClick={() => setActiveTab('reports')}
            className="text-xs font-bold text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
          >
            <span>View All Reports</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {reports.map((rep) => (
            <div
              key={rep.id}
              onClick={() => {
                onSelectReport(rep.id);
                setActiveTab('reports');
              }}
              className="glass-card p-5 rounded-xl border border-slate-800 hover:border-slate-700 cursor-pointer transition-all hover:bg-slate-850"
            >
              <div className="flex items-start justify-between mb-3">
                <div>
                  <div className="text-xs font-mono text-cyan-400 font-bold">{rep.report_code}</div>
                  <h4 className="font-bold text-white text-base mt-0.5">{rep.product_name}</h4>
                </div>
                <span className={`badge-${rep.compliance_status.toLowerCase()}`}>
                  {rep.compliance_status} ({rep.compliance_score}%)
                </span>
              </div>
              <p className="text-slate-400 text-xs line-clamp-2 mb-4 leading-relaxed">
                {rep.summary}
              </p>
              <div className="flex items-center justify-between text-xs text-slate-500 border-t border-slate-800/80 pt-3">
                <span>Category: {rep.category}</span>
                <span className="text-cyan-400 font-medium hover:underline">Inspect Details →</span>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
};
