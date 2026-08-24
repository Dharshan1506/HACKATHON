import React, { useState } from 'react';
import { Navbar } from './components/Navbar';
import { Footer } from './components/Footer';
import { Homepage } from './pages/Homepage';
import { ScanProduct } from './pages/ScanProduct';
import { UploadProduct } from './pages/UploadProduct';
import { ViewReports } from './pages/ViewReports';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'home' | 'scan' | 'upload' | 'reports'>('home');
  const [selectedReportId, setSelectedReportId] = useState<number | null>(null);

  const handleSelectReport = (reportId: number) => {
    setSelectedReportId(reportId);
    setActiveTab('reports');
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-cyan-500 selection:text-white">
      {/* Header Navbar */}
      <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />

      {/* Main Content View */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 pt-8">
        {activeTab === 'home' && (
          <Homepage 
            setActiveTab={setActiveTab} 
            onSelectReport={handleSelectReport} 
          />
        )}

        {activeTab === 'scan' && (
          <ScanProduct />
        )}

        {activeTab === 'upload' && (
          <UploadProduct 
            onUploaded={handleSelectReport} 
            setActiveTab={setActiveTab} 
          />
        )}

        {activeTab === 'reports' && (
          <ViewReports initialSelectedId={selectedReportId} />
        )}
      </main>

      {/* Footer */}
      <Footer />
    </div>
  );
};

export default App;
