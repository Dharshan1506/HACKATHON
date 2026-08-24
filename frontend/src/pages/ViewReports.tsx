import React, { useEffect, useState } from 'react';
import { 
  FileText, Search, Download, X, Scale, Eye, RefreshCw
} from 'lucide-react';
import { fetchReports, fetchReportDetail, getPdfDownloadUrl } from '../services/api';
import type { ComplianceReport, MandatoryRuleCheck } from '../types';

interface ViewReportsProps {
  initialSelectedId?: number | null;
}

export const ViewReports: React.FC<ViewReportsProps> = ({ initialSelectedId }) => {
  const [reports, setReports] = useState<ComplianceReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedReport, setSelectedReport] = useState<ComplianceReport | null>(null);

  const loadReports = async () => {
    setLoading(true);
    try {
      const res = await fetchReports(statusFilter === 'ALL' ? undefined : statusFilter, searchQuery);
      setReports(res.reports || []);
      
      if (initialSelectedId && !selectedReport) {
        const detail = await fetchReportDetail(initialSelectedId);
        setSelectedReport(detail);
      }
    } catch (err) {
      console.error("Error fetching reports:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReports();
  }, [statusFilter, searchQuery]);

  const handleOpenDetail = async (id: number) => {
    try {
      const detail = await fetchReportDetail(id);
      setSelectedReport(detail);
    } catch (err) {
      console.error("Error opening detail:", err);
    }
  };

  const modalRuleChecks: MandatoryRuleCheck[] = selectedReport?.details?.rule_checks || [];

  return (
    <div className="space-y-8 pb-16">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 glass-card p-8 rounded-3xl border border-slate-800">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 text-xs font-semibold mb-2 border border-emerald-500/20">
            <FileText className="w-3.5 h-3.5" />
            <span>Audit Repository</span>
          </div>
          <h1 className="text-3xl font-black text-white">Compliance Audit Reports</h1>
          <p className="text-slate-400 text-sm mt-1">
            Search and inspect official Legal Metrology Act compliance audit logs and certificates.
          </p>
        </div>

        {/* Status Tabs */}
        <div className="flex flex-wrap items-center gap-1.5 bg-slate-900/80 p-1.5 rounded-2xl border border-slate-800 self-start md:self-auto">
          {['ALL', 'COMPLIANT', 'MOSTLY COMPLIANT', 'NEEDS REVIEW', 'HIGH RISK'].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                statusFilter === st
                  ? 'bg-slate-800 text-cyan-400 border border-cyan-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Search Input & Refresh */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="w-5 h-5 text-slate-500 absolute left-4 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by product name, brand, or report code (e.g. PSR-8F21)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-12 pr-4 py-3.5 rounded-2xl bg-slate-900 border border-slate-800 text-slate-100 text-sm placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
          />
        </div>
        <button
          onClick={loadReports}
          className="p-3.5 rounded-2xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-white hover:border-slate-700 transition-colors"
          title="Refresh Reports"
        >
          <RefreshCw className="w-5 h-5" />
        </button>
      </div>

      {/* Reports Grid */}
      {loading ? (
        <div className="glass-card p-12 text-center text-slate-400 text-sm rounded-3xl">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-cyan-400" />
          <span>Loading compliance reports...</span>
        </div>
      ) : reports.length === 0 ? (
        <div className="glass-card p-12 text-center text-slate-400 space-y-2 rounded-3xl">
          <FileText className="w-10 h-10 text-slate-600 mx-auto" />
          <p className="font-semibold text-white">No compliance reports found</p>
          <p className="text-xs">Try adjusting your search filter or scan a new product.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {reports.map((rep) => (
            <div
              key={rep.id}
              onClick={() => handleOpenDetail(rep.id)}
              className="glass-card p-6 rounded-3xl border border-slate-800 hover:border-slate-700 cursor-pointer transition-all hover:bg-slate-850/80 space-y-4 shadow-lg hover:-translate-y-0.5"
            >
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-xs font-mono font-bold text-cyan-400 px-2 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/20">
                    {rep.report_code}
                  </span>
                  <h3 className="font-bold text-white text-lg mt-1">{rep.product_name}</h3>
                  <span className="text-xs text-slate-400">{rep.category}</span>
                </div>
                <div className="text-right">
                  <span className={`text-xs font-extrabold px-2.5 py-1 rounded-full border uppercase ${
                    rep.compliance_score >= 90
                      ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                      : rep.compliance_score >= 70
                        ? 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30'
                        : rep.compliance_score >= 40
                          ? 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                          : 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                  }`}>
                    {rep.compliance_score >= 90 ? 'COMPLIANT' : rep.compliance_score >= 70 ? 'MOSTLY COMPLIANT' : rep.compliance_score >= 40 ? 'NEEDS REVIEW' : 'HIGH RISK'} ({rep.compliance_score}%)
                  </span>
                  <div className="text-[11px] text-slate-500 mt-1 font-mono">
                    {new Date(rep.created_at).toLocaleDateString()}
                  </div>
                </div>
              </div>

              <p className="text-slate-300 text-xs leading-relaxed line-clamp-2 bg-slate-950/60 p-3 rounded-xl border border-slate-850">
                {rep.summary}
              </p>

              <div className="flex items-center justify-between text-xs pt-3 border-t border-slate-800/80">
                <div className="flex items-center gap-3 text-slate-400 font-medium">
                  <span className="text-emerald-400 font-semibold">✓ {rep.passed_count} Passed</span>
                  <span className="text-amber-400 font-semibold">⚠ {rep.warnings_count || 0} Warnings</span>
                  <span className="text-rose-400 font-semibold">✗ {rep.violations_count} Violations</span>
                </div>
                <span className="text-cyan-400 font-semibold flex items-center gap-1 hover:underline">
                  <Eye className="w-3.5 h-3.5" />
                  <span>Inspect Audit Details →</span>
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Report Details Modal */}
      {selectedReport && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4 overflow-y-auto">
          <div className="glass-card w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-3xl border border-slate-700 shadow-2xl p-6 sm:p-8 space-y-6">
            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-slate-800 pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold text-cyan-400 px-2.5 py-1 rounded bg-cyan-500/10 border border-cyan-500/20">
                    {selectedReport.report_code}
                  </span>
                  <span className={`text-xs font-extrabold px-2.5 py-1 rounded-full border uppercase ${
                    selectedReport.compliance_score >= 90
                      ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                      : selectedReport.compliance_score >= 70
                        ? 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30'
                        : selectedReport.compliance_score >= 40
                          ? 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                          : 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                  }`}>
                    {selectedReport.compliance_score >= 90 ? 'COMPLIANT' : selectedReport.compliance_score >= 70 ? 'MOSTLY COMPLIANT' : selectedReport.compliance_score >= 40 ? 'NEEDS REVIEW' : 'HIGH RISK'} ({selectedReport.compliance_score}%)
                  </span>
                </div>
                <h2 className="text-2xl font-black text-white mt-1.5">{selectedReport.product_name}</h2>
                <p className="text-xs text-slate-400 mt-0.5">Category: {selectedReport.category}</p>
              </div>

              <button
                onClick={() => setSelectedReport(null)}
                className="p-2 rounded-xl bg-slate-900 text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Summary */}
            <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">Executive Audit Summary</h4>
              <p className="text-sm text-slate-200 leading-relaxed">{selectedReport.summary}</p>
            </div>

            {/* Rule Checks List */}
            <div className="space-y-4">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <Scale className="w-5 h-5 text-cyan-400" />
                <span>Legal Metrology (Packaged Commodities) Rules 2011 Audit Breakdown</span>
              </h3>

              <div className="space-y-3">
                {modalRuleChecks.map((check) => (
                  <div key={check.rule_id} className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-2">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono font-bold text-cyan-400 px-2 py-0.5 rounded bg-cyan-500/10">
                          {check.rule_code}
                        </span>
                        <span className="font-bold text-white text-sm">{check.title}</span>
                      </div>
                      <span className={`text-xs font-bold px-2.5 py-1 rounded-full border self-start sm:self-auto ${
                        check.status === 'PASS'
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                          : check.status === 'WARNING'
                            ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                            : check.status === 'MANUAL REVIEW'
                              ? 'bg-purple-500/10 text-purple-400 border-purple-500/20'
                              : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                      }`}>
                        {check.status}
                      </span>
                    </div>

                    <div className="text-xs text-slate-400 italic">{check.clause}</div>

                    <div className="text-xs font-mono bg-slate-950 p-2.5 rounded-xl border border-slate-850 text-slate-200">
                      Declared Value: {check.value ? <span className="text-emerald-400 font-semibold">{check.value}</span> : <span className="text-rose-400 italic font-semibold">Not Declared / Missing</span>}
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1 text-xs">
                      <div className="text-slate-300">
                        <span className="font-semibold text-slate-400">Finding: </span>
                        {check.finding}
                      </div>
                      <div className="text-cyan-300">
                        <span className="font-semibold text-cyan-400">Remediation: </span>
                        {check.remediation}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Modal Footer Actions */}
            <div className="flex items-center justify-between pt-4 border-t border-slate-800">
              <a
                href={getPdfDownloadUrl(selectedReport.id)}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-bold text-xs shadow-lg shadow-emerald-500/20 hover:scale-105 transition-all"
              >
                <Download className="w-4 h-4" />
                <span>Download Report (PDF)</span>
              </a>

              <button
                onClick={() => setSelectedReport(null)}
                className="px-5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-semibold text-xs transition-colors"
              >
                Close Audit Inspection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
