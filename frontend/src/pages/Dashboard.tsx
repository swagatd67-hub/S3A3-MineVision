import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  Cpu,
  Eye,
  FileText,
  Gauge,
  Layers,
  MapPin,
  Play,
  ShieldAlert,
  Zap,
} from 'lucide-react';

interface NetworkNode {
  id: string;
  name: string;
  x: number;
  y: number;
  status: 'normal' | 'warning' | 'critical';
  defectCount: number;
}

const NODES: NetworkNode[] = [
  { id: 'N1', name: 'MH-112', x: 15, y: 35, status: 'normal', defectCount: 1 },
  { id: 'N2', name: 'MH-114', x: 40, y: 65, status: 'warning', defectCount: 3 },
  { id: 'N3', name: 'MH-116', x: 70, y: 40, status: 'critical', defectCount: 5 },
  { id: 'N4', name: 'MH-118', x: 90, y: 75, status: 'normal', defectCount: 0 },
];

const RECENT_ALERTS = [
  {
    id: 'ALT-101',
    severity: 'critical',
    title: 'Major Longitudinal Crack',
    location: 'MH-114 → MH-116 (Chainage 38.4m)',
    time: '2 mins ago',
    confidence: '96.2%',
  },
  {
    id: 'ALT-102',
    severity: 'warning',
    title: 'Joint Displacement & Silt Accumulation',
    location: 'MH-112 → MH-114 (Chainage 14.8m)',
    time: '14 mins ago',
    confidence: '89.4%',
  },
  {
    id: 'ALT-103',
    severity: 'normal',
    title: 'Routine Jetting Verification Completed',
    location: 'Sector 4B Pipe 12',
    time: '45 mins ago',
    confidence: '99.0%',
  },
];

