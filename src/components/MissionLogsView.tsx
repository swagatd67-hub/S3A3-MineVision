import React from 'react';
import { FileText, Clock, Radio, CheckCircle2, AlertCircle, ArrowLeft } from 'lucide-react';
import { sounds } from '../utils/audio';

interface MissionLogsViewProps {
  onReturnToTelemetry: () => void;
}

export const MissionLogsView: React.FC<MissionLogsViewProps> = ({ onReturnToTelemetry }) => {
  const logs = [
    { time: '14:26:12', type: 'TELEMETRY', msg: 'Depth sensor calibrated to -14.2m Subterranean datum.' },
    { time: '14:25:40', type: 'ANOMALY', msg: 'AI Defect Scanner flagged surface spalling at Clock 02:00.' },
    { time: '14:24:18', type: 'ROBOT', msg: 'Lights switched to HIGH BEAM 85% for deep dark conduit penetration.' },
    { time: '14:22:50', type: 'ROBOT', msg: 'Transmission set to CRUISE (1.0x). Throttle stabilized at 45%.' },
    { time: '14:21:05', type: 'SYSTEM', msg: 'MPU6050 6-Axis IMU synchronized. Zero-offset confirmed.' },
    { time: '14:20:00', type: 'SYSTEM', msg: 'PIPEVISION ROV-01 Tether link established (IP 192.168.1.104).' },
  ];

  return (
    <div className="flex-1 flex flex-col gap-6 animate-fade-in">
      <div className="glass-panel rounded-2xl p-6 flex items-center justify-between border border-white/10">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-[#5de6ff]/20 border border-[#5de6ff]/40 flex items-center justify-center text-[#5de6ff]">
            <FileText className="w-6 h-6" />
          </div>
          <div>
            <h2 className="font-['Poppins'] text-xl font-bold text-white">
              Mission Event & Telemetry Logs
            </h2>
            <p className="font-['Space_Mono'] text-xs text-white/50">
              Station ID: MH-204 &rarr; MH-205 Main Line Trunk
            </p>
          </div>
        </div>

        <button
          onClick={() => {
            sounds.playClick('tactile');
            onReturnToTelemetry();
          }}
          className="px-4 py-2 rounded-xl bg-[#a3e635] text-[#121f00] font-['Space_Mono'] text-xs font-bold"
        >
          Live Telemetry
        </button>
      </div>

      <div className="glass-panel rounded-2xl p-6 border border-white/10 flex flex-col gap-3 font-['Space_Mono'] text-xs">
        {logs.map((log, idx) => (
          <div key={idx} className="flex items-start gap-4 p-3 rounded-xl bg-black/30 border border-white/5 hover:border-white/20 transition-colors">
            <div className="flex items-center gap-1.5 text-white/40 text-[11px] pt-0.5">
              <Clock className="w-3.5 h-3.5" />
              <span>{log.time}</span>
            </div>
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
              log.type === 'ANOMALY' 
                ? 'bg-[#ff5449]/20 text-[#ffb4ab]' 
                : log.type === 'ROBOT'
                ? 'bg-[#a3e635]/20 text-[#ccff80]'
                : 'bg-[#5de6ff]/20 text-[#5de6ff]'
            }`}>
              {log.type}
            </span>
            <span className="text-white/80 flex-1">{log.msg}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
