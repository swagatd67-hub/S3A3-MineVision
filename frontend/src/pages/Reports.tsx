import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Clock,
  FileText,
  Printer,
  RefreshCw,
  Share2,
  ShieldAlert,
  ShieldCheck,
  X,
  Bot,
  Layers,
} from 'lucide-react';
import { getInspectionReport } from '../api/reports';
import type { EngineeringReport } from '../types/report';

export default function Reports() {
  const { missionId = 'PV-2026-001' } = useParams<{ missionId: string }>();
  const navigate = useNavigate();

  const [report, setReport] = useState<EngineeringReport | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadTrigger, setReloadTrigger] = useState<number>(0);

  const [isShareModalOpen, setIsShareModalOpen] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);

  useEffect(() => {
    let isMounted = true;

    getInspectionReport(missionId)
      .then((data) => {
        if (!isMounted) return;
        setReport(data);
        setError(null);
        setLoading(false);
      })
      .catch((err: Error) => {
        if (!isMounted) return;
        console.error(`Failed to load inspection report for ${missionId}:`, err);
        setError(err.message || `Inspection report data unavailable for ${missionId}`);
        setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [missionId, reloadTrigger]);

  const handlePrint = () => {
    window.print();
  };

  const handleShareCopy = () => {
    const shareUrl = `${window.location.origin}/reports/${report?.missionId || missionId}`;
    navigator.clipboard.writeText(shareUrl).then(() => {
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2000);
    });
  };

  return (
    <div className="min-h-screen bg-[#0a1617] text-white p-4 sm:p-6 lg:p-8 font-['Inter'] selection:bg-[#CCFF80] selection:text-black">
      {/* Print-Only Custom CSS Styles */}
      <style>{`
        @media print {
          /* Hide all application navigation & interactive controls */
          header, nav, aside, .no-print, button, .action-toolbar {
            display: none !important;
          }
          body {
            background-color: #ffffff !important;
            color: #000000 !important;
            font-family: Arial, sans-serif !important;
          }
          .report-document {
            background-color: #ffffff !important;
            color: #000000 !important;
            border: 1px solid #cccccc !important;
            box-shadow: none !important;
            max-width: 100% !important;
            margin: 0 !important;
            padding: 20px !important;
          }
          .report-document * {
            color: #000000 !important;
            border-color: #dddddd !important;
          }
          .badge-print {
            border: 1px solid #000000 !important;
            background: #f0f0f0 !important;
            color: #000000 !important;
          }
        }
      `}</style>

      {/* Header Banner & Toolbar (No-Print) */}
      <div className="no-print flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-[#183536]">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/missions')}
            className="p-2 rounded-lg bg-[#0e2425] border border-[#1b3b3a] text-[#5de6ff] hover:bg-[#153837] transition-all cursor-pointer"
            title="Back to Missions"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-3">
              <FileText className="w-6 h-6 text-[#CCFF80]" />
              <h1 className="font-['Poppins'] text-2xl sm:text-3xl font-black uppercase tracking-wider text-white">
                Engineering Inspection Report
              </h1>
            </div>
            <p className="text-[#649c96] text-xs sm:text-sm mt-1 font-['Space_Mono']">
              Derived Condition Assessment • Real Observation Log • Document Export
            </p>
          </div>
        </div>

        {/* Action Toolbar */}
        <div className="action-toolbar flex flex-wrap items-center gap-3">
          <button
            onClick={() => setReloadTrigger((prev) => prev + 1)}
            className="px-3.5 py-2 rounded-lg bg-[#0e2425] hover:bg-[#153837] border border-[#1b3b3a] text-[#5de6ff] text-xs font-['Space_Mono'] font-bold flex items-center gap-2 transition-all cursor-pointer"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Refresh</span>
          </button>

          <button
            onClick={() => setIsShareModalOpen(true)}
            className="px-3.5 py-2 rounded-lg bg-[#0e2425] hover:bg-[#153837] border border-[#1b3b3a] text-[#CCFF80] text-xs font-['Space_Mono'] font-bold flex items-center gap-2 transition-all cursor-pointer"
          >
            <Share2 className="w-4 h-4" />
            <span>Share</span>
          </button>

          <button
            onClick={handlePrint}
            className="px-4 py-2 rounded-lg bg-[#CCFF80] hover:bg-[#b6f059] text-black font-['Poppins'] font-bold text-xs sm:text-sm uppercase tracking-wider flex items-center gap-2 transition-all shadow-[0_0_15px_rgba(163,230,53,0.3)] cursor-pointer"
          >
            <Printer className="w-4 h-4" />
            <span>Print / Save as PDF</span>
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      {loading ? (
        <div className="max-w-4xl mx-auto my-12 bg-[#0d1f20] border border-[#1b3b3a] rounded-xl p-12 text-center flex flex-col items-center justify-center gap-4">
          <RefreshCw className="w-8 h-8 text-[#CCFF80] animate-spin" />
          <h3 className="font-['Poppins'] text-lg font-bold text-white uppercase tracking-wider">
            Loading Inspection Report...
          </h3>
          <p className="text-xs font-['Space_Mono'] text-[#649c96]">
            Fetching mission snapshot, observation logs, robot state, and analytics.
          </p>
        </div>
      ) : error || !report ? (
        <div className="max-w-4xl mx-auto my-12 bg-[#1c0d0e] border border-[#5c1d24] rounded-xl p-8 text-center flex flex-col items-center justify-center gap-4 shadow-2xl">
          <AlertTriangle className="w-10 h-10 text-[#ff5449]" />
          <h3 className="font-['Poppins'] text-xl font-bold text-white uppercase tracking-wider">
            Report Data Unavailable
          </h3>
          <p className="text-xs font-['Space_Mono'] text-[#ffb4ab] max-w-md">
            {error || `Failed to fetch inspection report for mission '${missionId}'.`}
          </p>
          <div className="flex items-center gap-3 mt-2">
            <button
              onClick={() => navigate('/missions')}
              className="px-4 py-2 rounded-lg bg-[#0e2425] border border-[#1b3b3a] text-white font-['Space_Mono'] text-xs font-bold hover:bg-[#153837] cursor-pointer"
            >
              Back to Missions
            </button>
            <button
              onClick={() => setReloadTrigger((prev) => prev + 1)}
              className="px-4 py-2 rounded-lg bg-[#ff5449] text-white font-['Poppins'] font-bold text-xs uppercase hover:bg-[#ff6e64] flex items-center gap-2 cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Retry Connection</span>
            </button>
          </div>
        </div>
      ) : (
        /* Report Document Container */
        <div className="report-document max-w-4xl mx-auto my-8 bg-[#0d1f20] border border-[#1b3b3a] rounded-xl p-6 sm:p-10 shadow-2xl flex flex-col gap-8">
          {/* Interim Mission Warning Banner if Active */}
          {report.isInterim && (
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4 flex items-center gap-3 text-amber-300 font-['Space_Mono'] text-xs">
              <Clock className="w-5 h-5 text-amber-400 shrink-0" />
              <div>
                <strong className="block font-bold text-amber-200">INTERIM REPORT NOTICE</strong>
                <span>
                  This inspection survey is currently {report.status}. Report content reflects real-time interim data.
                </span>
              </div>
            </div>
          )}

          {/* Document Header */}
          <div className="flex flex-col sm:flex-row justify-between items-start border-b border-[#1b3b3a] pb-6 gap-4">
            <div>
              <div className="text-[#CCFF80] font-['Space_Mono'] text-xs uppercase tracking-widest font-bold mb-1 flex items-center gap-2">
                <span>PipeVision Engineering Audit</span>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    report.isInterim
                      ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                      : 'bg-[#CCFF80]/20 text-[#CCFF80] border border-[#CCFF80]/40'
                  }`}
                >
                  {report.reportTitle}
                </span>
              </div>
              <h2 className="font-['Poppins'] text-2xl font-black text-white uppercase tracking-wider">
                Pipe Condition Assessment Report
              </h2>
              <div className="text-[#649c96] font-['Space_Mono'] text-xs mt-1">
                Mission Ref ID: <strong className="text-white font-bold">{report.missionId}</strong>
              </div>
            </div>

            <div className="bg-[#071314] p-3 rounded-lg border border-[#173838] text-right font-['Space_Mono'] text-xs text-[#649c96]">
              <div>
                Survey Date: <strong className="text-white">{report.surveyDate}</strong>
              </div>
              <div>
                Status: <strong className="text-[#5de6ff] uppercase">{report.status}</strong>
              </div>
            </div>
          </div>

          {/* System Metadata Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 bg-[#071314] p-5 rounded-lg border border-[#173838] font-['Space_Mono'] text-xs text-[#649c96]">
            <div>
              <span className="block text-[#649c96] text-[11px]">Robot Crawler:</span>
              <strong className="text-white block mt-0.5 flex items-center gap-1.5">
                <Bot className="w-3.5 h-3.5 text-[#5de6ff]" />
                <span>
                  {report.robotId} {report.robot?.name ? `(${report.robot.name})` : ''}
                </span>
              </strong>
            </div>

            <div>
              <span className="block text-[#649c96] text-[11px]">Inspector Certification:</span>
              <strong className="text-[#9ed4ce] block mt-0.5">{report.inspectorName}</strong>
            </div>

            <div>
              <span className="block text-[#649c96] text-[11px]">Inspected Distance:</span>
              <strong className="text-[#CCFF80] block mt-0.5 text-sm font-bold">
                {report.inspectedDistanceM.toFixed(1)} m
              </strong>
            </div>

            <div>
              <span className="block text-[#649c96] text-[11px]">Client / Authority:</span>
              <strong className="text-[#9ed4ce] block mt-0.5">{report.clientName}</strong>
            </div>

            <div>
              <span className="block text-[#649c96] text-[11px]">Asset Identifier:</span>
              <strong className="text-[#9ed4ce] block mt-0.5">{report.assetCode}</strong>
            </div>

            <div>
              <span className="block text-[#649c96] text-[11px]">Pipe Segment:</span>
              <strong className="text-[#9ed4ce] block mt-0.5">{report.pipeSegment}</strong>
            </div>
          </div>

          {/* Derived Assessment Card */}
          <div className="bg-[#071314] p-5 rounded-lg border border-[#173838] flex flex-col gap-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#173838] pb-3">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-[#5de6ff]" />
                <h3 className="font-['Poppins'] text-sm font-bold text-white uppercase tracking-wider">
                  {report.derivedAssessment.label}
                </h3>
              </div>
              <div className="px-3 py-1 rounded bg-[#ff5449]/20 border border-[#ff5449]/40 text-[#ffb4ab] font-['Space_Mono'] text-xs font-bold">
                {report.derivedAssessment.overallGradeText}
              </div>
            </div>

            <p className="text-xs font-['Space_Mono'] text-[#649c96] leading-relaxed">
              {report.derivedAssessment.description}
            </p>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2 font-['Space_Mono'] text-xs">
              <div className="bg-[#0c2022] p-2.5 rounded border border-[#173838]">
                <span className="text-[#649c96] text-[10px] block">Structural Grade</span>
                <span className="text-white font-bold">
                  {report.derivedAssessment.structuralGrade !== null
                    ? `Grade ${report.derivedAssessment.structuralGrade} / 5`
                    : 'N/A'}
                </span>
              </div>
              <div className="bg-[#0c2022] p-2.5 rounded border border-[#173838]">
                <span className="text-[#649c96] text-[10px] block">O&M Defect Grade</span>
                <span className="text-white font-bold">
                  {report.derivedAssessment.omGrade !== null
                    ? `Grade ${report.derivedAssessment.omGrade} / 5`
                    : 'N/A'}
                </span>
              </div>
              <div className="bg-[#0c2022] p-2.5 rounded border border-[#173838]">
                <span className="text-[#649c96] text-[10px] block">Total Defects</span>
                <span className="text-[#5de6ff] font-bold">{report.totalObservationsCount}</span>
              </div>
              <div className="bg-[#0c2022] p-2.5 rounded border border-[#173838]">
                <span className="text-[#649c96] text-[10px] block">Assessment Source</span>
                <span className="text-[#CCFF80] font-bold">PipeVision Heuristic</span>
              </div>
            </div>
          </div>

          {/* Recorded Defect Log Summary Table */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <h3 className="font-['Poppins'] text-base font-bold text-white uppercase tracking-wider flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-[#ff5449]" />
                <span>Recorded Defect Log ({report.observations.length})</span>
              </h3>
              {report.observations.length > 0 && (
                <span className="text-xs font-['Space_Mono'] text-[#649c96]">
                  Source: Real Inspection Observations
                </span>
              )}
            </div>

            {report.observations.length === 0 ? (
              <div className="bg-[#071314] p-8 rounded-lg border border-[#173838] text-center font-['Space_Mono'] text-xs text-[#649c96] flex flex-col items-center gap-2">
                <CheckCircle2 className="w-6 h-6 text-[#CCFF80]" />
                <span>No defects or anomalies recorded during this inspection.</span>
              </div>
            ) : (
              <div className="overflow-x-auto border border-[#173838] rounded-lg">
                <table className="w-full text-left border-collapse text-xs font-['Space_Mono']">
                  <thead>
                    <tr className="bg-[#071314] text-[#5de6ff] border-b border-[#173838]">
                      <th className="p-3">Obs ID</th>
                      <th className="p-3">Frame #</th>
                      <th className="p-3">Chainage (m)</th>
                      <th className="p-3">Class Code</th>
                      <th className="p-3">Defect Label</th>
                      <th className="p-3">Clock Pos</th>
                      <th className="p-3">Confidence</th>
                      <th className="p-3">Severity</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#173838] text-white">
                    {report.observations.map((obs) => (
                      <tr key={obs.observation_id} className="hover:bg-[#0e2425]/50 transition-colors">
                        <td className="p-3 font-bold text-[#5de6ff]">{obs.observation_id}</td>
                        <td className="p-3 text-[#649c96]">#{obs.frame_index}</td>
                        <td className="p-3 font-bold text-[#CCFF80]">{obs.distance_m.toFixed(1)} m</td>
                        <td className="p-3 font-bold">{obs.class_code.toUpperCase()}</td>
                        <td className="p-3 text-white">{obs.class_name}</td>
                        <td className="p-3 text-[#9ed4ce]">{obs.clock_position}</td>
                        <td className="p-3">{(obs.confidence * 100).toFixed(1)}%</td>
                        <td className="p-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              obs.severity === 'CRITICAL'
                                ? 'bg-[#ff5449]/20 text-[#ff5449] border border-[#ff5449]/40'
                                : obs.severity === 'HIGH'
                                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                                : obs.severity === 'MEDIUM'
                                ? 'bg-[#5de6ff]/20 text-[#5de6ff] border border-[#5de6ff]/40'
                                : 'bg-[#649c96]/20 text-[#649c96] border border-[#649c96]/40'
                            }`}
                          >
                            {obs.severity}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Action Recommendations */}
          <div className="bg-[#071314] p-5 rounded-lg border border-[#173838] flex flex-col gap-4">
            <h4 className="font-['Poppins'] text-sm font-bold text-[#CCFF80] uppercase tracking-wider flex items-center gap-2">
              <Layers className="w-4 h-4 text-[#CCFF80]" />
              <span>Engineering Action Plan & Recommendations</span>
            </h4>

            <div className="flex flex-col gap-3">
              {report.recommendations.map((rec) => (
                <div key={rec.id} className="bg-[#0c2022] p-3.5 rounded border border-[#173838] flex flex-col gap-1.5">
                  <div className="flex items-center justify-between">
                    <strong className="text-white font-['Poppins'] text-xs font-bold uppercase tracking-wider">
                      {rec.title}
                    </strong>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-['Space_Mono'] font-bold ${
                        rec.priority === 'URGENT'
                          ? 'bg-[#ff5449]/20 text-[#ff5449] border border-[#ff5449]/40'
                          : rec.priority === 'HIGH'
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                          : rec.priority === 'MEDIUM'
                          ? 'bg-[#5de6ff]/20 text-[#5de6ff] border border-[#5de6ff]/40'
                          : 'bg-[#649c96]/20 text-[#649c96] border border-[#649c96]/40'
                      }`}
                    >
                      {rec.priority} PRIORITY
                    </span>
                  </div>
                  <p className="text-xs font-['Space_Mono'] text-[#9ed4ce] leading-relaxed">
                    {rec.action}
                  </p>
                  <span className="text-[10px] font-['Space_Mono'] text-[#649c96]">
                    Source: {rec.source}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Report Footer Disclaimer */}
          <div className="border-t border-[#1b3b3a] pt-4 flex flex-col sm:flex-row justify-between items-center text-[10px] font-['Space_Mono'] text-[#649c96] gap-2">
            <div>PipeVision Automated Inspection System • Version 0.2.0</div>
            <div>Generated from Mission {report.missionId}</div>
          </div>
        </div>
      )}

      {/* Share Modal (No-Print) */}
      {isShareModalOpen && report && (
        <div className="no-print fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0e2425] border border-[#1b3b3a] rounded-xl p-6 max-w-md w-full flex flex-col gap-4 shadow-2xl animate-fade-in">
            <div className="flex items-center justify-between">
              <h3 className="font-['Poppins'] text-base font-bold text-white uppercase tracking-wider flex items-center gap-2">
                <Share2 className="w-4 h-4 text-[#CCFF80]" />
                <span>Share Inspection Report</span>
              </h3>
              <button onClick={() => setIsShareModalOpen(false)} className="text-[#649c96] hover:text-white cursor-pointer">
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs font-['Space_Mono'] text-[#649c96]">
              Copy environment-aware link for report <strong>{report.missionId}</strong>:
            </p>

            <div className="flex items-center gap-2">
              <input
                type="text"
                readOnly
                value={`${window.location.origin}/reports/${report.missionId}`}
                className="flex-1 bg-[#071314] border border-[#173838] rounded p-2 text-xs font-['Space_Mono'] text-[#5de6ff]"
              />
              <button
                onClick={handleShareCopy}
                className="px-3 py-2 bg-[#CCFF80] text-black font-['Poppins'] font-bold text-xs rounded cursor-pointer hover:bg-[#b6f059] transition-all"
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