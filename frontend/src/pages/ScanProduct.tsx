import React, { useState, useRef } from 'react';
import { 
  Camera, UploadCloud, RefreshCw, Download, ShieldCheck, 
  Trash2, AlertTriangle, 
  Code2, Sparkles, Scale, Info, Edit3
} from 'lucide-react';
import { scanProductImage, getPdfDownloadUrl, updateScanResult } from '../services/api';
import type { ComplianceReport, MandatoryRuleCheck } from '../types';

export const ScanProduct: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [productName, setProductName] = useState('');
  const [category, setCategory] = useState('Packaged Food');
  const [isScanning, setIsScanning] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [report, setReport] = useState<ComplianceReport | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showRawText, setShowRawText] = useState(false);
  const [fields, setFields] = useState<Record<string, string>>({
    commodity_name: '',
    brand: '',
    manufacturer_details: '',
    address: '',
    importer: '',
    country_of_origin: '',
    customer_care: '',
    mrp: '',
    net_quantity: '',
    mfg_date: '',
    expiry_date: '',
    unit_sale_price: ''
  });
  
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      const validTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
      
      if (!validTypes.includes(file.type) && !file.name.match(/\.(jpg|jpeg|png|webp)$/i)) {
        setErrorMsg('Please upload a valid image file (JPG, JPEG, PNG, or WEBP).');
        return;
      }

      setErrorMsg(null);
      setSelectedFile(file);
      setPreviewUrl(URL.createObjectURL(file));
      setReport(null);
    }
  };

  const handleRemoveImage = () => {
    setSelectedFile(null);
    setPreviewUrl(null);
    setReport(null);
    setErrorMsg(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleStartComplianceCheck = async () => {
    if (!selectedFile) {
      setErrorMsg('Please select or upload a packaging image first.');
      return;
    }

    setIsScanning(true);
    setErrorMsg(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      if (productName.trim()) {
        formData.append('product_name', productName.trim());
      }
      formData.append('category', category);

      const res = await scanProductImage(formData);
      setReport(res);
      
      const extractedFields = res.details?.fields || {};
      setFields({
        commodity_name: extractedFields.commodity_name || '',
        brand: extractedFields.brand || '',
        manufacturer_details: extractedFields.manufacturer_details || '',
        address: extractedFields.address || '',
        importer: extractedFields.importer || '',
        country_of_origin: extractedFields.country_of_origin || '',
        customer_care: extractedFields.customer_care || '',
        mrp: extractedFields.mrp || '',
        net_quantity: extractedFields.net_quantity || '',
        mfg_date: extractedFields.mfg_date || '',
        expiry_date: extractedFields.expiry_date || '',
        unit_sale_price: extractedFields.unit_sale_price || ''
      });
    } catch (err: any) {
      console.error("Compliance Check error:", err);
      setErrorMsg(err.response?.data?.detail || 'Failed to connect to backend server. Please verify FastAPI is running.');
    } finally {
      setIsScanning(false);
    }
  };

  const handleUpdateCompliance = async () => {
    if (!report) return;
    setIsUpdating(true);
    setErrorMsg(null);
    try {
      const formData = new FormData();
      formData.append('report_id', String(report.id));
      Object.entries(fields).forEach(([key, val]) => {
        formData.append(key, val);
      });
      const res = await updateScanResult(formData);
      setReport(res);
      alert('Compliance re-evaluated successfully!');
    } catch (err: any) {
      console.error("Update error:", err);
      setErrorMsg(err.response?.data?.detail || 'Failed to update compliance details.');
    } finally {
      setIsUpdating(false);
    }
  };

  const ruleChecks: MandatoryRuleCheck[] = report?.details?.rule_checks || [];

  return (
    <div className="space-y-10 pb-16">
      {/* Page Title & Breadcrumb */}
      <div className="glass-card p-8 rounded-3xl border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 text-cyan-400 text-xs font-semibold mb-2 border border-cyan-500/20">
            <Camera className="w-3.5 h-3.5" />
            <span>Product Scan Hub</span>
          </div>
          <h1 className="text-3xl font-black text-white tracking-tight">
            Packaging Compliance Scanner
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Upload product artwork to perform authentic OCR extraction and Legal Metrology Rules (2011) compliance verification.
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono text-slate-400 bg-slate-900/80 px-4 py-2 rounded-xl border border-slate-800">
          <Scale className="w-4 h-4 text-cyan-400" />
          <span>Section 36 / PCR 2011</span>
        </div>
      </div>

      {errorMsg && (
        <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-sm flex items-center justify-between animate-shake">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 flex-shrink-0" />
            <span>{errorMsg}</span>
          </div>
          <button onClick={() => setErrorMsg(null)} className="text-xs hover:underline font-bold">
            Dismiss
          </button>
        </div>
      )}

      {/* Main Upload & Scan Interface */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Upload, Preview & Controls */}
        <div className="lg:col-span-5 space-y-6">
          <div className="glass-card p-6 sm:p-7 rounded-3xl border border-slate-800 space-y-6 shadow-xl">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-white text-base">1. Upload Packaging Image</h3>
              <span className="text-[11px] text-slate-400 font-mono">JPG, PNG, WEBP</span>
            </div>

            {/* Dropzone / Preview Area */}
            {!previewUrl ? (
              <div 
                onClick={() => fileInputRef.current?.click()}
                className="group relative border-2 border-dashed border-slate-700 hover:border-cyan-500/70 rounded-2xl p-8 text-center cursor-pointer transition-all duration-200 bg-slate-900/40 hover:bg-slate-900/70 flex flex-col items-center justify-center min-h-[260px]"
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/jpg,image/png,image/webp"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <div className="w-14 h-14 rounded-2xl bg-cyan-500/10 text-cyan-400 flex items-center justify-center group-hover:scale-110 group-hover:bg-cyan-500 group-hover:text-white transition-all shadow-lg mb-4">
                  <UploadCloud className="w-7 h-7" />
                </div>
                <p className="text-sm font-bold text-white mb-1">
                  Click to select packaging photo
                </p>
                <p className="text-xs text-slate-400 max-w-xs">
                  Upload principal display panel or nutrition/label side of product
                </p>
                <div className="mt-4 inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-slate-800 text-slate-300 text-[11px] font-mono">
                  <span>Supports: JPG, JPEG, PNG, WEBP</span>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Image Preview */}
                <div className="relative rounded-2xl overflow-hidden bg-slate-950 border border-slate-800 shadow-inner group">
                  <img
                    src={previewUrl}
                    alt="Packaging label preview"
                    className="w-full max-h-80 object-contain mx-auto rounded-xl p-2"
                  />
                  <div className="absolute top-3 right-3 flex items-center gap-2">
                    <button
                      type="button"
                      onClick={handleRemoveImage}
                      className="p-2 rounded-xl bg-rose-500/80 hover:bg-rose-600 text-white shadow-lg backdrop-blur-md transition-all hover:scale-105"
                      title="Remove Image"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <div className="flex items-center justify-between text-xs text-slate-400 bg-slate-900/60 p-3 rounded-xl border border-slate-800">
                  <span className="truncate max-w-[200px] font-mono text-slate-300">
                    {selectedFile?.name}
                  </span>
                  <span>{selectedFile ? (selectedFile.size / 1024).toFixed(1) : 0} KB</span>
                </div>
              </div>
            )}

            {/* Optional Metadata Inputs */}
            <div className="space-y-4 pt-2 border-t border-slate-800/80">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Product / Commodity Name (Optional override)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Pure Wheat Flour / Almond Butter"
                  value={productName}
                  onChange={(e) => setProductName(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-100 text-sm focus:outline-none focus:border-cyan-500 transition-colors"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Commodity Category
                </label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-100 text-sm focus:outline-none focus:border-cyan-500 transition-colors"
                >
                  <option value="Packaged Food">Packaged Food</option>
                  <option value="Dairy & Beverages">Dairy & Beverages</option>
                  <option value="Cosmetics & Personal Care">Cosmetics & Personal Care</option>
                  <option value="Electronics & Appliances">Electronics & Appliances</option>
                  <option value="General Goods">General Packaged Goods</option>
                </select>
              </div>

              {/* Action Buttons */}
              <div className="pt-2 flex flex-col gap-2.5">
                <button
                  type="button"
                  onClick={handleStartComplianceCheck}
                  disabled={!selectedFile || isScanning}
                  className="w-full py-4 rounded-2xl bg-gradient-to-r from-cyan-500 via-blue-600 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 disabled:opacity-50 text-white font-bold text-sm shadow-xl shadow-cyan-500/25 flex items-center justify-center gap-2.5 transition-all active:scale-[0.98]"
                >
                  {isScanning ? (
                    <>
                      <RefreshCw className="w-5 h-5 animate-spin" />
                      <span>Extracting OCR & Evaluating Rules...</span>
                    </>
                  ) : (
                    <>
                      <ShieldCheck className="w-5 h-5" />
                      <span>Start Compliance Check</span>
                    </>
                  )}
                </button>

                {previewUrl && (
                  <button
                    type="button"
                    onClick={handleRemoveImage}
                    className="w-full py-2.5 rounded-xl bg-slate-900 hover:bg-slate-850 text-slate-400 hover:text-rose-400 text-xs font-semibold border border-slate-800 flex items-center justify-center gap-1.5 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                    <span>Remove Image & Reset</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Real Compliance Results Display */}
        <div className="lg:col-span-7 space-y-6">
          {report ? (
            <div className="space-y-6 animate-fade-in">
              {/* Executive Score & Verdict Card */}
              <div className="glass-card p-7 rounded-3xl border border-slate-800 space-y-5 shadow-xl">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-slate-800">
                  <div>
                    <span className="text-xs font-mono text-cyan-400 font-bold px-2.5 py-1 rounded bg-cyan-500/10 border border-cyan-500/20">
                      {report.report_code}
                    </span>
                    <h2 className="text-2xl font-black text-white mt-1.5">{report.product_name}</h2>
                    <p className="text-xs text-slate-400">Category: {report.category}</p>
                  </div>

                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <div className="text-3xl font-black text-white">{report.compliance_score}%</div>
                      <div className="text-[11px] text-slate-400 font-semibold">Compliance Score</div>
                    </div>
                    <span className={`badge-${report.compliance_status.toLowerCase()} text-sm py-2 px-3.5 font-bold`}>
                      {report.compliance_status}
                    </span>
                  </div>
                </div>

                {/* Summary Box */}
                <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-1.5">
                  <div className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                    <span>AI Compliance Assessment</span>
                  </div>
                  <p className="text-sm text-slate-200 leading-relaxed">
                    {report.summary}
                  </p>
                </div>

                {/* Score Breakdown Pills */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-center">
                    <div className="text-xl font-bold text-emerald-400">{report.passed_count || 0}</div>
                    <div className="text-[11px] text-emerald-300 font-medium">Passed Rules</div>
                  </div>

                  <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-center">
                    <div className="text-xl font-bold text-amber-400">{report.warnings_count || 0}</div>
                    <div className="text-[11px] text-amber-300 font-medium">Warnings</div>
                  </div>

                  <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-center">
                    <div className="text-xl font-bold text-rose-400">{report.violations_count || 0}</div>
                    <div className="text-[11px] text-rose-300 font-medium">Violations</div>
                  </div>
                </div>

                {/* Actions & Export */}
                <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-800">
                  <button
                    type="button"
                    onClick={() => setShowRawText(!showRawText)}
                    className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-300 text-xs font-semibold border border-slate-800 transition-colors"
                  >
                    <Code2 className="w-4 h-4 text-cyan-400" />
                    <span>{showRawText ? "Hide Raw OCR Text" : "View Extracted Text"}</span>
                  </button>

                  <a
                    href={getPdfDownloadUrl(report.id)}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-bold text-xs shadow-lg shadow-emerald-500/20 hover:scale-105 transition-all"
                  >
                    <Download className="w-4 h-4" />
                    <span>Download Official PDF Certificate</span>
                  </a>
                </div>

                {/* Toggleable Raw OCR Output */}
                {showRawText && (
                  <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 space-y-4">
                    <div>
                      <div className="text-xs font-mono font-bold text-slate-400 mb-2">Authentic Raw OCR Extracted Stream:</div>
                      <pre className="text-xs font-mono text-cyan-300 whitespace-pre-wrap max-h-48 overflow-y-auto p-3 bg-slate-900/80 rounded-xl border border-slate-850">
                        {report.details?.raw_text || "No raw text recorded."}
                      </pre>
                    </div>

                    {/* Detected Text Segments with Bounding Boxes & Confidence */}
                    {report.details?.bounding_boxes && report.details.bounding_boxes.length > 0 && (
                      <div className="space-y-2 pt-2 border-t border-slate-900">
                        <div className="text-xs font-mono font-bold text-slate-400">OCR Bounding Boxes & Confidences:</div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 max-h-60 overflow-y-auto pr-1">
                          {report.details.bounding_boxes.map((boxItem: any, index: number) => (
                            <div key={index} className="p-2.5 rounded-xl bg-slate-900 border border-slate-850 flex items-center justify-between text-xs">
                              <div className="space-y-0.5 truncate pr-2">
                                <div className="text-slate-150 font-semibold truncate text-[11px]">{boxItem.text}</div>
                                <div className="text-[10px] text-slate-500 font-mono">
                                  Box: [{boxItem.box ? boxItem.box.join(', ') : '0, 0, 0, 0'}]
                                </div>
                              </div>
                              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0 ${
                                boxItem.confidence >= 0.85 
                                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                                  : boxItem.confidence >= 0.7 
                                    ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' 
                                    : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                              }`}>
                                {Math.round(boxItem.confidence * 100)}%
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Review & Correct Extracted Declarations Form */}
              <div className="glass-card p-7 rounded-3xl border border-slate-800 space-y-5 shadow-xl">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <h3 className="font-bold text-white text-base flex items-center gap-2">
                    <Edit3 className="w-5 h-5 text-cyan-400" />
                    <span>Review & Correct Extracted Declarations</span>
                  </h3>
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">AI/NLP Fields</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Product / Commodity Name</label>
                    <input
                      type="text"
                      value={fields.commodity_name || ''}
                      onChange={(e) => setFields({ ...fields, commodity_name: e.target.value })}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-850 text-slate-100 text-xs focus:outline-none focus:border-cyan-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Brand Name</label>
                    <input
                      type="text"
                      value={fields.brand || ''}
                      onChange={(e) => setFields({ ...fields, brand: e.target.value })}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-850 text-slate-100 text-xs focus:outline-none focus:border-cyan-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Manufacturer Name</label>
                    <input
                      type="text"
                      value={fields.manufacturer_details || ''}
                      onChange={(e) => setFields({ ...fields, manufacturer_details: e.target.value })}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-850 text-slate-100 text-xs focus:outline-none focus:border-cyan-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Manufacturer Address</label>
                    <input
                      type="text"
                      value={fields.address || ''}
                      onChange={(e) => setFields({ ...fields, address: e.target.value })}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-850 text-slate-100 text-xs focus:outline-none focus:border-cyan-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Importer Name</label>
                    <input
                      type="text"
                      value={fields.importer || ''}
                      onChange={(e) => setFields({ ...fields, importer: e.target.value })}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-850 text-slate-100 text-xs focus:outline-none focus:border-cyan-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Country of Origin</label>
                    <input
                      type="text"
                      value={fields.country_of_origin || ''}
                      onChange={(e) => setFields({ ...fields, country_of_origin: e.target.value })}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-850 text-slate-100 text-xs focus:outline-none focus:border-cyan-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Consumer Care Details</label>
                    <input
                      type="text"
                      value={fields.customer_care || ''}
                      onChange={(e) => setFields({ ...fields, customer_care: e.target.value })}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-850 text-slate-100 text-xs focus:outline-none focus:border-cyan-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Maximum Retail Price (MRP)</label>
                    <input
                      type="text"
                      value={fields.mrp || ''}
                      onChange={(e) => setFields({ ...fields, mrp: e.target.value })}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-850 text-slate-100 text-xs focus:outline-none focus:border-cyan-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Net Quantity</label>
                    <input
                      type="text"
                      value={fields.net_quantity || ''}
                      onChange={(e) => setFields({ ...fields, net_quantity: e.target.value })}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-850 text-slate-100 text-xs focus:outline-none focus:border-cyan-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Manufacturing Date</label>
                    <input
                      type="text"
                      value={fields.mfg_date || ''}
                      onChange={(e) => setFields({ ...fields, mfg_date: e.target.value })}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-850 text-slate-100 text-xs focus:outline-none focus:border-cyan-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Best Before / Expiry</label>
                    <input
                      type="text"
                      value={fields.expiry_date || ''}
                      onChange={(e) => setFields({ ...fields, expiry_date: e.target.value })}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-850 text-slate-100 text-xs focus:outline-none focus:border-cyan-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Unit Sale Price</label>
                    <input
                      type="text"
                      value={fields.unit_sale_price || ''}
                      onChange={(e) => setFields({ ...fields, unit_sale_price: e.target.value })}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-850 text-slate-100 text-xs focus:outline-none focus:border-cyan-500"
                    />
                  </div>
                </div>

                <button
                  type="button"
                  onClick={handleUpdateCompliance}
                  disabled={isUpdating}
                  className="w-full py-3.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 disabled:opacity-50 text-white font-bold text-xs shadow-lg shadow-emerald-500/20 hover:scale-[1.01] transition-all flex items-center justify-center gap-2"
                >
                  {isUpdating ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Saving Corrections & Recalculating Compliance...</span>
                    </>
                  ) : (
                    <>
                      <RefreshCw className="w-4 h-4" />
                      <span>Save Corrections & Recalculate Compliance</span>
                    </>
                  )}
                </button>
              </div>

              {/* 7 Mandatory Legal Declarations Breakdown */}
              <div className="glass-card p-7 rounded-3xl border border-slate-800 space-y-5 shadow-xl">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-white text-lg flex items-center gap-2">
                    <Scale className="w-5 h-5 text-cyan-400" />
                    <span>7 Mandatory Declarations Audit (PCR 2011)</span>
                  </h3>
                  <span className="text-xs text-slate-400 font-mono">
                    {ruleChecks.length} Criteria Checked
                  </span>
                </div>

                <div className="space-y-3.5">
                  {ruleChecks.map((check) => (
                    <div key={check.rule_id} className="p-4 rounded-2xl bg-slate-900/70 border border-slate-800 hover:border-slate-700 transition-colors space-y-2.5">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono font-bold text-cyan-400 px-2 py-0.5 rounded bg-cyan-500/10">
                            {check.rule_code}
                          </span>
                          <span className="font-bold text-white text-sm">{check.title}</span>
                        </div>
                        <span className={`badge-${check.status.toLowerCase()} self-start sm:self-auto`}>
                          {check.status}
                        </span>
                      </div>

                      <div className="text-[11px] text-slate-400 italic">
                        {check.clause}
                      </div>

                      <div className="text-xs font-mono bg-slate-950 p-2.5 rounded-xl border border-slate-850 text-slate-200 truncate">
                        <span className="text-slate-400">Extracted Value: </span>
                        {check.value ? (
                          <span className="text-emerald-400 font-semibold">{check.value}</span>
                        ) : (
                          <span className="text-rose-400 italic font-semibold">Missing / Undetected</span>
                        )}
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs pt-1">
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
            </div>
          ) : (
            <div className="glass-card p-12 rounded-3xl border border-slate-800 text-center space-y-4 flex flex-col items-center justify-center min-h-[440px] shadow-xl">
              <div className="w-16 h-16 rounded-3xl bg-cyan-500/10 text-cyan-400 flex items-center justify-center border border-cyan-500/20 shadow-inner">
                <Sparkles className="w-8 h-8" />
              </div>
              <h3 className="text-xl font-bold text-white">No Compliance Audit Yet</h3>
              <p className="text-slate-400 text-sm max-w-md leading-relaxed">
                Upload or select a product packaging label on the left and click <b>Start Compliance Check</b> to extract declarations and verify statutory Legal Metrology compliance.
              </p>
              <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-400 max-w-sm flex items-center gap-2 text-left">
                <Info className="w-4 h-4 text-cyan-400 flex-shrink-0" />
                <span>Extracts Net Qty, MRP, Unit Sale Price, Mfg Date, Address, and Customer Care.</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
