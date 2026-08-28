import React from 'react';
import { ShieldAlert, AlertTriangle, CheckCircle, FileSpreadsheet, Download, Sparkles, Eye } from 'lucide-react';
import { DefectDetection } from '../types';
import { sounds } from '../utils/audio';

interface DefectAnalyzerViewProps {
  defects: DefectDetection[];
  onReturnToTelemetry: () => void;
}

export const DefectAnalyzerView: React.FC<DefectAnalyzerViewProps> = ({
  defects,
  onReturnToTelemetry,
}) => {
  return (
    <div className="flex-1 flex flex-col gap-6 animate-fade-in">
      {/* Header Bar */}
      <div className="glass-panel rounded-2xl p-6 flex flex-wrap items-center justify-between gap-4 border border-white/10">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-[#ff5449]/20 border border-[#ff5449]/40 flex items-center justify-center text-[#ffb4ab]">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <h2 className="font-['Poppins'] text-xl font-bold text-white flex items-center gap-2">
              AI Pipe Defect Analyzer
              <span className="px-2 py-0.5 rounded text-[10px] font-['Space_Mono'] bg-[#a3e635]/20 text-[#ccff80] border border-[#a3e635]/40">
                NASSCO PACP V7.0
              </span>
            </h2>
            <p className="font-['Space_Mono'] text-xs text-white/50">
              Automated computer vision structural assessment & anomaly classification
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              sounds.playClick('tactile');
              alert('Exporting PACP Inspection Summary Report (CSV)...');
            }}
            className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-white border border-white/15 font-['Space_Mono'] text-xs flex items-center gap-2 transition-colors"
          >
            <Download className="w-4 h-4 text-[#5de6ff]" />
            <span>Export Report (CSV)</span>
          </button>

          <button
            onClick={() => {
              sounds.playClick('tactile');
              onReturnToTelemetry();
            }}
            className="px-4 py-2 rounded-xl bg-[#a3e635] hover:bg-[#b2f746] text-[#121f00] font-['Space_Mono'] text-xs font-bold transition-all shadow-[0_0_15px_rgba(163,230,53,0.4)]"
          >
            Live Camera Feed
          </button>
        </div>
      </div>

      {/* Overview Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 font-['Space_Mono']">
        <div className="glass-panel rounded-xl p-4 border border-white/10 flex flex-col gap-1">
          <span className="text-xs text-white/50 font-bold">STRUCTURAL RATING</span>
          <div className="text-2xl font-bold text-[#ccff80] flex items-baseline gap-1">
            Grade 2 <span className="text-xs font-normal text-white/50">(Minor)</span>
          </div>
          <div className="text-[10px] text-[#a3e635]">92.4% Structural Integrity</div>
        </div>

        <div className="glass-panel rounded-xl p-4 border border-white/10 flex flex-col gap-1">
          <span className="text-xs text-white/50 font-bold">DETECTED DEFECTS</span>
          <div className="text-2xl font-bold text-[#ffb4ab] flex items-baseline gap-1">
            {defects.length} <span className="text-xs font-normal text-white/50">points</span>
          </div>
          <div className="text-[10px] text-white/50">2 Monitored, 1 Actionable</div>
        </div>

        <div className="glass-panel rounded-xl p-4 border border-white/10 flex flex-col gap-1">
          <span className="text-xs text-white/50 font-bold">CONDUIT MATERIAL</span>
          <div className="text-xl font-bold text-[#5de6ff]">
            Reinforced Conc.
          </div>
          <div className="text-[10px] text-white/50">Diameter: DN 800mm (32")</div>
        </div>

        <div className="glass-panel rounded-xl p-4 border border-white/10 flex flex-col gap-1">
          <span className="text-xs text-white/50 font-bold">INSPECTION PROGRESS</span>
          <div className="text-2xl font-bold text-white">
            42.8m <span className="text-xs font-normal text-white/50">/ 120m</span>
          </div>
          <div className="text-[10px] text-[#5de6ff]">Speed: 0.4 m/s (Optimal)</div>
        </div>
      </div>

      {/* Defects Detailed Table */}
      <div className="glass-panel rounded-2xl p-6 border border-white/10 flex flex-col gap-4">
        <h3 className="font-['Poppins'] text-base font-bold text-white flex items-center gap-2">
          <span>Identified Anomaly Log</span>
          <span className="w-2 h-2 rounded-full bg-[#ff5449] animate-ping" />
        </h3>

        <div className="overflow-x-auto">
          <table className="w-full text-left font-['Space_Mono'] text-xs">
            <thead>
              <tr className="border-b border-white/10 text-white/50">
                <th className="pb-3 font-bold">DEFECT TYPE</th>
                <th className="pb-3 font-bold">SEVERITY</th>
                <th className="pb-3 font-bold">CHAINAGE / POS</th>
                <th className="pb-3 font-bold">AI CONFIDENCE</th>
                <th className="pb-3 font-bold">PACP CODE</th>
                <th className="pb-3 font-bold">ACTION RECOMMENDED</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {defects.map((d) => (
                <tr key={d.id} className="hover:bg-white/5 transition-colors">
                  <td className="py-3.5 text-white font-bold flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-[#ff5449]" />
                    {d.type}
                  </td>
                  <td className="py-3.5">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      d.severity === 'HIGH' 
                        ? 'bg-[#ff5449]/20 text-[#ffb4ab] border border-[#ff5449]/40' 
                        : 'bg-[#fbbf24]/20 text-[#fbbf24] border border-[#fbbf24]/40'
                    }`}>
                      {d.severity}
                    </span>
                  </td>
                  <td className="py-3.5 text-white/80">38.4m (Clock 11:00)</td>
                  <td className="py-3.5 text-[#a3e635] font-bold">{(d.confidence * 100).toFixed(1)}%</td>
                  <td className="py-3.5 text-[#5de6ff]">MWL-04</td>
                  <td className="py-3.5 text-white/70">{d.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