export default function Dashboard() {
  const navigate = useNavigate();
  const [timeframe, setTimeframe] = useState<'7D' | '30D' | 'YTD'>('7D');
  const [selectedNode, setSelectedNode] = useState<NetworkNode | null>(NODES[1]);

  return (
    <div className="min-h-screen bg-[#0a1617] text-white p-4 sm:p-6 lg:p-8 font-['Inter'] selection:bg-[#a3e635] selection:text-black">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-[#183536]">
        <div>
          <div className="flex items-center gap-3">
            <span className="w-3 h-3 rounded-full bg-[#a3e635] animate-pulse shadow-[0_0_10px_#a3e635]" />
            <h1 className="font-['Poppins'] text-2xl sm:text-3xl font-black uppercase tracking-wider text-white">
              PipeVision Executive Dashboard
            </h1>
          </div>
          <p className="text-[#649c96] text-xs sm:text-sm mt-1 font-['Space_Mono']">
            Autonomous Sewer Crawler Fleet • Spatial Reconstruction & Perception Engine
          </p>
        </div>

        {/* Timeframe selector & Quick Launch */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="bg-[#0e2425] p-1 rounded-lg border border-[#1b3b3a] flex items-center gap-1">
            {(['7D', '30D', 'YTD'] as const).map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={`px-3 py-1.5 rounded text-xs font-['Space_Mono'] font-bold transition-all ${
                  timeframe === tf
                    ? 'bg-[#5de6ff] text-[#001f25] shadow-[0_0_10px_#5de6ff]'
                    : 'text-[#649c96] hover:text-white'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>

          <button
            onClick={() => navigate('/missions/M-104/live')}
            className="px-4 py-2 rounded-lg bg-[#a3e635] hover:bg-[#b6f059] text-black font-['Poppins'] font-bold text-xs sm:text-sm uppercase tracking-wider flex items-center gap-2 transition-all shadow-[0_0_15px_rgba(163,230,53,0.3)] cursor-pointer"
          >
            <Play className="w-4 h-4 fill-black" />
            <span>Launch Live Cockpit</span>
          </button>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 my-6">
        <div className="bg-[#0e2425]/90 border border-[#1b3b3a] p-5 rounded-xl shadow-lg hover:border-[#2a5754] transition-all">
          <div className="flex items-center justify-between text-[#649c96] mb-2">
            <span className="text-xs font-['Space_Mono'] uppercase tracking-wider">Active Survey Network</span>
            <Activity className="w-4 h-4 text-[#5de6ff]" />
          </div>
          <div className="font-['Space_Mono'] text-2xl font-black text-white">14.8 km</div>
          <div className="text-[11px] text-[#a3e635] mt-1 flex items-center gap-1">
            <ArrowUpRight className="w-3.0 h-3.0" />
            <span>+2.4 km surveyed this week</span>
          </div>
        </div>

        <div className="bg-[#0e2425]/90 border border-[#1b3b3a] p-5 rounded-xl shadow-lg hover:border-[#2a5754] transition-all">
          <div className="flex items-center justify-between text-[#649c96] mb-2">
            <span className="text-xs font-['Space_Mono'] uppercase tracking-wider">Network Integrity Score</span>
            <Gauge className="w-4 h-4 text-[#a3e635]" />
          </div>
          <div className="font-['Space_Mono'] text-2xl font-black text-white">92.4%</div>
          <div className="text-[11px] text-[#649c96] mt-1">Grade 2 • Acceptable Hydraulic Capacity</div>
        </div>

        <div className="bg-[#0e2425]/90 border border-[#1b3b3a] p-5 rounded-xl shadow-lg hover:border-[#2a5754] transition-all">
          <div className="flex items-center justify-between text-[#649c96] mb-2">
            <span className="text-xs font-['Space_Mono'] uppercase tracking-wider">Unresolved Anomalies</span>
            <AlertTriangle className="w-4 h-4 text-[#ff5449]" />
          </div>
          <div className="font-['Space_Mono'] text-2xl font-black text-[#ff5449]">9 Defects</div>
          <div className="text-[11px] text-[#ff8c82] mt-1">2 Critical • Require Immediate Jetting</div>
        </div>

        <div className="bg-[#0e2425]/90 border border-[#1b3b3a] p-5 rounded-xl shadow-lg hover:border-[#2a5754] transition-all">
          <div className="flex items-center justify-between text-[#649c96] mb-2">
            <span className="text-xs font-['Space_Mono'] uppercase tracking-wider">Crawler Fleet Status</span>
            <Cpu className="w-4 h-4 text-[#5de6ff]" />
          </div>
          <div className="font-['Space_Mono'] text-2xl font-black text-[#5de6ff]">3 / 3 Ready</div>
          <div className="text-[11px] text-[#a3e635] mt-1 flex items-center gap-1">
            <CheckCircle2 className="w-3.0 h-3.0" />
            <span>ROV-01 Currently Active</span>
          </div>
        </div>
      </div>

      {/* Main Content Split Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Spatial Network Viewer & Quick Nav (2 Cols) */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          {/* Interactive Spatial Pipe Network Map */}
          <div className="bg-[#0e2425]/80 border border-[#1b3b3a] rounded-xl p-5 shadow-xl flex flex-col gap-4 relative overflow-hidden">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-['Poppins'] text-base font-bold text-white uppercase tracking-wider flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-[#5de6ff]" />
                  <span>Subsurface Pipe Network Graph</span>
                </h3>
                <p className="text-[#649c96] text-xs font-['Space_Mono']">
                  Interactive node map • Sector 4B Sewer Trunk Line
                </p>
              </div>

              <div className="flex items-center gap-2 text-xs font-['Space_Mono']">
                <span className="px-2.5 py-1 rounded bg-[#a3e635]/10 text-[#a3e635] border border-[#a3e635]/30">
                  Live Sync
                </span>
              </div>
            </div>

            {/* Visual SVG Pipe Graph Canvas */}
            <div className="w-full h-[320px] bg-[#071314] rounded-lg border border-[#173838] relative overflow-hidden flex items-center justify-center p-4">
              <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
                {/* Grid lines */}
                <defs>
                  <pattern id="grid" width="10" height="10" patternUnits="userSpaceOnUse">
                    <path d="M 10 0 L 0 0 0 10" fill="none" stroke="#102d2e" strokeWidth="0.5" />
                  </pattern>
                </defs>
                <rect width="100%" height="100%" fill="url(#grid)" />

                {/* Pipe Connections */}
                <line x1="15" y1="35" x2="40" y2="65" stroke="#1c4848" strokeWidth="2.5" strokeDasharray="2 1" />
                <line x1="40" y1="65" x2="70" y2="40" stroke="#ff5449" strokeWidth="3" />
                <line x1="70" y1="40" x2="90" y2="75" stroke="#1c4848" strokeWidth="2.5" />

                {/* Animated crawler position */}
                <circle cx="55" cy="52.5" r="3" fill="#a3e635">
                  <animate attributeName="r" values="3;5;3" dur="2s" repeatCount="indefinite" />
                </circle>

                {/* Manhole Nodes */}
                {NODES.map((node) => {
                  const isSelected = selectedNode?.id === node.id;
                  const color =
                    node.status === 'critical'
                      ? '#ff5449'
                      : node.status === 'warning'
                      ? '#ffb4ab'
                      : '#5de6ff';

                  return (
                    <g key={node.id} onClick={() => setSelectedNode(node)} className="cursor-pointer">
                      <circle
                        cx={node.x}
                        cy={node.y}
                        r={isSelected ? '6' : '4.5'}
                        fill="#0a1617"
                        stroke={color}
                        strokeWidth="2"
                      />
                      <text
                        x={node.x}
                        y={node.y - 7}
                        fill="#9ed4ce"
                        fontSize="3.5"
                        fontFamily="Space Mono"
                        textAnchor="middle"
                      >
                        {node.name}
                      </text>
                    </g>
                  );
                })}
              </svg>

              {/* Crawler Floating Badge */}
              <div className="absolute top-4 left-4 bg-[#0a1617]/90 backdrop-blur-md border border-[#1e4848] p-3 rounded-lg text-xs font-['Space_Mono'] flex flex-col gap-1">
                <span className="text-[#a3e635] font-bold flex items-center gap-1.5">
                  <Zap className="w-3.5 h-3.5" /> ROV-01 Crawling
                </span>
                <span className="text-[#649c96]">Pipe Segment: MH-114 → MH-116</span>
                <span className="text-white">Chainage: 38.4m / 61.0m</span>
              </div>

              {/* Selected Node Details Card */}
              {selectedNode && (
                <div className="absolute bottom-4 right-4 bg-[#0a1617]/95 backdrop-blur-md border border-[#1e4848] p-3.5 rounded-lg text-xs font-['Space_Mono'] max-w-[220px]">
                  <div className="flex items-center justify-between text-[#5de6ff] font-bold mb-1">
                    <span>{selectedNode.name}</span>
                    <span className="uppercase text-[10px] px-1.5 py-0.5 rounded bg-white/10">
                      {selectedNode.status}
                    </span>
                  </div>
                  <div className="text-[#649c96] text-[11px]">
                    Defects Logged: <strong className="text-white">{selectedNode.defectCount}</strong>
                  </div>
                  <button
                    onClick={() => navigate('/analytics')}
                    className="mt-2.5 w-full py-1 bg-[#153837] hover:bg-[#1f504e] text-[#5de6ff] rounded text-[11px] transition-all cursor-pointer"
                  >
                    View Analytics
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Quick Action Navigation Deck */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <button
              onClick={() => navigate('/analytics')}
              className="bg-[#0e2425]/90 border border-[#1b3b3a] hover:border-[#5de6ff] p-4 rounded-xl flex flex-col gap-2 text-left transition-all group cursor-pointer"
            >
              <div className="flex items-center justify-between">
                <Layers className="w-5 h-5 text-[#5de6ff] group-hover:scale-110 transition-transform" />
                <ArrowUpRight className="w-4 h-4 text-[#649c96] group-hover:text-[#5de6ff]" />
              </div>
              <div className="font-['Poppins'] font-bold text-sm text-white">Spatial Analytics</div>
              <div className="text-[#649c96] text-xs">Reconstruction & Jetting Cycle analytics</div>
            </button>

            <button
              onClick={() => navigate('/findings')}
              className="bg-[#0e2425]/90 border border-[#1b3b3a] hover:border-[#ff5449] p-4 rounded-xl flex flex-col gap-2 text-left transition-all group cursor-pointer"
            >
              <div className="flex items-center justify-between">
                <ShieldAlert className="w-5 h-5 text-[#ff5449] group-hover:scale-110 transition-transform" />
                <ArrowUpRight className="w-4 h-4 text-[#649c96] group-hover:text-[#ff5449]" />
              </div>
              <div className="font-['Poppins'] font-bold text-sm text-white">Defect Findings</div>
              <div className="text-[#649c96] text-xs">Review AI defect detections & note logs</div>
            </button>

            <button
              onClick={() => navigate('/reports')}
              className="bg-[#0e2425]/90 border border-[#1b3b3a] hover:border-[#a3e635] p-4 rounded-xl flex flex-col gap-2 text-left transition-all group cursor-pointer"
            >
              <div className="flex items-center justify-between">
                <FileText className="w-5 h-5 text-[#a3e635] group-hover:scale-110 transition-transform" />
                <ArrowUpRight className="w-4 h-4 text-[#649c96] group-hover:text-[#a3e635]" />
              </div>
              <div className="font-['Poppins'] font-bold text-sm text-white">Inspection Reports</div>
              <div className="text-[#649c96] text-xs">Generate & export engineering reports</div>
            </button>
          </div>
        </div>

        {/* Right Column: Perception & Alert Feed (1 Col) */}
        <div className="flex flex-col gap-6">
          {/* Live Anomaly Alert Feed */}
          <div className="bg-[#0e2425]/80 border border-[#1b3b3a] rounded-xl p-5 shadow-xl flex flex-col gap-4 flex-1">
            <div className="flex items-center justify-between pb-3 border-b border-[#183536]">
              <h3 className="font-['Poppins'] text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-[#ff5449]" />
                <span>Perception AI Alert Feed</span>
              </h3>
              <span className="text-[11px] font-['Space_Mono'] text-[#a3e635]">Live</span>
            </div>

            <div className="flex flex-col gap-3">
              {RECENT_ALERTS.map((alert) => (
                <div
                  key={alert.id}
                  className="bg-[#071314] border border-[#173838] p-3.5 rounded-lg flex flex-col gap-1.5 hover:border-[#275c5a] transition-all"
                >
                  <div className="flex items-center justify-between">
                    <span
                      className={`text-[10px] font-['Space_Mono'] px-2 py-0.5 rounded font-bold uppercase ${
                        alert.severity === 'critical'
                          ? 'bg-[#ff5449]/20 text-[#ff8c82] border border-[#ff5449]/40'
                          : alert.severity === 'warning'
                          ? 'bg-[#ffb4ab]/20 text-[#ffc0b8] border border-[#ffb4ab]/40'
                          : 'bg-[#5de6ff]/20 text-[#5de6ff] border border-[#5de6ff]/40'
                      }`}
                    >
                      {alert.severity}
                    </span>
                    <span className="text-[11px] text-[#528782] font-['Space_Mono']">{alert.time}</span>
                  </div>

                  <div className="font-['Poppins'] font-bold text-xs text-white">{alert.title}</div>

                  <div className="text-[11px] text-[#649c96] font-['Space_Mono'] flex items-center justify-between">
                    <span>{alert.location}</span>
                    <span className="text-[#a3e635]">{alert.confidence}</span>
                  </div>
                </div>
              ))}
            </div>

            <button
              onClick={() => navigate('/findings')}
              className="mt-auto w-full py-2.5 bg-[#0e2c2c] hover:bg-[#143e3d] border border-[#1b4442] text-[#5de6ff] rounded-lg text-xs font-['Space_Mono'] font-bold transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              <Eye className="w-3.5 h-3.5" />
              <span>Explore All 24 Detections</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}