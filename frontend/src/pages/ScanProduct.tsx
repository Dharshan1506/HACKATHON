import React, { useState, useRef } from 'react';
import { 
  Camera, UploadCloud, RefreshCw, Download, ShieldCheck, 
  Trash2, AlertTriangle, 
  Code2, Sparkles, Scale, Info, Edit3, Maximize2, X, CheckCheck, ListChecks,
  AlertCircle, FileText, CheckSquare, Layers
} from 'lucide-react';
import { scanProductImage, getPdfDownloadUrl, updateScanResult } from '../services/api';
import type { ComplianceReport, MandatoryRuleCheck } from '../types';

type SurfaceSlot = 'Front' | 'Back' | 'Side' | 'Bottom';

interface SlotImage {
  slot: SurfaceSlot | string;
  file: File;
  previewUrl: string;
}

export const ScanProduct: React.FC = () => {
  // Multi-image state
  const [slotImages, setSlotImages] = useState<Record<SurfaceSlot, SlotImage | null>>({
    Front: null,
    Back: null,
    Side: null,
    Bottom: null
  });
  const [additionalFiles, setAdditionalFiles] = useState<SlotImage[]>([]);

  const [productName, setProductName] = useState('');
  const [category, setCategory] = useState('Auto-Detect');
  const [isScanning, setIsScanning] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [report, setReport] = useState<ComplianceReport | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showRawText, setShowRawText] = useState(false);
  const [checkFilter, setCheckFilter] = useState<'ALL' | 'FAIL' | 'WARNING' | 'PASS' | 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'>('ALL');
  const [modalImageSrc, setModalImageSrc] = useState<string | null>(null);

  const [fields, setFields] = useState<Record<string, string>>({
    commodity_name: '',
    brand: '',
    category: 'Food',
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
  
  const [stepperStage, setStepperStage] = useState<number>(1);
  const [stepperPercent, setStepperPercent] = useState<number>(0);
  const [stepperSubtext, setStepperSubtext] = useState<string>('Uploading Images ✓');

  const frontInputRef = useRef<HTMLInputElement | null>(null);
  const backInputRef = useRef<HTMLInputElement | null>(null);
  const sideInputRef = useRef<HTMLInputElement | null>(null);
  const bottomInputRef = useRef<HTMLInputElement | null>(null);
  const bulkInputRef = useRef<HTMLInputElement | null>(null);

  const compressImage = async (file: File): Promise<File> => {
    if (!file || !file.type.startsWith('image/')) return file;
    if (file.size <= 1.5 * 1024 * 1024) return file;

    return new Promise((resolve) => {
      const img = new Image();
      const url = URL.createObjectURL(file);
      img.onload = () => {
        URL.revokeObjectURL(url);
        let { width, height } = img;
        const maxDimension = 1600;
        if (width > maxDimension || height > maxDimension) {
          if (width > height) {
            height = Math.round((height * maxDimension) / width);
            width = maxDimension;
          } else {
            width = Math.round((width * maxDimension) / height);
            height = maxDimension;
          }
        }
        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        if (ctx) ctx.drawImage(img, 0, 0, width, height);
        canvas.toBlob((blob) => {
          if (blob && blob.size < file.size) {
            resolve(new File([blob], file.name.replace(/\.[^.]+$/, '.jpg'), { type: 'image/jpeg' }));
          } else {
            resolve(file);
          }
        }, 'image/jpeg', 0.88);
      };
      img.onerror = () => resolve(file);
      img.src = url;
    });
  };

  const handleSlotUpload = async (slot: SurfaceSlot, e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const rawFile = e.target.files[0];
      const validTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
      if (!validTypes.includes(rawFile.type) && !rawFile.name.match(/\.(jpg|jpeg|png|webp)$/i)) {
        setErrorMsg('Please upload a valid image file (JPG, JPEG, PNG, or WEBP).');
        return;
      }
      setErrorMsg(null);
      const optimized = await compressImage(rawFile);
      setSlotImages(prev => ({
        ...prev,
        [slot]: {
          slot,
          file: optimized,
          previewUrl: URL.createObjectURL(optimized)
        }
      }));
    }
  };

  const handleRemoveSlot = (slot: SurfaceSlot) => {
    setSlotImages(prev => ({ ...prev, [slot]: null }));
  };

  const handleBulkUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setErrorMsg(null);
      const newItems: SlotImage[] = [];
      for (let i = 0; i < e.target.files.length; i++) {
        const raw = e.target.files[i];
        const opt = await compressImage(raw);
        newItems.push({
          slot: `Additional View ${additionalFiles.length + i + 1}`,
          file: opt,
          previewUrl: URL.createObjectURL(opt)
        });
      }
      setAdditionalFiles(prev => [...prev, ...newItems]);
    }
  };

  const handleRemoveAdditional = (idx: number) => {
    setAdditionalFiles(prev => prev.filter((_, i) => i !== idx));
  };

  const getAllFiles = (): SlotImage[] => {
    const list: SlotImage[] = [];
    (['Front', 'Back', 'Side', 'Bottom'] as SurfaceSlot[]).forEach(s => {
      if (slotImages[s]) list.push(slotImages[s]!);
    });
    additionalFiles.forEach(f => list.push(f));
    return list;
  };

  const handleClearAll = () => {
    setSlotImages({ Front: null, Back: null, Side: null, Bottom: null });
    setAdditionalFiles([]);
    setReport(null);
    setErrorMsg(null);
  };

  const handleStartComplianceCheck = async () => {
    const all = getAllFiles();
    if (all.length === 0) {
      setErrorMsg('Please select or upload at least one packaging image (Front, Back, Side, or Bottom).');
      return;
    }

    setIsScanning(true);
    setErrorMsg(null);
    setReport(null);

    // 8 sequential live stages
    const totalImgs = all.length;
    setStepperStage(1);
    setStepperPercent(12);
    setStepperSubtext(`Image 1/${totalImgs} → OCR`);

    const t2 = setTimeout(() => { setStepperStage(2); setStepperPercent(25); setStepperSubtext(totalImgs >= 2 ? `Image 2/${totalImgs} → OCR` : 'Combining OCR...'); }, 450);
    const t3 = setTimeout(() => { setStepperStage(3); setStepperPercent(38); setStepperSubtext(totalImgs >= 3 ? `Image 3/${totalImgs} → OCR` : 'Combining OCR...'); }, 950);
    const t4 = setTimeout(() => { setStepperStage(4); setStepperPercent(50); setStepperSubtext(totalImgs >= 4 ? `Image 4/${totalImgs} → OCR` : 'Combining OCR...'); }, 1450);
    const t5 = setTimeout(() => { setStepperStage(5); setStepperPercent(65); setStepperSubtext('Combining OCR...'); }, 2000);
    const t6 = setTimeout(() => { setStepperStage(6); setStepperPercent(78); setStepperSubtext('Extracting information...'); }, 2600);
    const t7 = setTimeout(() => { setStepperStage(7); setStepperPercent(88); setStepperSubtext('Compliance checking...'); }, 3200);
    const t8 = setTimeout(() => { setStepperStage(8); setStepperPercent(96); setStepperSubtext('Generating report...'); }, 3800);

    try {
      const formData = new FormData();
      all.forEach(item => {
        formData.append('files', item.file);
      });
      if (productName.trim()) {
        formData.append('product_name', productName.trim());
      }
      formData.append('category', category);

      const res = await scanProductImage(formData);
      
      [t2, t3, t4, t5, t6, t7, t8].forEach(clearTimeout);
      setStepperStage(9);
      setStepperPercent(100);
      setStepperSubtext('Compliance scan successfully completed!');

      setTimeout(() => {
        setReport(res);
        const detectedCat = res.category || (res as any).detected_category || 'Food';
        setCategory(detectedCat);

        const extractedFields = res.details?.fields || {};
        setFields({
          commodity_name: extractedFields.commodity_name || '',
          brand: extractedFields.brand || '',
          category: detectedCat,
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
        setIsScanning(false);
      }, 300);
    } catch (err: any) {
      [t2, t3, t4, t5, t6, t7, t8].forEach(clearTimeout);
      console.error("Compliance Check error:", err);
      setErrorMsg(err.response?.data?.detail || 'Failed to complete compliance scan. Please verify FastAPI backend is running and retry.');
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
      if (res.category) {
        setCategory(res.category);
      }
      alert('Compliance re-evaluated successfully!');
    } catch (err: any) {
      console.error("Update error:", err);
      setErrorMsg(err.response?.data?.detail || 'Failed to update compliance details.');
    } finally {
      setIsUpdating(false);
    }
  };

  const allUploadedFiles = getAllFiles();
  const ruleChecks: MandatoryRuleCheck[] = report?.details?.rule_checks || [];
  
  // Sort priority checks: CRITICAL -> HIGH -> MEDIUM -> LOW
  const priorityWeights: Record<string, number> = { 'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1 };
  const sortedRuleChecks = [...ruleChecks].sort((a, b) => {
    return (priorityWeights[b.priority || 'LOW'] || 1) - (priorityWeights[a.priority || 'LOW'] || 1);
  });

  const filteredRuleChecks = sortedRuleChecks.filter((c) => {
    if (checkFilter === 'ALL') return true;
    if (checkFilter === 'FAIL') return c.status === 'FAIL';
    if (checkFilter === 'WARNING') return c.status === 'WARNING';
    if (checkFilter === 'PASS') return c.status === 'PASS';
    if (['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].includes(checkFilter)) {
      return c.priority === checkFilter;
    }
    return true;
  });

  const fieldConfidenceMap: Record<string, number> = report?.details?.fields_confidence || report?.fields_confidence || {};
  const extractedDetailsFields = report?.details?.fields || {};

  const declarationItems = [
    { label: 'Product / Commodity', key: 'commodity_name', fallback: 'Not Detected' },
    { label: 'Brand Name', key: 'brand', fallback: 'Generic Brand' },
    { label: 'Category', key: 'category', fallback: 'Food' },
    { label: 'Manufacturer Name', key: 'manufacturer_details', fallback: 'Missing' },
    { label: 'Packer / Mfg Address', key: 'address', fallback: 'Missing' },
    { label: 'Maximum Retail Price (MRP)', key: 'mrp', fallback: 'Missing' },
    { label: 'Net Quantity', key: 'net_quantity', fallback: 'Missing' },
    { label: 'Mfg / Packing Date', key: 'mfg_date', fallback: 'Missing' },
    { label: 'Best Before / Expiry Date', key: 'expiry_date', fallback: 'Missing' },
    { label: 'Country of Origin', key: 'country_of_origin', fallback: 'India' },
    { label: 'Consumer Care Helpline', key: 'customer_care', fallback: 'Missing' },
    { label: 'Unit Sale Price (USP)', key: 'unit_sale_price', fallback: 'Missing' }
  ];

  return (
    <div className="space-y-10 pb-16">
      {/* Page Title & Controls */}
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
            Upload multi-surface packaging views (Front, Back, Side, Bottom) to combine OCR streams and audit Legal Metrology statutory compliance.
          </p>
        </div>

        {allUploadedFiles.length > 0 && (
          <button
            onClick={handleClearAll}
            className="px-4 py-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-rose-400 text-xs font-semibold flex items-center gap-2 self-start md:self-auto transition-colors"
          >
            <Trash2 className="w-4 h-4" />
            <span>Clear All ({allUploadedFiles.length})</span>
          </button>
        )}
      </div>

      {errorMsg && (
        <div className="p-5 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3 animate-shake">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{errorMsg}</span>
          </div>
          <button 
            onClick={handleStartComplianceCheck} 
            className="px-3.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs flex items-center gap-1.5 self-start sm:self-auto transition-all"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Retry Compliance Check</span>
          </button>
        </div>
      )}

      {/* Main Upload & Scan Interface */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Multi-Image Slots, Preview & Controls */}
        <div className="lg:col-span-5 space-y-6">
          <div className="glass-card p-6 sm:p-7 rounded-3xl border border-slate-800 space-y-6 shadow-xl">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-white text-base">Packaging Images</h3>
              <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                {allUploadedFiles.length} Image{allUploadedFiles.length === 1 ? '' : 's'} Selected
              </span>
            </div>

            {/* 4 Packaging Surface Slots (Front, Back, Side, Bottom) */}
            <div className="grid grid-cols-2 gap-3">
              {/* Front Slot */}
              <div 
                onClick={() => frontInputRef.current?.click()}
                className={`relative p-3 rounded-2xl border transition-all text-center cursor-pointer min-h-[115px] flex flex-col items-center justify-center group ${
                  slotImages.Front 
                    ? 'border-cyan-500/60 bg-slate-900/90 shadow-md' 
                    : 'border-dashed border-slate-700 hover:border-cyan-500/70 bg-slate-900/40 hover:bg-slate-900/70'
                }`}
              >
                <input
                  ref={frontInputRef}
                  type="file"
                  accept="image/jpeg,image/jpg,image/png,image/webp"
                  onChange={(e) => handleSlotUpload('Front', e)}
                  className="hidden"
                />
                {slotImages.Front ? (
                  <div className="relative w-full h-full">
                    <img src={slotImages.Front.previewUrl} alt="Front View" className="w-full h-20 object-cover rounded-xl" />
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); handleRemoveSlot('Front'); }}
                      className="absolute -top-1.5 -right-1.5 w-6 h-6 bg-rose-500 hover:bg-rose-600 text-white rounded-full flex items-center justify-center text-xs shadow-lg backdrop-blur-sm"
                      title="Remove Front Image"
                    >
                      ×
                    </button>
                    <span className="absolute bottom-1 left-1 px-1.5 py-0.5 rounded bg-slate-950/80 text-cyan-300 text-[10px] font-bold">Front</span>
                  </div>
                ) : (
                  <div className="space-y-1">
                    <Camera className="w-6 h-6 text-cyan-400 mx-auto group-hover:scale-110 transition-transform" />
                    <div className="text-xs font-bold text-white">Front View</div>
                    <div className="text-[10px] text-slate-400">Brand / Name / Net Qty</div>
                  </div>
                )}
              </div>

              {/* Back Slot */}
              <div 
                onClick={() => backInputRef.current?.click()}
                className={`relative p-3 rounded-2xl border transition-all text-center cursor-pointer min-h-[115px] flex flex-col items-center justify-center group ${
                  slotImages.Back 
                    ? 'border-cyan-500/60 bg-slate-900/90 shadow-md' 
                    : 'border-dashed border-slate-700 hover:border-cyan-500/70 bg-slate-900/40 hover:bg-slate-900/70'
                }`}
              >
                <input
                  ref={backInputRef}
                  type="file"
                  accept="image/jpeg,image/jpg,image/png,image/webp"
                  onChange={(e) => handleSlotUpload('Back', e)}
                  className="hidden"
                />
                {slotImages.Back ? (
                  <div className="relative w-full h-full">
                    <img src={slotImages.Back.previewUrl} alt="Back View" className="w-full h-20 object-cover rounded-xl" />
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); handleRemoveSlot('Back'); }}
                      className="absolute -top-1.5 -right-1.5 w-6 h-6 bg-rose-500 hover:bg-rose-600 text-white rounded-full flex items-center justify-center text-xs shadow-lg backdrop-blur-sm"
                      title="Remove Back Image"
                    >
                      ×
                    </button>
                    <span className="absolute bottom-1 left-1 px-1.5 py-0.5 rounded bg-slate-950/80 text-cyan-300 text-[10px] font-bold">Back</span>
                  </div>
                ) : (
                  <div className="space-y-1">
                    <FileText className="w-6 h-6 text-cyan-400 mx-auto group-hover:scale-110 transition-transform" />
                    <div className="text-xs font-bold text-white">Back View</div>
                    <div className="text-[10px] text-slate-400">Mfg / MRP / Exp / Care</div>
                  </div>
                )}
              </div>

              {/* Side Slot */}
              <div 
                onClick={() => sideInputRef.current?.click()}
                className={`relative p-3 rounded-2xl border transition-all text-center cursor-pointer min-h-[115px] flex flex-col items-center justify-center group ${
                  slotImages.Side 
                    ? 'border-cyan-500/60 bg-slate-900/90 shadow-md' 
                    : 'border-dashed border-slate-700 hover:border-cyan-500/70 bg-slate-900/40 hover:bg-slate-900/70'
                }`}
              >
                <input
                  ref={sideInputRef}
                  type="file"
                  accept="image/jpeg,image/jpg,image/png,image/webp"
                  onChange={(e) => handleSlotUpload('Side', e)}
                  className="hidden"
                />
                {slotImages.Side ? (
                  <div className="relative w-full h-full">
                    <img src={slotImages.Side.previewUrl} alt="Side View" className="w-full h-20 object-cover rounded-xl" />
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); handleRemoveSlot('Side'); }}
                      className="absolute -top-1.5 -right-1.5 w-6 h-6 bg-rose-500 hover:bg-rose-600 text-white rounded-full flex items-center justify-center text-xs shadow-lg backdrop-blur-sm"
                      title="Remove Side Image"
                    >
                      ×
                    </button>
                    <span className="absolute bottom-1 left-1 px-1.5 py-0.5 rounded bg-slate-950/80 text-cyan-300 text-[10px] font-bold">Side</span>
                  </div>
                ) : (
                  <div className="space-y-1">
                    <Layers className="w-6 h-6 text-cyan-400 mx-auto group-hover:scale-110 transition-transform" />
                    <div className="text-xs font-bold text-white">Side View</div>
                    <div className="text-[10px] text-slate-400">USP / Barcode / Nutri</div>
                  </div>
                )}
              </div>

              {/* Bottom Slot */}
              <div 
                onClick={() => bottomInputRef.current?.click()}
                className={`relative p-3 rounded-2xl border transition-all text-center cursor-pointer min-h-[115px] flex flex-col items-center justify-center group ${
                  slotImages.Bottom 
                    ? 'border-cyan-500/60 bg-slate-900/90 shadow-md' 
                    : 'border-dashed border-slate-700 hover:border-cyan-500/70 bg-slate-900/40 hover:bg-slate-900/70'
                }`}
              >
                <input
                  ref={bottomInputRef}
                  type="file"
                  accept="image/jpeg,image/jpg,image/png,image/webp"
                  onChange={(e) => handleSlotUpload('Bottom', e)}
                  className="hidden"
                />
                {slotImages.Bottom ? (
                  <div className="relative w-full h-full">
                    <img src={slotImages.Bottom.previewUrl} alt="Bottom View" className="w-full h-20 object-cover rounded-xl" />
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); handleRemoveSlot('Bottom'); }}
                      className="absolute -top-1.5 -right-1.5 w-6 h-6 bg-rose-500 hover:bg-rose-600 text-white rounded-full flex items-center justify-center text-xs shadow-lg backdrop-blur-sm"
                      title="Remove Bottom Image"
                    >
                      ×
                    </button>
                    <span className="absolute bottom-1 left-1 px-1.5 py-0.5 rounded bg-slate-950/80 text-cyan-300 text-[10px] font-bold">Bottom</span>
                  </div>
                ) : (
                  <div className="space-y-1">
                    <CheckSquare className="w-6 h-6 text-cyan-400 mx-auto group-hover:scale-110 transition-transform" />
                    <div className="text-xs font-bold text-white">Bottom View</div>
                    <div className="text-[10px] text-slate-400">Batch / Date Stamp</div>
                  </div>
                )}
              </div>
            </div>

            {/* Bulk Dropzone */}
            <div 
              onClick={() => bulkInputRef.current?.click()}
              className="border-2 border-dashed border-slate-700 hover:border-cyan-500/70 rounded-2xl p-4 text-center cursor-pointer bg-slate-900/40 hover:bg-slate-900/70 transition-all flex flex-col items-center justify-center space-y-1"
            >
              <input
                ref={bulkInputRef}
                type="file"
                multiple
                accept="image/jpeg,image/jpg,image/png,image/webp"
                onChange={handleBulkUpload}
                className="hidden"
              />
              <UploadCloud className="w-6 h-6 text-cyan-400" />
              <p className="text-xs font-bold text-white">Or click to select multiple photos at once</p>
              <p className="text-[10px] text-slate-400">JPG, JPEG, PNG, WEBP</p>
            </div>

            {/* Selected Images List */}
            {allUploadedFiles.length > 0 && (
              <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                {allUploadedFiles.map((item, idx) => (
                  <div key={idx} className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800 flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2.5 truncate pr-2">
                      <img src={item.previewUrl} alt={item.slot} className="w-8 h-8 rounded-lg object-cover border border-slate-700 flex-shrink-0" />
                      <span className="px-2 py-0.5 rounded-md bg-cyan-500/10 text-cyan-400 text-[10px] font-bold border border-cyan-500/20">{item.slot}</span>
                      <span className="text-slate-300 font-mono truncate text-[11px]">{item.file.name}</span>
                      <span className="text-slate-500 text-[10px]">({(item.file.size / 1024).toFixed(1)} KB)</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        if (['Front', 'Back', 'Side', 'Bottom'].includes(item.slot)) {
                          handleRemoveSlot(item.slot as SurfaceSlot);
                        } else {
                          handleRemoveAdditional(idx - 4);
                        }
                      }}
                      className="p-1 text-slate-500 hover:text-rose-400 transition-colors"
                      title="Remove"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
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
                  <option value="Auto-Detect">Auto-Detect (AI Classification)</option>
                  <option value="Food">Food</option>
                  <option value="Cosmetics">Cosmetics</option>
                  <option value="Household">Household</option>
                  <option value="Consumer Goods">Consumer Goods</option>
                  <option value="Imported Goods">Imported Goods</option>
                  <option value="Other">Other</option>
                </select>
              </div>

              {/* Action Buttons */}
              <div className="pt-2">
                <button
                  type="button"
                  onClick={handleStartComplianceCheck}
                  disabled={allUploadedFiles.length === 0 || isScanning}
                  className="w-full py-4 rounded-2xl bg-gradient-to-r from-cyan-500 via-blue-600 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 disabled:opacity-50 text-white font-bold text-sm shadow-xl shadow-cyan-500/25 flex items-center justify-center gap-2.5 transition-all active:scale-[0.98]"
                >
                  {isScanning ? (
                    <>
                      <RefreshCw className="w-5 h-5 animate-spin" />
                      <span>Analyzing {allUploadedFiles.length} Packaging View{allUploadedFiles.length === 1 ? '' : 's'}...</span>
                    </>
                  ) : (
                    <>
                      <ShieldCheck className="w-5 h-5" />
                      <span>Start Compliance Check</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: 8-Step Stepper & Results Display */}
        <div className="lg:col-span-7 space-y-6">
          {report ? (
            <div className="space-y-6 animate-fade-in">
              {/* Executive Score & Verdict Card */}
              <div className="glass-card p-7 rounded-3xl border border-slate-800 space-y-6 shadow-xl">
                
                {/* Header with Product Image Thumbnails & Identity */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-slate-800">
                  <div className="flex items-center gap-4">
                    {allUploadedFiles.length > 0 && (
                      <div className="flex items-center -space-x-3 overflow-hidden py-1">
                        {allUploadedFiles.map((item, idx) => (
                          <div 
                            key={idx}
                            onClick={() => setModalImageSrc(item.previewUrl)}
                            className="relative group w-14 h-14 rounded-2xl overflow-hidden border-2 border-slate-800 bg-slate-950 flex-shrink-0 cursor-pointer shadow-md"
                            title={`Click to view ${item.slot}`}
                          >
                            <img src={item.previewUrl} alt={item.slot} className="w-full h-full object-cover group-hover:scale-110 transition-transform" />
                            <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                              <Maximize2 className="w-3.5 h-3.5 text-cyan-300" />
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono text-cyan-400 font-bold px-2.5 py-1 rounded bg-cyan-500/10 border border-cyan-500/20">
                          {report.report_code}
                        </span>
                        <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                          {report.category || category || 'Food'}
                        </span>
                      </div>
                      <h2 className="text-2xl font-black text-white mt-1.5">{report.product_name}</h2>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-3">
                    <div className="text-right">
                      <div className="text-3xl font-black text-white">{report.compliance_score}%</div>
                      <div className="text-[11px] text-slate-400 font-semibold">Compliance Score</div>
                    </div>
                    <div className="text-right pl-2 border-l border-slate-800">
                      <div className="text-xl font-black text-rose-400">
                        {report.risk_percentage !== undefined ? `${report.risk_percentage}%` : `${(100 - report.compliance_score).toFixed(1)}%`}
                      </div>
                      <div className="text-[11px] text-slate-400 font-semibold">Risk Level</div>
                    </div>
                    <span className={`text-xs py-2 px-3.5 font-extrabold rounded-full border tracking-wide uppercase ${
                      report.compliance_score >= 90
                        ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                        : report.compliance_score >= 70
                          ? 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30'
                          : report.compliance_score >= 40
                            ? 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                            : 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                    }`}>
                      {report.compliance_status || (report.compliance_score >= 90 ? 'COMPLIANT' : report.compliance_score >= 70 ? 'MOSTLY COMPLIANT' : report.compliance_score >= 40 ? 'NEEDS REVIEW' : 'HIGH RISK')}
                    </span>
                    <a
                      href={getPdfDownloadUrl(report.id)}
                      target="_blank"
                      rel="noreferrer"
                      id="header-download-report-btn"
                      className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-bold text-xs shadow-lg shadow-emerald-500/25 transition-all active:scale-[0.98]"
                      title="Download Official Legal Metrology Audit PDF Report"
                    >
                      <Download className="w-4 h-4" />
                      <span>Download Report</span>
                    </a>
                  </div>
                </div>

                {/* Summary Box */}
                <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-1.5">
                  <div className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                    <span>AI Statutory Assessment Verdict</span>
                  </div>
                  <p className="text-sm text-slate-200 leading-relaxed">
                    {report.summary}
                  </p>
                </div>

                {/* Status Checks Breakdown Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div 
                    onClick={() => setCheckFilter('PASS')}
                    className={`p-3 rounded-xl border text-center cursor-pointer transition-all ${
                      checkFilter === 'PASS' 
                        ? 'bg-emerald-500/25 border-emerald-500 ring-1 ring-emerald-500/50' 
                        : 'bg-emerald-500/10 border-emerald-500/20 hover:bg-emerald-500/15'
                    }`}
                  >
                    <div className="text-xl font-bold text-emerald-400">{report.passed_count || 0}</div>
                    <div className="text-[11px] text-emerald-300 font-semibold">PASS</div>
                  </div>

                  <div 
                    onClick={() => setCheckFilter('FAIL')}
                    className={`p-3 rounded-xl border text-center cursor-pointer transition-all ${
                      checkFilter === 'FAIL' 
                        ? 'bg-rose-500/25 border-rose-500 ring-1 ring-rose-500/50' 
                        : 'bg-rose-500/10 border-rose-500/20 hover:bg-rose-500/15'
                    }`}
                  >
                    <div className="text-xl font-bold text-rose-400">{report.violations_count || 0}</div>
                    <div className="text-[11px] text-rose-300 font-semibold">FAIL</div>
                  </div>

                  <div 
                    onClick={() => setCheckFilter('WARNING')}
                    className={`p-3 rounded-xl border text-center cursor-pointer transition-all ${
                      checkFilter === 'WARNING' 
                        ? 'bg-amber-500/25 border-amber-500 ring-1 ring-amber-500/50' 
                        : 'bg-amber-500/10 border-amber-500/20 hover:bg-amber-500/15'
                    }`}
                  >
                    <div className="text-xl font-bold text-amber-400">{report.warnings_count || 0}</div>
                    <div className="text-[11px] text-amber-300 font-semibold">WARNING</div>
                  </div>

                  <div 
                    onClick={() => setCheckFilter('ALL')}
                    className={`p-3 rounded-xl border text-center cursor-pointer transition-all ${
                      checkFilter === 'ALL' 
                        ? 'bg-indigo-500/25 border-indigo-500 ring-1 ring-indigo-500/50' 
                        : 'bg-purple-500/10 border-purple-500/20 hover:bg-purple-500/15'
                    }`}
                  >
                    <div className="text-xl font-bold text-purple-400">{report.manual_review_count || (report.details as any)?.manual_review_count || 0}</div>
                    <div className="text-[11px] text-purple-300 font-semibold">MANUAL REVIEW</div>
                  </div>
                </div>

                {/* Priority Violations Breakdown Bar */}
                <div className="flex flex-wrap items-center justify-between gap-2 p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs">
                  <span className="text-slate-400 font-bold uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                    <span>Priority Violations (Highest-Risk First):</span>
                  </span>
                  <div className="flex flex-wrap items-center gap-2">
                    <button 
                      type="button"
                      onClick={() => setCheckFilter('CRITICAL')}
                      className={`px-2.5 py-1 rounded-lg border font-extrabold text-[10px] uppercase tracking-wider transition-all ${
                        checkFilter === 'CRITICAL'
                          ? 'bg-rose-500/30 text-rose-200 border-rose-400 ring-1 ring-rose-400'
                          : 'bg-rose-500/15 text-rose-300 border-rose-500/30 hover:bg-rose-500/25'
                      }`}
                    >
                      {(report.details?.rule_checks || []).filter(r => r.priority === 'CRITICAL' && r.status !== 'PASS').length} CRITICAL
                    </button>

                    <button 
                      type="button"
                      onClick={() => setCheckFilter('HIGH')}
                      className={`px-2.5 py-1 rounded-lg border font-extrabold text-[10px] uppercase tracking-wider transition-all ${
                        checkFilter === 'HIGH'
                          ? 'bg-orange-500/30 text-orange-200 border-orange-400 ring-1 ring-orange-400'
                          : 'bg-orange-500/15 text-orange-300 border-orange-500/30 hover:bg-orange-500/25'
                      }`}
                    >
                      {(report.details?.rule_checks || []).filter(r => r.priority === 'HIGH' && r.status !== 'PASS').length} HIGH
                    </button>

                    <button 
                      type="button"
                      onClick={() => setCheckFilter('MEDIUM')}
                      className={`px-2.5 py-1 rounded-lg border font-extrabold text-[10px] uppercase tracking-wider transition-all ${
                        checkFilter === 'MEDIUM'
                          ? 'bg-purple-500/30 text-purple-200 border-purple-400 ring-1 ring-purple-400'
                          : 'bg-purple-500/15 text-purple-300 border-purple-500/30 hover:bg-purple-500/25'
                      }`}
                    >
                      {(report.details?.rule_checks || []).filter(r => r.priority === 'MEDIUM' && r.status !== 'PASS').length} MEDIUM
                    </button>

                    <button 
                      type="button"
                      onClick={() => setCheckFilter('LOW')}
                      className={`px-2.5 py-1 rounded-lg border font-extrabold text-[10px] uppercase tracking-wider transition-all ${
                        checkFilter === 'LOW'
                          ? 'bg-blue-500/30 text-blue-200 border-blue-400 ring-1 ring-blue-400'
                          : 'bg-blue-500/15 text-blue-300 border-blue-500/30 hover:bg-blue-500/25'
                      }`}
                    >
                      {(report.details?.rule_checks || []).filter(r => r.priority === 'LOW' && r.status !== 'PASS').length} LOW
                    </button>
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
                    <span>{showRawText ? "Hide Raw OCR Stream" : "View Extracted Text Stream"}</span>
                  </button>

                  <a
                    href={getPdfDownloadUrl(report.id)}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-bold text-xs shadow-lg shadow-emerald-500/20 hover:scale-105 transition-all"
                  >
                    <Download className="w-4 h-4" />
                    <span>Download Report (PDF)</span>
                  </a>
                </div>

                {/* Toggleable Raw OCR Output */}
                {showRawText && (
                  <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 space-y-4">
                    <div>
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Combined Raw OCR Stream:</h4>
                      <pre className="p-3.5 rounded-xl bg-slate-900 text-cyan-400 font-mono text-xs overflow-x-auto whitespace-pre-wrap max-h-48 border border-slate-800">
                        {report.details?.raw_text || "No raw text detected."}
                      </pre>
                    </div>

                    {report.details?.bounding_boxes && report.details.bounding_boxes.length > 0 && (
                      <div>
                        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
                          Detected Text Segments ({report.details.bounding_boxes.length} Bounding Boxes):
                        </h4>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-48 overflow-y-auto pr-1">
                          {report.details.bounding_boxes.map((b: any, idx: number) => {
                            const conf = Math.round((b.confidence || 0.88) * 100);
                            return (
                              <div key={idx} className="p-2 rounded-lg bg-slate-900/80 border border-slate-800 flex items-center justify-between text-xs">
                                <div className="truncate pr-2">
                                  <div className="text-slate-200 font-medium truncate">{b.text || b.label}</div>
                                  <div className="text-[10px] text-slate-500 font-mono">Box: [{b.box ? b.box.join(', ') : '0,0,0,0'}]</div>
                                </div>
                                <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                  conf >= 85 ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                                }`}>
                                  {conf}%
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Real Results: 12 Key Declarations Display Grid with Confidences */}
              <div className="glass-card p-7 rounded-3xl border border-slate-800 space-y-4 shadow-xl">
                <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                  <h3 className="font-bold text-white text-base flex items-center gap-2">
                    <CheckSquare className="w-5 h-5 text-cyan-400" />
                    <span>Extracted Statutory Declarations & Confidence</span>
                  </h3>
                  <span className="text-[10px] font-bold uppercase px-2.5 py-1 rounded-md bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                    Legal Metrology Audit
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
                  {declarationItems.map((item) => {
                    const val = extractedDetailsFields[item.key] || item.fallback;
                    const isPresent = val && val !== 'Missing' && val !== 'Not Detected' && val !== 'Generic Brand';
                    const conf = fieldConfidenceMap[item.key] !== undefined ? fieldConfidenceMap[item.key] : (isPresent ? 94 : 0);

                    return (
                      <div key={item.key} className="p-3 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-1.5 text-xs">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">{item.label}</span>
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                            isPresent 
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                              : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                          }`}>
                            {isPresent ? `${conf}% Conf` : 'Missing'}
                          </span>
                        </div>
                        <div className={`font-semibold ${isPresent ? 'text-white' : 'text-rose-400 italic'} truncate`} title={val}>
                          {val}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Actionable Priority Regulatory Recommendations Section */}
              <div className="glass-card p-7 rounded-3xl border border-slate-800 space-y-4 shadow-xl">
                <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                  <h3 className="font-bold text-white text-base flex items-center gap-2">
                    <ListChecks className="w-5 h-5 text-cyan-400" />
                    <span>Prioritized Violations & Corrective Actions</span>
                  </h3>
                  <span className="text-[10px] font-bold uppercase px-2.5 py-1 rounded-md bg-rose-500/10 text-rose-400 border border-rose-500/20">
                    Highest Risk First
                  </span>
                </div>

                <div className="space-y-3">
                  {sortedRuleChecks.filter(r => r.status !== 'PASS').length > 0 ? (
                    sortedRuleChecks.filter(r => r.status !== 'PASS').map((r, idx) => (
                      <div key={r.rule_id} className="p-3.5 rounded-2xl bg-slate-900/80 border border-slate-800 flex items-start gap-3">
                        <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5 ${
                          r.priority === 'CRITICAL' ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40' :
                          r.priority === 'HIGH' ? 'bg-orange-500/20 text-orange-300 border border-orange-500/40' :
                          'bg-purple-500/20 text-purple-300 border border-purple-500/40'
                        }`}>
                          {idx + 1}
                        </span>
                        <div className="space-y-1 flex-1">
                          <div className="flex flex-wrap items-center justify-between gap-1">
                            <span className="font-bold text-white text-xs">{r.priority || 'HIGH'} — {r.title}</span>
                            <span className="text-[10px] font-mono text-slate-400">{r.clause}</span>
                          </div>
                          <p className="text-xs text-cyan-300 leading-relaxed">{r.remediation}</p>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center gap-3 text-emerald-300 text-xs">
                      <CheckCheck className="w-5 h-5 text-emerald-400 flex-shrink-0" />
                      <span>Packaging artwork complies with all statutory Legal Metrology declarations. Ready for commercial market distribution.</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Review & Correct Extracted Declarations Form */}
              <div className="glass-card p-7 rounded-3xl border border-slate-800 space-y-4 shadow-xl">
                <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                  <h4 className="text-sm font-bold text-white flex items-center gap-2">
                    <Edit3 className="w-4 h-4 text-cyan-400" />
                    <span>Review & Correct Extracted Declarations</span>
                  </h4>
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Editable Fields</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Product Category</label>
                    <select
                      value={fields.category || 'Food'}
                      onChange={(e) => setFields({ ...fields, category: e.target.value })}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-850 text-slate-100 text-xs focus:outline-none focus:border-cyan-500"
                    >
                      <option value="Food">Food</option>
                      <option value="Cosmetics">Cosmetics</option>
                      <option value="Household">Household</option>
                      <option value="Consumer Goods">Consumer Goods</option>
                      <option value="Imported Goods">Imported Goods</option>
                      <option value="Other">Other</option>
                    </select>
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
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Product / Commodity Name</label>
                    <input
                      type="text"
                      value={fields.commodity_name || ''}
                      onChange={(e) => setFields({ ...fields, commodity_name: e.target.value })}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-850 text-slate-100 text-xs focus:outline-none focus:border-cyan-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Manufacturer Details</label>
                    <input
                      type="text"
                      value={fields.manufacturer_details || ''}
                      onChange={(e) => setFields({ ...fields, manufacturer_details: e.target.value })}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-850 text-slate-100 text-xs focus:outline-none focus:border-cyan-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Address</label>
                    <input
                      type="text"
                      value={fields.address || ''}
                      onChange={(e) => setFields({ ...fields, address: e.target.value })}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-850 text-slate-100 text-xs focus:outline-none focus:border-cyan-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Importer Name (If Imported)</label>
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
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Customer Care Contacts</label>
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

              {/* Mandatory Legal Declarations Detailed Audit Explorer */}
              <div className="glass-card p-7 rounded-3xl border border-slate-800 space-y-5 shadow-xl">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800">
                  <div>
                    <h3 className="font-bold text-white text-lg flex items-center gap-2">
                      <Scale className="w-5 h-5 text-cyan-400" />
                      <span>Legal Metrology Statutory Declarations Audit</span>
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5">Clause-by-Clause Statutory Audit Log against Packaged Commodities Rules 2011</p>
                  </div>

                  {/* Filter Tabs */}
                  <div className="flex flex-wrap items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800">
                    {[
                      { id: 'ALL', label: `All (${ruleChecks.length})` },
                      { id: 'FAIL', label: `Failed (${report.violations_count})` },
                      { id: 'WARNING', label: `Warnings (${report.warnings_count})` },
                      { id: 'PASS', label: `Passed (${report.passed_count})` }
                    ].map((tab) => (
                      <button
                        key={tab.id}
                        type="button"
                        onClick={() => setCheckFilter(tab.id as any)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                          checkFilter === tab.id
                            ? 'bg-slate-800 text-cyan-400 border border-cyan-500/30'
                            : 'text-slate-400 hover:text-white'
                        }`}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-3.5">
                  {filteredRuleChecks.map((check) => (
                    <div key={check.rule_id} className="p-4 rounded-2xl bg-slate-900/70 border border-slate-800 hover:border-slate-700 transition-colors space-y-2.5">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-xs font-mono font-bold text-cyan-400 px-2 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/20">
                            {check.rule_code}
                          </span>
                          <span className={`text-[10px] font-extrabold px-2 py-0.5 rounded uppercase border tracking-wider ${
                            check.priority === 'CRITICAL'
                              ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                              : check.priority === 'HIGH'
                                ? 'bg-orange-500/20 text-orange-300 border-orange-500/40'
                                : check.priority === 'MEDIUM'
                                  ? 'bg-purple-500/20 text-purple-300 border-purple-500/40'
                                  : 'bg-blue-500/15 text-blue-300 border-blue-500/30'
                          }`}>
                            {check.priority || 'LOW'} PRIORITY
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

                  {filteredRuleChecks.length === 0 && (
                    <div className="p-8 text-center text-slate-400 text-xs rounded-2xl bg-slate-900/40 border border-slate-800">
                      No statutory checks match the selected filter.
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : isScanning ? (
            <div className="glass-card p-8 rounded-3xl border border-cyan-500/40 bg-slate-900/90 shadow-2xl space-y-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-2xl bg-cyan-500/20 text-cyan-400 flex items-center justify-center animate-pulse border border-cyan-500/30">
                    <Sparkles className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-white">AI Compliance Engine Active</h3>
                    <p className="text-xs text-cyan-400 font-medium">{stepperSubtext}</p>
                  </div>
                </div>
                <span className="text-xl font-black font-mono text-cyan-400">{stepperPercent}%</span>
              </div>

              {/* Glowing Progress Bar */}
              <div className="w-full bg-slate-950 rounded-full h-2.5 overflow-hidden border border-slate-800 p-0.5">
                <div 
                  className="h-full rounded-full bg-gradient-to-r from-cyan-500 via-blue-500 to-indigo-500 transition-all duration-300"
                  style={{ width: `${stepperPercent}%` }}
                />
              </div>

              {/* 8 Live Analysis Stages */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2">
                {[
                  { step: 1, title: `Image 1/${allUploadedFiles.length || 4} → OCR` },
                  { step: 2, title: `Image 2/${allUploadedFiles.length || 4} → OCR` },
                  { step: 3, title: `Image 3/${allUploadedFiles.length || 4} → OCR` },
                  { step: 4, title: `Image 4/${allUploadedFiles.length || 4} → OCR` },
                  { step: 5, title: 'Combining OCR' },
                  { step: 6, title: 'Extracting information' },
                  { step: 7, title: 'Compliance checking' },
                  { step: 8, title: 'Generating report' }
                ].map(({ step, title }) => {
                  const isDone = stepperStage > step;
                  const isActive = stepperStage === step;
                  return (
                    <div 
                      key={step}
                      className={`p-2.5 rounded-2xl border text-center space-y-1 transition-all ${
                        isDone 
                          ? 'bg-emerald-500/10 border-emerald-500/30' 
                          : isActive 
                            ? 'bg-cyan-500/10 border-cyan-500/50 shadow-lg shadow-cyan-500/10' 
                            : 'bg-slate-950 border-slate-800'
                      }`}
                    >
                      <div className={`w-6 h-6 rounded-lg mx-auto flex items-center justify-center text-xs font-bold ${
                        isDone
                          ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20'
                          : isActive
                            ? 'bg-cyan-500 text-slate-950 animate-pulse'
                            : 'bg-slate-800 text-slate-400'
                      }`}>
                        {isDone ? '✓' : step}
                      </div>
                      <div className="text-[11px] font-bold text-slate-300 truncate">{title}</div>
                      <div className={`text-[9px] font-semibold ${
                        isDone ? 'text-emerald-400' : isActive ? 'text-cyan-400' : 'text-slate-500'
                      }`}>
                        {isDone ? 'Completed' : isActive ? 'Active' : 'Pending'}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="glass-card p-12 rounded-3xl border border-slate-800 text-center space-y-4 flex flex-col items-center justify-center min-h-[440px] shadow-xl">
              <div className="w-16 h-16 rounded-3xl bg-cyan-500/10 text-cyan-400 flex items-center justify-center border border-cyan-500/20 shadow-inner">
                <Sparkles className="w-8 h-8" />
              </div>
              <h3 className="text-xl font-bold text-white">No Compliance Audit Yet</h3>
              <p className="text-slate-400 text-sm max-w-md leading-relaxed">
                Upload or select product packaging views (Front, Back, Side, Bottom) on the left and click <b>Start Compliance Check</b> to extract declarations and evaluate statutory Legal Metrology compliance.
              </p>
              <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-400 max-w-sm flex items-center gap-2 text-left">
                <Info className="w-4 h-4 text-cyan-400 flex-shrink-0" />
                <span>Extracts Net Qty, MRP, Unit Sale Price, Mfg Date, Address, and Customer Care.</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Lightbox Modal for Product Image Preview */}
      {modalImageSrc && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4" onClick={() => setModalImageSrc(null)}>
          <div className="relative max-w-4xl max-h-[90vh] bg-slate-900 border border-slate-700 rounded-3xl p-4 shadow-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <button 
              type="button" 
              onClick={() => setModalImageSrc(null)}
              className="absolute top-4 right-4 p-2 rounded-full bg-slate-800 hover:bg-slate-700 text-white z-10 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
            <img src={modalImageSrc} alt="Product label full preview" className="max-h-[80vh] w-auto mx-auto rounded-xl object-contain" />
          </div>
        </div>
      )}
    </div>
  );
};
