import { HelpCircle, Key, Cpu } from 'lucide-react';
import { sounds } from '../utils/audio';

interface HelpViewProps {
  onReturnToTelemetry: () => void;
}

export const HelpView: React.FC<HelpViewProps> = ({ onReturnToTelemetry }) => {
  return (
    <div className="flex-1 flex flex-col gap-6 animate-fade-in font-['Space_Mono']">
      <div className="glass-panel rounded-2xl p-6 flex items-center justify-between border border-white/10">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-white/10 border border-white/20 flex items-center justify-center text-white">
            <HelpCircle className="w-6 h-6" />
          </div>
          <div>
            <h2 className="font-['Poppins'] text-xl font-bold text-white">
              Operator Control Manual & Specifications
            </h2>
            <p className="text-xs text-white/50">
              ROV-01 Subterranean Telemetry System v4.2
            </p>
          </div>
        </div>

        <button
          onClick={() => {
            sounds.playClick('tactile');
            onReturnToTelemetry();
          }}
          className="px-4 py-2 rounded-xl bg-[#a3e635] text-[#121f00] text-xs font-bold"
        >
          Live Telemetry
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Keyboard Map */}
        <div className="glass-panel rounded-2xl p-6 border border-white/10 flex flex-col gap-4">
          <h3 className="font-['Poppins'] text-base font-bold text-white flex items-center gap-2">
            <Key className="w-5 h-5 text-[#a3e635]" />
            Direct Hotkey Bindings
          </h3>

          <div className="flex flex-col gap-2 text-xs">
            <div className="flex justify-between p-2.5 rounded-lg bg-black/30 border border-white/5">
              <span>Drive Thrusters:</span>
              <span className="text-[#a3e635] font-bold">W / A / S / D & Arrow Keys</span>
            </div>
            <div className="flex justify-between p-2.5 rounded-lg bg-black/30 border border-white/5">
              <span>Emergency STOP:</span>
              <span className="text-[#ffb4ab] font-bold">SPACEBAR</span>
            </div>
            <div className="flex justify-between p-2.5 rounded-lg bg-black/30 border border-white/5">
              <span>Toggle Headlights:</span>
              <span className="text-[#5de6ff] font-bold">L Key</span>
            </div>
            <div className="flex justify-between p-2.5 rounded-lg bg-black/30 border border-white/5">
              <span>Cycle Camera Feeds:</span>
              <span className="text-white font-bold">C Key</span>
            </div>
            <div className="flex justify-between p-2.5 rounded-lg bg-black/30 border border-white/5">
              <span>Toggle Recording:</span>
              <span className="text-[#ffb4ab] font-bold">R Key</span>
            </div>
            <div className="flex justify-between p-2.5 rounded-lg bg-black/30 border border-white/5">
              <span>High-Res Snapshot:</span>
              <span className="text-[#ccff80] font-bold">S Key</span>
            </div>
          </div>
        </div>

        {/* Technical Specs */}
        <div className="glass-panel rounded-2xl p-6 border border-white/10 flex flex-col gap-4">
          <h3 className="font-['Poppins'] text-base font-bold text-white flex items-center gap-2">
            <Cpu className="w-5 h-5 text-[#5de6ff]" />
            ROV-01 Hardware Specs
          </h3>

          <div className="flex flex-col gap-2 text-xs">
            <div className="flex justify-between p-2.5 rounded-lg bg-black/30 border border-white/5">
              <span>Conduit Range:</span>
              <span className="text-white">DN 150mm – 1200mm</span>
            </div>
            <div className="flex justify-between p-2.5 rounded-lg bg-black/30 border border-white/5">
              <span>Ingress Protection:</span>
              <span className="text-[#a3e635] font-bold">IP68 Submersible (10m)</span>
            </div>
            <div className="flex justify-between p-2.5 rounded-lg bg-black/30 border border-white/5">
              <span>IMU Sampling Rate:</span>
              <span className="text-[#5de6ff]">100Hz Internal / 20Hz Telemetry</span>
            </div>
            <div className="flex justify-between p-2.5 rounded-lg bg-black/30 border border-white/5">
              <span>Illumination:</span>
              <span className="text-white">2x 3000 Lumen CREE LED Array</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
