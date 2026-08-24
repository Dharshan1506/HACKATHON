import React, { useState } from 'react';
import { UploadCloud, CheckCircle2, RefreshCw, FileText, ArrowRight, Shield } from 'lucide-react';
import { uploadProductImage } from '../services/api';
import type { ComplianceReport } from '../types';

interface UploadProductProps {
  onUploaded: (reportId: number) => void;
  setActiveTab: (tab: 'home' | 'scan' | 'upload' | 'reports') => void;
}

export const UploadProduct: React.FC<UploadProductProps> = ({ onUploaded, setActiveTab }) => {
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState('Packaged Food');
  const [isUploading, setIsUploading] = useState(false);
  const [successReport, setSuccessReport] = useState<ComplianceReport | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('category', category);

      const res = await uploadProductImage(formData);
      setSuccessReport(res);
    } catch (err) {
      console.error("Upload error:", err);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-10 pb-12">
      {/* Header */}
      <div className="glass-card p-8 rounded-2xl border border-slate-800 text-center space-y-3">
        <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 text-indigo-400 mx-auto flex items-center justify-center border border-indigo-500/20">
          <UploadCloud className="w-6 h-6" />
        </div>
        <h1 className="text-3xl font-black text-white">Upload Product Package</h1>
        <p className="text-slate-400 text-sm max-w-lg mx-auto">
          Upload packaged commodity artwork or photo labels to automatically extract declarations, 
          run legal rules validation, and save official compliance audit logs.
        </p>
      </div>

      {successReport ? (
        <div className="glass-card p-8 rounded-2xl border border-emerald-500/30 text-center space-y-6">
          <div className="w-16 h-16 rounded-full bg-emerald-500/10 text-emerald-400 mx-auto flex items-center justify-center border border-emerald-500/30">
            <CheckCircle2 className="w-8 h-8" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-white">Product Successfully Audited!</h2>
            <p className="text-slate-400 text-sm mt-1">
              Report <span className="font-mono text-cyan-400">{successReport.report_code}</span> generated for {successReport.product_name}.
            </p>
          </div>

          <div className="inline-flex items-center gap-3 bg-slate-900 px-6 py-3 rounded-xl border border-slate-800 text-sm">
            <span className="text-slate-400">Compliance Score:</span>
            <span className="text-2xl font-black text-emerald-400">{successReport.compliance_score}%</span>
            <span className={`badge-${successReport.compliance_status.toLowerCase()}`}>
              {successReport.compliance_status}
            </span>
          </div>

          <div className="flex items-center justify-center gap-4 pt-4">
            <button
              onClick={() => {
                onUploaded(successReport.id);
                setActiveTab('reports');
              }}
              className="px-6 py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-bold text-sm flex items-center gap-2 shadow-lg shadow-cyan-500/20"
            >
              <FileText className="w-4 h-4" />
              <span>Inspect Full Audit Report</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="glass-card p-8 rounded-2xl border border-slate-800 space-y-6">
          <div className="space-y-4">
            <label className="block text-sm font-semibold text-slate-200">
              Packaging Image / Label File
            </label>
            <div className="relative border-2 border-dashed border-slate-700 hover:border-indigo-500 rounded-xl p-8 text-center cursor-pointer transition-colors bg-slate-900/50">
              <input
                type="file"
                accept="image/*"
                onChange={handleFileChange}
                required
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              />
              <div className="space-y-3">
                <div className="w-12 h-12 rounded-full bg-indigo-500/10 text-indigo-400 mx-auto flex items-center justify-center">
                  <UploadCloud className="w-6 h-6" />
                </div>
                {file ? (
                  <div className="text-sm font-bold text-white flex items-center justify-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span>{file.name} ({(file.size / 1024).toFixed(1)} KB)</span>
                  </div>
                ) : (
                  <>
                    <div className="text-sm text-slate-300">
                      <span className="font-bold text-indigo-400">Click to choose image</span> or drop file here
                    </div>
                    <p className="text-xs text-slate-500">Supports JPG, PNG, WEBP packaging images</p>
                  </>
                )}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-2">
                Commodity Category
              </label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full px-4 py-3 rounded-xl bg-slate-900 border border-slate-800 text-slate-100 text-sm focus:outline-none focus:border-indigo-500"
              >
                <option value="Packaged Food">Packaged Food</option>
                <option value="Dairy & Beverages">Dairy & Beverages</option>
                <option value="Cosmetics & Personal Care">Cosmetics & Personal Care</option>
                <option value="Electronics & Appliances">Electronics & Appliances</option>
                <option value="General Goods">General Goods</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-2">
                Legal Framework
              </label>
              <div className="px-4 py-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-400 flex items-center gap-2">
                <Shield className="w-4 h-4 text-cyan-400" />
                <span>Legal Metrology Act, 2009 (Rules 2011)</span>
              </div>
            </div>
          </div>

          <button
            type="submit"
            disabled={!file || isUploading}
            className="w-full py-4 rounded-xl bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-500 hover:to-blue-500 disabled:opacity-50 text-white font-bold text-sm shadow-xl shadow-indigo-600/20 flex items-center justify-center gap-2 transition-all"
          >
            {isUploading ? (
              <>
                <RefreshCw className="w-5 h-5 animate-spin" />
                <span>Processing & Verifying Legal Metrology Rules...</span>
              </>
            ) : (
              <>
                <UploadCloud className="w-5 h-5" />
                <span>Upload & Start Automated Audit</span>
              </>
            )}
          </button>
        </form>
      )}
    </div>
  );
};
