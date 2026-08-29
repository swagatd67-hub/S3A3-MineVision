import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Download,
  Edit,
  FileText,
  Printer,
  Share2,
  ShieldAlert,
  X,
} from 'lucide-react';

interface ReportMetadata {
  reportId: string;
  clientName: string;
  assetCode: string;
  inspectorName: string;
  surveyDate: string;
  pipeSegment: string;
  overallGrade: string;
  recommendation: string;
}

const DEFAULT_METADATA: ReportMetadata = {
  reportId: 'PV-2026-001',
  clientName: 'City Municipal Water & Sewer Authority',
  assetCode: 'ASSET-PIPE-DN450-S4B',
  inspectorName: 'Eng. Sarah Jenkins (Certified PACP Inspector)',
  surveyDate: '2026-08-29',
  pipeSegment: 'Sector 4B • Manhole MH-112 to MH-116',
  overallGrade: 'Grade 3 - Moderate Structural Defect',
  recommendation: 'Schedule High-Pressure Jetting cycle to clear silt deposits at 14.8m and conduct spot lining for crack at 38.4m within 30 days.',
};

export default function Reports() {
  const { missionId = 'PV-2026-001' } = useParams<{ missionId: string }>();
  const navigate = useNavigate();

  const [metadata, setMetadata] = useState<ReportMetadata>({
    ...DEFAULT_METADATA,
    reportId: missionId,
  });

  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isShareModalOpen, setIsShareModalOpen] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);

  const handlePrint = () => {
    window.print();
  };

  const handleShare = () => {
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  return (
    <div className="min-h-screen bg-[#0a1617] text-white p-4 sm:p-6 lg:p-8 font-['Inter'] selection:bg-[#a3e635] selection:text-black">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-[#183536]">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/missions')}
            className="p-2 rounded-lg bg-[#0e2425] border border-[#1b3b3a] text-[#5de6ff] hover:bg-[#153837] transition-all cursor-pointer"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-3">
              <FileText className="w-6 h-6 text-[#a3e635]" />
              <h1 className="font-['Poppins'] text-2xl sm:text-3xl font-black uppercase tracking-wider text-white">
                Engineering Inspection Report
              </h1>
            </div>
            <p className="text-[#649c96] text-xs sm:text-sm mt-1 font-['Space_Mono']">
              PACP Condition Assessment • Automated Defect Log • Document Export
            </p>
          </div>
        </div>

        {/* Action Toolbar */}
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={() => setIsEditModalOpen(true)}
            className="px-3.5 py-2 rounded-lg bg-[#0e2425] hover:bg-[#153837] border border-[#1b3b3a] text-[#5de6ff] text-xs font-['Space_Mono'] font-bold flex items-center gap-2 transition-all cursor-pointer"
          >
            <Edit className="w-4 h-4" />
            <span>Edit Metadata</span>
          </button>

          <button
            onClick={handlePrint}
            className="px-3.5 py-2 rounded-lg bg-[#0e2425] hover:bg-[#153837] border border-[#1b3b3a] text-white text-xs font-['Space_Mono'] font-bold flex items-center gap-2 transition-all cursor-pointer"
          >
            <Printer className="w-4 h-4" />
            <span>Print Report</span>
          </button>

          <button
            onClick={() => setIsShareModalOpen(true)}
            className="px-3.5 py-2 rounded-lg bg-[#0e2425] hover:bg-[#153837] border border-[#1b3b3a] text-[#a3e635] text-xs font-['Space_Mono'] font-bold flex items-center gap-2 transition-all cursor-pointer"
          >
            <Share2 className="w-4 h-4" />
            <span>Share</span>
          </button>

          <button
            onClick={handlePrint}
            className="px-4 py-2 rounded-lg bg-[#a3e635] hover:bg-[#b6f059] text-black font-['Poppins'] font-bold text-xs sm:text-sm uppercase tracking-wider flex items-center gap-2 transition-all shadow-[0_0_15px_rgba(163,230,53,0.3)] cursor-pointer"
          >
            <Download className="w-4 h-4" />
            <span>Download PDF</span>
          </button>
        </div>
      </div>

      {/* Main Report Preview Document Container */}
      <div className="max-w-4xl mx-auto my-8 bg-[#0d1f20] border border-[#1b3b3a] rounded-xl p-6 sm:p-10 shadow-2xl flex flex-col gap-8">
        {/* Report Document Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start border-b border-[#1b3b3a] pb-6 gap-4">
          <div>
            <div className="text-[#a3e635] font-['Space_Mono'] text-xs uppercase tracking-widest font-bold mb-1">
              PipeVision Engineering Audit
            </div>
            <h2 className="font-['Poppins'] text-2xl font-black text-white uppercase tracking-wider">
              Pipe Condition Assessment Report
            </h2>
            <div className="text-[#649c96] font-['Space_Mono'] text-xs mt-1">
              Report Ref ID: <strong className="text-white">{metadata.reportId}</strong>
            </div>
          </div>

          <div className="bg-[#071314] p-3 rounded-lg border border-[#173838] text-right font-['Space_Mono'] text-xs text-[#649c96]">
            <div>Date: <strong className="text-white">{metadata.surveyDate}</strong></div>
            <div>Inspector: <strong className="text-white">{metadata.inspectorName}</strong></div>
          </div>
        </div>

        {/* Metadata Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 bg-[#071314] p-5 rounded-lg border border-[#173838] font-['Space_Mono'] text-xs text-[#649c96]">
          <div>
            Client / Authority: <strong className="text-white block mt-0.5">{metadata.clientName}</strong>
          </div>
          <div>
            Asset Identifier: <strong className="text-white block mt-0.5">{metadata.assetCode}</strong>
          </div>
          <div>
            Pipe Segment: <strong className="text-white block mt-0.5">{metadata.pipeSegment}</strong>
          </div>
          <div>
            PACP Overall Condition Grade:
            <strong className="text-[#ff5449] block mt-0.5 font-bold">{metadata.overallGrade}</strong>
          </div>
        </div>

        {/* Defect Log Summary Table */}
        <div className="flex flex-col gap-3">
          <h3 className="font-['Poppins'] text-base font-bold text-white uppercase tracking-wider flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-[#ff5449]" />
            <span>Recorded Defect Log</span>
          </h3>

          <div className="overflow-x-auto border border-[#173838] rounded-lg">
            <table className="w-full text-left border-collapse text-xs font-['Space_Mono']">
              <thead>
                <tr className="bg-[#071314] text-[#5de6ff] border-b border-[#173838]">
                  <th className="p-3">Ref ID</th>
                  <th className="p-3">Chainage (m)</th>
                  <th className="p-3">Defect Description</th>
                  <th className="p-3">Clock Pos</th>
                  <th className="p-3">Severity</th>
                  <th className="p-3">Action Required</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#173838] text-white">
                <tr>
                  <td className="p-3 font-bold text-[#5de6ff]">DEF-001</td>
                  <td className="p-3">14.8 m</td>
                  <td className="p-3">Joint Displacement & Silt Deposit</td>
                  <td className="p-3">03:00</td>
                  <td className="p-3 text-[#ffb4ab]">MEDIUM</td>
                  <td className="p-3 text-[#649c96]">High-Pressure Jetting</td>
                </tr>
                <tr>
                  <td className="p-3 font-bold text-[#5de6ff]">DEF-002</td>
                  <td className="p-3">38.4 m</td>
                  <td className="p-3">Longitudinal Crack (Fracture)</td>
                  <td className="p-3">12:00</td>
                  <td className="p-3 text-[#ff5449] font-bold">CRITICAL</td>
                  <td className="p-3 text-[#649c96]">Spot CIPP Lining</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Field Recommendations */}
        <div className="bg-[#071314] p-5 rounded-lg border border-[#173838] flex flex-col gap-2">
          <h4 className="font-['Poppins'] text-sm font-bold text-[#a3e635] uppercase tracking-wider">
            Engineering Action Plan & Recommendations
          </h4>
          <p className="text-xs font-['Space_Mono'] text-[#9ed4ce] leading-relaxed">
            {metadata.recommendation}
          </p>
        </div>
      </div>

      {/* Edit Metadata Modal */}
      {isEditModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0e2425] border border-[#1b3b3a] rounded-xl p-6 max-w-lg w-full flex flex-col gap-4 shadow-2xl animate-fade-in">
            <div className="flex items-center justify-between">
              <h3 className="font-['Poppins'] text-base font-bold text-white uppercase tracking-wider">
                Edit Report Metadata
              </h3>
              <button onClick={() => setIsEditModalOpen(false)} className="text-[#649c96] hover:text-white cursor-pointer">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex flex-col gap-3 text-xs font-['Space_Mono']">
              <div>
                <label className="text-[#649c96] block mb-1">Client Name</label>
                <input
                  type="text"
                  value={metadata.clientName}
                  onChange={(e) => setMetadata({ ...metadata, clientName: e.target.value })}
                  className="w-full bg-[#071314] border border-[#173838] rounded p-2 text-white font-['Space_Mono']"
                />
              </div>
              <div>
                <label className="text-[#649c96] block mb-1">Inspector Name</label>
                <input
                  type="text"
                  value={metadata.inspectorName}
                  onChange={(e) => setMetadata({ ...metadata, inspectorName: e.target.value })}
                  className="w-full bg-[#071314] border border-[#173838] rounded p-2 text-white font-['Space_Mono']"
                />
              </div>
              <div>
                <label className="text-[#649c96] block mb-1">Recommendations</label>
                <textarea
                  rows={3}
                  value={metadata.recommendation}
                  onChange={(e) => setMetadata({ ...metadata, recommendation: e.target.value })}
                  className="w-full bg-[#071314] border border-[#173838] rounded p-2 text-white font-['Space_Mono']"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setIsEditModalOpen(false)}
                className="px-4 py-2 rounded bg-[#a3e635] text-black font-['Poppins'] font-bold text-xs uppercase cursor-pointer"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Share Modal */}
      {isShareModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0e2425] border border-[#1b3b3a] rounded-xl p-6 max-w-md w-full flex flex-col gap-4 shadow-2xl animate-fade-in">
            <div className="flex items-center justify-between">
              <h3 className="font-['Poppins'] text-base font-bold text-white uppercase tracking-wider">
                Share Inspection Report
              </h3>
              <button onClick={() => setIsShareModalOpen(false)} className="text-[#649c96] hover:text-white cursor-pointer">
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs font-['Space_Mono'] text-[#649c96]">
              Copy secure encrypted engineering link for report {metadata.reportId}:
            </p>

            <div className="flex items-center gap-2">
              <input
                type="text"
                readOnly
                value={`https://pipevision.local/reports/${metadata.reportId}`}
                className="flex-1 bg-[#071314] border border-[#173838] rounded p-2 text-xs font-['Space_Mono'] text-[#5de6ff]"
              />
              <button
                onClick={handleShare}
                className="px-3 py-2 bg-[#a3e635] text-black font-['Poppins'] font-bold text-xs rounded cursor-pointer"
              >
                {copiedLink ? 'Copied!' : 'Copy'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}