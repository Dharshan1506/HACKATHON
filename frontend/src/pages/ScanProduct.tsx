import React, { useState } from 'react';
import { 
  Camera, UploadCloud, RefreshCw, Download, ShieldCheck, Edit3, Sparkles
} from 'lucide-react';
import { scanProductImage, getPdfDownloadUrl } from '../services/api';
import type { ComplianceReport, MandatoryRuleCheck } from '../types';

export const ScanProduct: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [productName, setProductName] = useState('');
  const [category, setCategory] = useState('Packaged Food');
  const [isScanning, setIsScanning] = useState(false);
  const [report, setReport] = useState<ComplianceReport | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      setPreviewUrl(URL.createObjectURL(file));
      setReport(null);
    }
  };

  const handleSampleSelect = (filename: string, name: string) => {
    setProductName(name);
    const blob = new Blob(["sample label"], { type: "image/jpeg" });
    const file = new File([blob], filename, { type: "image/jpeg" });
    setSelectedFile(file);
    setPreviewUrl(`https://images.unsplash.com/photo-1620916566398-39f1143ab7be?auto=format&fit=crop&w=600&q=80`);
    setReport(null);
  };

  const handleScan = async () => {
    if (!selectedFile) return;
    setIsScanning(true);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      if (productName) formData.append('product_name', productName);
      formData.append('category', category);

      const res = await scanProductImage(formData);
      setReport(res);
    } catch (err) {
      console.error("Scan error:", err);
    } finally {
      setIsScanning(false);
    }
  };

  const ruleChecks: MandatoryRuleCheck[] = report?.details?.rule_checks || [];

  return (
    <div className="space-y-10 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 glass-card p-8 rounded-2xl border border-slate-800">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 text-cyan-400 text-xs font-semibold mb-2">
            <Camera className="w-3.5 h-3.5" />
            <span>AI Label Scanner</span>
          </div>
          <h1 className="text-3xl font-black text-white">Scan Product Packaging Label</h1>
          <p className="text-slate-400 text-sm mt-1">
            Capture or upload product packaging to verify mandatory Legal Metrology declarations.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Input & Preview Panel */}
        <div className="lg:col-span-5 space-y-6">
          <div className="glass-card p-6 rounded-2xl border border-slate-800 space-y-6">
            <h3 className="text-lg font-bold text-white flex items-center justify-between">
              <span>Select Label Image</span>
              <span className="text-xs text-slate-400 font-normal">Formats: JPG, PNG, WEBP</span>
            </h3>

            {/* Quick Sample Selector */}
            <div className="space-y-2">
              <label className="text-xs text-slate-400 font-medium">Or Quick Test with Sample Labels:</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => handleSampleSelect('cooking_oil.jpg', 'SunPure Cooking Oil 1L')}
                  className="px-3 py-2 text-xs rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 hover:text-white text-left transition-colors"
                >
                  🌻 Cooking Oil 1L
                </button>
                <button
                  type="button"
                  onClick={() => handleSampleSelect('choco_biscuit.jpg', 'NutriBite Biscuits 120g')}
                  className="px-3 py-2 text-xs rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 hover:text-white text-left transition-colors"
                >
                  🍪 Choco Biscuits 120g
                </button>
                <button
                  type="button"
                  onClick={() => handleSampleSelect('herbal_shampoo.jpg', 'Botanica Shampoo 250ml')}
                  className="px-3 py-2 text-xs rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 hover:text-white text-left transition-colors"
                >
                  🧴 Hair Shampoo 250ml
                </button>
                <button
                  type="button"
                  onClick={() => handleSampleSelect('organic_milk.jpg', 'PureNature Almond Milk 1L')}
                  className="px-3 py-2 text-xs rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 hover:text-white text-left transition-colors"
                >
                  🥛 Almond Milk 1L
                </button>
              </div>
            </div>

            {/* Upload Dropzone */}
            <div className="relative border-2 border-dashed border-slate-700 hover:border-cyan-500 rounded-xl p-6 text-center cursor-pointer transition-colors bg-slate-900/50">
              <input
                type="file"
                accept="image/*"
                onChange={handleFileChange}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              />
              {previewUrl ? (
                <div className="relative group">
                  <img
                    src={previewUrl}
                    alt="Packaging preview"
                    className="max-h-64 mx-auto rounded-lg object-contain shadow-lg"
                  />
                  <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center rounded-lg transition-opacity">
                    <span className="text-white text-xs font-semibold flex items-center gap-1.5">
                      <RefreshCw className="w-4 h-4" /> Change Image
                    </span>
                  </div>
                </div>
              ) : (
                <div className="space-y-3 py-4">
                  <div className="w-12 h-12 rounded-full bg-cyan-500/10 text-cyan-400 mx-auto flex items-center justify-center">
                    <UploadCloud className="w-6 h-6" />
                  </div>
                  <div className="text-sm text-slate-300">
                    <span className="font-bold text-cyan-400">Click to upload</span> or drag and drop
                  </div>
                  <p className="text-xs text-slate-500">Packaging principal display panel photo</p>
                </div>
              )}
            </div>

            {/* Metadata Fields */}
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Product Name / Commodity (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. Refined Sunflower Oil"
                  value={productName}
                  onChange={(e) => setProductName(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-100 text-sm focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Product Category</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-100 text-sm focus:outline-none focus:border-cyan-500"
                >
                  <option value="Packaged Food">Packaged Food</option>
                  <option value="Dairy & Beverages">Dairy & Beverages</option>
                  <option value="Cosmetics & Personal Care">Cosmetics & Personal Care</option>
                  <option value="Electronics & Appliances">Electronics & Appliances</option>
                  <option value="General Goods">General Packaged Goods</option>
                </select>
              </div>

              <button
                onClick={handleScan}
                disabled={!selectedFile || isScanning}
                className="w-full py-3.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 disabled:opacity-50 text-white font-bold text-sm shadow-lg shadow-cyan-500/20 flex items-center justify-center gap-2 transition-all"
              >
                {isScanning ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Running OCR & AI Compliance Check...</span>
                  </>
                ) : (
                  <>
                    <ShieldCheck className="w-5 h-5" />
                    <span>Analyze Packaging Compliance</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Right Audit Results Display */}
        <div className="lg:col-span-7 space-y-6">
          {report ? (
            <div className="space-y-6">
              {/* Summary Card */}
              <div className="glass-card p-6 rounded-2xl border border-slate-800 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
                  <div>
                    <span className="text-xs font-mono text-cyan-400 font-bold">{report.report_code}</span>
                    <h2 className="text-xl font-bold text-white mt-0.5">{report.product_name}</h2>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <div className="text-2xl font-black text-white">{report.compliance_score}%</div>
                      <div className="text-[11px] text-slate-400 font-medium">Score</div>
                    </div>
                    <span className={`badge-${report.compliance_status.toLowerCase()} py-1.5 px-3 text-sm`}>
                      {report.compliance_status}
                    </span>
                  </div>
                </div>

                <p className="text-slate-300 text-sm leading-relaxed bg-slate-900/60 p-4 rounded-xl border border-slate-800">
                  {report.summary}
                </p>

                <div className="flex flex-wrap items-center justify-between gap-4 pt-2">
                  <div className="flex items-center gap-4 text-xs font-semibold text-slate-300">
                    <span className="text-emerald-400">✓ {report.passed_count || 0} Passed</span>
                    <span className="text-amber-400">⚠ {report.warnings_count || 0} Warnings</span>
                    <span className="text-rose-400">✗ {report.violations_count || 0} Failures</span>
                  </div>

                  <a
                    href={getPdfDownloadUrl(report.id)}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs font-bold transition-all"
                  >
                    <Download className="w-4 h-4" />
                    <span>Download Official PDF Report</span>
                  </a>
                </div>
              </div>

              {/* Extracted Fields Breakdown */}
              <div className="glass-card p-6 rounded-2xl border border-slate-800 space-y-4">
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <Edit3 className="w-5 h-5 text-cyan-400" />
                  <span>OCR Extracted Declarations</span>
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {ruleChecks.map((check) => (
                    <div key={check.rule_id} className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-mono font-bold text-cyan-400">{check.rule_code}</span>
                        <span className={`badge-${check.status.toLowerCase()}`}>{check.status}</span>
                      </div>
                      <div className="font-bold text-slate-100 text-sm">{check.title}</div>
                      <div className="text-xs font-mono text-slate-300 bg-slate-950 p-2 rounded border border-slate-850 truncate">
                        {check.value || <span className="text-rose-400 italic">Not Declared / Missing</span>}
                      </div>
                      <p className="text-[11px] text-slate-400 leading-tight">{check.finding}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="glass-card p-12 rounded-2xl border border-slate-800 text-center space-y-4 flex flex-col items-center justify-center min-h-[400px]">
              <div className="w-16 h-16 rounded-2xl bg-cyan-500/10 text-cyan-400 flex items-center justify-center border border-cyan-500/20">
                <Sparkles className="w-8 h-8" />
              </div>
              <h3 className="text-xl font-bold text-white">Ready to Verify Packaging</h3>
              <p className="text-slate-400 text-sm max-w-md">
                Select an image on the left or click one of the quick test sample labels to run OCR and Legal Metrology rules analysis.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
