import { useState } from 'react';
import type { RobotDriveState } from '../types';

interface NetworkMappingViewProps {
  robotState?: RobotDriveState;
}

export const NetworkMappingView: React.FC<NetworkMappingViewProps> = () => {
  const [selectedNode, setSelectedNode] = useState<string | null>('MH-114');

  return (
    <div id="network-mapping-view" className="flex flex-col gap-6 w-full">
      {/* Top Card: Pipe Network Map */}
      <div className="bg-[#141619] rounded-xl p-5 sm:p-6 flex flex-col gap-4 border border-white/10 shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <div className="flex items-center gap-3">
            <h3 className="font-['Poppins'] text-lg font-bold text-white tracking-wide">
              Pipe Network Map (2D Topology)
            </h3>
            {selectedNode && (
              <span className="font-['Space_Mono'] text-xs text-[#a3e635] bg-[#a3e635]/10 px-2.5 py-1 rounded-md border border-[#a3e635]/30">
                Selected: {selectedNode}
              </span>
            )}
          </div>
          <span className="font-['Space_Mono'] text-[10px] sm:text-xs text-white/50 tracking-widest uppercase">
            SPATIAL / MAPPING LAYER
          </span>
        </div>

        {/* Interactive Map Visualizer */}
        <div className="relative w-full h-64 sm:h-80 bg-[#0d0f12] rounded-lg border border-white/5 overflow-hidden flex items-center justify-center p-4">
          {/* Subtle Grid Background */}
          <div
            className="absolute inset-0 opacity-15 pointer-events-none"
            style={{
              backgroundImage: 'radial-gradient(rgba(255,255,255,0.2) 1px, transparent 1px)',
              backgroundSize: '24px 24px'
            }}
          />

          <svg className="w-full h-full" viewBox="0 0 900 300" preserveAspectRatio="xMidYMid meet">
            <defs>
              <filter id="glow-green" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="4" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
              <filter id="glow-cyan" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>

            {/* Solid Pipe Lines (Surveyed) */}
            {/* MH-112 to MH-114 */}
            <line
              x1="160" y1="200"
              x2="340" y2="100"
              stroke="#5de6ff"
              strokeWidth="2.5"
              opacity="0.8"
            />
            {/* MH-114 to MH-116 */}
            <line
              x1="340" y1="100"
              x2="520" y2="220"
              stroke="#a3e635"
              strokeWidth="2.5"
              filter="url(#glow-green)"
            />
            {/* MH-116 to MH-118 */}
            <line
              x1="520" y1="220"
              x2="660" y2="120"
              stroke="#5de6ff"
              strokeWidth="2.5"
              opacity="0.8"
            />

            {/* Dashed Pipe Lines (Unsurveyed) */}
            {/* MH-118 to MH-120 */}
            <line
              x1="660" y1="120"
              x2="760" y2="220"
              stroke="#5de6ff"
              strokeWidth="2.5"
              strokeDasharray="6 6"
              opacity="0.7"
            />

            {/* Nodes & Defect Markers */}
            {/* Node MH-112 */}
            <g className="cursor-pointer" onClick={() => setSelectedNode('MH-112')}>
              <circle cx="160" cy="200" r="7" fill="#0d0f12" stroke="#5de6ff" strokeWidth="2.5" />
              <text x="160" y="230" textAnchor="middle" fill="#c2cab0" fontFamily="Space Mono" fontSize="11" fontWeight="bold">
                MH-112
              </text>
            </g>

            {/* Node MH-114 (Robot Position) */}
            <g className="cursor-pointer" onClick={() => setSelectedNode('MH-114')}>
              <circle cx="340" cy="100" r="14" fill="none" stroke="#a3e635" strokeWidth="1.5" opacity="0.5" className="animate-ping" />
              <circle cx="340" cy="100" r="9" fill="#0d0f12" stroke="#a3e635" strokeWidth="3" filter="url(#glow-green)" />
              <text x="340" y="70" textAnchor="middle" fill="#ccff80" fontFamily="Space Mono" fontSize="11" fontWeight="bold">
                MH-114
              </text>
            </g>

            {/* Defect on segment MH-114 -> MH-116 */}
            <g className="cursor-pointer">
              <circle cx="440" cy="165" r="4.5" fill="#ffb4ab" filter="url(#glow-cyan)" />
            </g>

            {/* Node MH-116 */}
            <g className="cursor-pointer" onClick={() => setSelectedNode('MH-116')}>
              <circle cx="520" cy="220" r="7" fill="#0d0f12" stroke="#5de6ff" strokeWidth="2.5" />
              <text x="520" y="250" textAnchor="middle" fill="#c2cab0" fontFamily="Space Mono" fontSize="11" fontWeight="bold">
                MH-116
              </text>
            </g>

            {/* Defect on segment MH-116 -> MH-118 */}
            <g className="cursor-pointer">
              <circle cx="630" cy="142" r="5" fill="#ff5449" />
            </g>

            {/* Node MH-118 */}
            <g className="cursor-pointer" onClick={() => setSelectedNode('MH-118')}>
              <circle cx="660" cy="120" r="7" fill="#0d0f12" stroke="#5de6ff" strokeWidth="2.5" />
              <text x="660" y="70" textAnchor="middle" fill="#c2cab0" fontFamily="Space Mono" fontSize="11" fontWeight="bold">
                MH-118
              </text>
            </g>

            {/* Node MH-120 */}
            <g className="cursor-pointer" onClick={() => setSelectedNode('MH-120')}>
              <circle cx="760" cy="220" r="7" fill="#0d0f12" stroke="#5de6ff" strokeWidth="2.5" strokeDasharray="3 3" />
              <text x="760" y="250" textAnchor="middle" fill="#c2cab0" fontFamily="Space Mono" fontSize="11" fontWeight="bold">
                MH-120
              </text>
            </g>
          </svg>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap items-center gap-4 sm:gap-8 pt-2 font-['Space_Mono'] text-xs text-white/70">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-sm bg-[#a3e635]" />
            <span>Robot position</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-sm bg-[#ffb4ab]" />
            <span>Defect – moderate</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-sm bg-[#ff5449]" />
            <span>Defect – severe</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-4 h-0.5 border-b-2 border-dashed border-[#5de6ff]" />
            <span>Unsurveyed segment</span>
          </div>
        </div>
      </div>

      {/* Bottom Row: AI Perception (Left) & Morphology - Bore Gauge (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Left Card: AI Perception */}
        <div className="bg-[#141619] rounded-xl p-5 sm:p-6 flex flex-col justify-between gap-5 border border-white/10 shadow-xl">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-white/10 pb-3">
            <h3 className="font-['Poppins'] text-lg font-bold text-white tracking-wide">
              AI Perception
            </h3>
            <span className="font-['Space_Mono'] text-[10px] sm:text-xs text-white/50 tracking-widest uppercase">
              FUSED DETECTIONS
            </span>
          </div>

          {/* Detections List */}
          <div className="flex flex-col gap-5 py-1">
            {/* Item 1: Surface Deposit */}
            <div className="flex flex-col gap-1.5">
              <div className="flex justify-between items-center font-['Space_Mono'] text-xs">
                <span className="text-white font-semibold">Surface Deposit</span>
                <span className="text-white/60">CH 42.6m</span>
              </div>
              <div className="w-full h-1.5 bg-black/50 rounded-full overflow-hidden">
                <div className="h-full bg-[#a3e635] rounded-full" style={{ width: '86%' }} />
              </div>
              <div className="flex justify-end">
                <span className="font-['Space_Mono'] text-xs text-[#5de6ff] font-bold">86%</span>
              </div>
            </div>

            {/* Item 2: Joint Offset */}
            <div className="flex flex-col gap-1.5">
              <div className="flex justify-between items-center font-['Space_Mono'] text-xs">
                <span className="text-white font-semibold">Joint Offset</span>
                <span className="text-white/60">CH 41.7m</span>
              </div>
              <div className="w-full h-1.5 bg-black/50 rounded-full overflow-hidden">
                <div className="h-full bg-[#ffb4ab]" style={{ width: '76%' }} />
              </div>
              <div className="flex justify-end">
                <span className="font-['Space_Mono'] text-xs text-[#ffb4ab] font-bold">76%</span>
              </div>
            </div>

            {/* Item 3: Longitudinal Crack */}
            <div className="flex flex-col gap-1.5">
              <div className="flex justify-between items-center font-['Space_Mono'] text-xs">
                <span className="text-white font-semibold">Longitudinal Crack</span>
                <span className="text-white/60">CH 38.2m</span>
              </div>
              <div className="w-full h-1.5 bg-black/50 rounded-full overflow-hidden">
                <div className="h-full bg-[#ff5449]" style={{ width: '98%' }} />
              </div>
              <div className="flex justify-end">
                <span className="font-['Space_Mono'] text-xs text-[#ff5449] font-bold">98%</span>
              </div>
            </div>
          </div>

          {/* Model Badges */}
          <div className="flex items-center gap-2 pt-2 border-t border-white/5">
            <span className="px-2.5 py-1 rounded bg-black/50 border border-white/10 font-['Space_Mono'] text-[10px] text-white/60">
              YOLO-Sewer v4
            </span>
            <span className="px-2.5 py-1 rounded bg-black/50 border border-white/10 font-['Space_Mono'] text-[10px] text-white/60">
              Sewer-ML C10
            </span>
          </div>
        </div>

        {/* Right Card: Morphology — Bore Gauge */}
        <div className="bg-[#141619] rounded-xl p-5 sm:p-6 flex flex-col justify-between gap-5 border border-white/10 shadow-xl">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-white/10 pb-3">
            <h3 className="font-['Poppins'] text-lg font-bold text-white tracking-wide">
              Morphology — Bore Gauge
            </h3>
            <span className="font-['Space_Mono'] text-[10px] sm:text-xs text-white/50 tracking-widest uppercase">
              DIAMETER / DEFORMATION
            </span>
          </div>

          {/* Numeric Readout & Gauge Area */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-6 py-2">

            {/* Radial Dial Gauge */}
            <div className="relative w-44 h-44 flex items-center justify-center flex-shrink-0 select-none">
              <svg className="w-full h-full transform -rotate-90" viewBox="0 0 160 160">
                {/* Background Ring */}
                <circle
                  cx="80"
                  cy="80"
                  r="62"
                  fill="none"
                  stroke="#1b1e22"
                  strokeWidth="12"
                />

                {/* Glowing Cyan Gauge Arc Segments */}
                <circle
                  cx="80"
                  cy="80"
                  r="62"
                  fill="none"
                  stroke="#5de6ff"
                  strokeWidth="8"
                  strokeDasharray="90 300"
                  strokeDashoffset="-20"
                  strokeLinecap="round"
                  style={{ filter: 'drop-shadow(0 0 6px rgba(93,230,255,0.7))' }}
                />

                <circle
                  cx="80"
                  cy="80"
                  r="62"
                  fill="none"
                  stroke="#a3e635"
                  strokeWidth="8"
                  strokeDasharray="40 300"
                  strokeDashoffset="-150"
                  strokeLinecap="round"
                  style={{ filter: 'drop-shadow(0 0 6px rgba(163,230,53,0.7))' }}
                />

                {/* Center Hub */}
                <circle cx="80" cy="80" r="8" fill="#141619" stroke="#5de6ff" strokeWidth="2" />
              </svg>

              {/* Indicator Needle */}
              <div
                className="absolute w-1 h-20 bg-gradient-to-t from-transparent to-[#ccff80] origin-bottom -translate-y-10 rounded-full pointer-events-none"
                style={{
                  transform: 'rotate(40deg)',
                  boxShadow: '0 0 8px #a3e635'
                }}
              />
              <div className="absolute w-3 h-3 rounded-full bg-[#ccff80] shadow-[0_0_10px_#ccff80]" />
            </div>

            {/* Readout Numbers & Specs */}
            <div className="flex flex-col gap-4 flex-1">
              {/* 299.3 mm nominal 300 */}
              <div>
                <div className="font-['Space_Mono'] text-3xl sm:text-4xl font-extrabold text-[#5de6ff] tracking-tight">
                  299.3
                </div>
                <div className="font-['Space_Mono'] text-xs text-white/50">
                  mm nominal 300
                </div>
              </div>

              {/* Stats Table */}
              <div className="flex flex-col gap-2 font-['Space_Mono'] text-xs">
                <div className="flex justify-between items-center text-white/70">
                  <span>Ovality</span>
                  <span className="font-bold text-white">2.5%</span>
                </div>
                <div className="flex justify-between items-center text-white/70">
                  <span>Deformation</span>
                  <span className="font-bold text-white">0.80%</span>
                </div>
                <div className="flex justify-between items-center text-white/70">
                  <span>Wall condition</span>
                  <span className="px-2 py-0.5 rounded bg-[#a3e635]/15 border border-[#a3e635]/50 text-[#ccff80] font-bold text-[10px]">
                    STABLE
                  </span>
                </div>
              </div>

              {/* Method badge */}
              <div className="flex items-center gap-2 pt-1">
                <span className="font-['Space_Mono'] text-[10px] text-white/40">Method</span>
                <span className="px-2 py-0.5 rounded bg-black/60 border border-white/10 font-['Space_Mono'] text-[10px] text-white/80">
                  Stereo fusion
                </span>
              </div>
            </div>

          </div>

        </div>

      </div>
    </div>
  );
};
