import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowLeft,
  Box,
  FileText,
  Play,
  RotateCcw,
  ShieldAlert,
  ZoomIn,
  ZoomOut,
  RefreshCw,
  AlertOctagon,
} from 'lucide-react';
import { mockFindings } from '../mocks/findings';
import { getMission } from '../api/missions';
import type { Mission } from '../types/mission';

export default function MissionDetail() {
  const { missionId = 'M-104' } = useParams<{ missionId: string }>();
  const navigate = useNavigate();

  const [mission, setMission] = useState<Mission | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // 3D Digital Twin Viewer controls
  const [zoomLevel, setZoomLevel] = useState(1);
  const [isWireframe, setIsWireframe] = useState(false);
  const [isAutoRotate, setIsAutoRotate] = useState(true);
  const [selectedDefect, setSelectedDefect] = useState<typeof mockFindings[0] | null>(mockFindings[0]);

  useEffect(() => {
    let isMounted = true;

    getMission(missionId)
      .then((data) => {
        if (isMounted) {
          setMission(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          console.error(`Failed to fetch mission ${missionId}:`, err);
          setError(`Mission '${missionId}' could not be fetched from PipeVision API server.`);
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [missionId]);

  return (
    <div className="min-h-screen bg-[#0a1617] text-white p-4 sm:p-6 lg:p-8 font-['Inter'] selection:bg-[#a3e635] selection:text-black">
      {/* Header Navigation */}
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
              <span className="font-['Space_Mono'] font-bold text-sm text-[#5de6ff] uppercase tracking-wider">
                {missionId}
              </span>
              {loading ? (
                <span className="px-2.5 py-0.5 rounded bg-[#5de6ff]/20 text-[#5de6ff] border border-[#5de6ff]/40 text-[10px] font-['Space_Mono'] font-bold uppercase animate-pulse">
                  Loading...
                </span>
              ) : mission ? (
                <span
                  className={`px-2.5 py-0.5 rounded text-[10px] font-['Space_Mono'] font-bold uppercase ${
                    mission.status === 'active'
                      ? 'bg-[#a3e635]/20 text-[#a3e635] border border-[#a3e635]/40 animate-pulse'
                      : mission.status === 'completed'
                      ? 'bg-[#5de6ff]/20 text-[#5de6ff] border border-[#5de6ff]/40'
                      : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                  }`}
                >
                  {mission.status}
                </span>
              ) : (
                <span className="px-2.5 py-0.5 rounded bg-red-500/20 text-red-300 border border-red-500/40 text-[10px] font-['Space_Mono'] font-bold uppercase">
                  Unavailable
                </span>
              )}
            </div>
            <h1 className="font-['Poppins'] text-xl sm:text-2xl font-black uppercase tracking-wider text-white mt-1">
              Digital Twin & Pipe Reconstruction
            </h1>
            {mission && (
              <p className="text-xs font-['Space_Mono'] text-[#649c96] mt-0.5">
                {mission.location} • Assigned Robot: {mission.robot_id || 'ROV-01'}
              </p>
            )}
          </div>
        </div>

        {/* Quick Launch Buttons */}
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={() => navigate(`/missions/${missionId}/live`)}
            className="px-4 py-2 rounded-lg bg-[#a3e635] hover:bg-[#b6f059] text-black font-['Poppins'] font-bold text-xs sm:text-sm uppercase tracking-wider flex items-center gap-2 transition-all shadow-[0_0_15px_rgba(163,230,53,0.3)] cursor-pointer"
          >
            <Play className="w-4 h-4 fill-black" />
            <span>Launch Live Cockpit</span>
          </button>

          <button
            onClick={() => navigate(`/reports/${missionId}`)}
            className="px-4 py-2 rounded-lg bg-[#0e2425] hover:bg-[#153837] border border-[#1b3b3a] text-[#5de6ff] font-['Space_Mono'] font-bold text-xs flex items-center gap-2 transition-all cursor-pointer"
          >
            <FileText className="w-4 h-4" />
            <span>Export Report</span>
          </button>
        </div>
      </div>

      {error ? (
        <div className="my-6 bg-[#1f0f11] border border-[#ff5449]/40 rounded-xl p-8 flex flex-col items-center justify-center gap-4 text-center">
          <AlertOctagon className="w-10 h-10 text-[#ff5449]" />
          <div>
            <div className="font-['Poppins'] font-bold text-white text-base">
              Mission Data Fetch Error
            </div>
            <div className="font-['Space_Mono'] text-xs text-[#ff8c82] mt-1 max-w-md">
              {error}
            </div>
          </div>
          <button
            onClick={() => {
              setLoading(true);
              setError(null);
              getMission(missionId)
                .then((data) => {
                  setMission(data);
                  setLoading(false);
                })
                .catch((err) => {
                  console.error(err);
                  setError(`Mission '${missionId}' could not be fetched.`);
                  setLoading(false);
                });
            }}
            className="px-4 py-2 rounded-lg bg-[#ff5449]/20 hover:bg-[#ff5449]/30 border border-[#ff5449]/40 text-white font-['Space_Mono'] text-xs font-bold flex items-center gap-2 transition-all cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Retry Connection</span>
          </button>
        </div>
      ) : (
        /* Main Grid: 3D Twin Canvas View (Left) & Inspector (Right) */
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 my-6">
          {/* 3D Pipe Reconstruction Viewer */}
          <div className="lg:col-span-2 bg-[#0e2425]/90 border border-[#1b3b3a] rounded-xl p-5 shadow-2xl flex flex-col gap-4 relative overflow-hidden">
            <div className="flex items-center justify-between z-10">
              <div className="flex items-center gap-2">
                <Box className="w-5 h-5 text-[#5de6ff]" />
                <h3 className="font-['Poppins'] text-sm font-bold text-white uppercase tracking-wider">
                  3D Sewer Cylinder Reconstruction
                </h3>
              </div>

              <div className="flex items-center gap-2 bg-[#071314] p-1 rounded-lg border border-[#173838]">
                <button
                  onClick={() => setIsWireframe(!isWireframe)}
                  className={`px-2.5 py-1 rounded text-[11px] font-['Space_Mono'] transition-all ${
                    isWireframe ? 'bg-[#5de6ff] text-[#001f25] font-bold' : 'text-[#649c96] hover:text-white'
                  }`}
                >
                  Wireframe
                </button>
                <button
                  onClick={() => setIsAutoRotate(!isAutoRotate)}
                  className={`px-2.5 py-1 rounded text-[11px] font-['Space_Mono'] transition-all ${
                    isAutoRotate ? 'bg-[#a3e635] text-black font-bold' : 'text-[#649c96] hover:text-white'
                  }`}
                >
                  Auto-Rotate
                </button>
              </div>
            </div>

            {/* Interactive SVG / WebGL Simulation Container */}
            <div className="w-full h-[380px] bg-[#050e0f] rounded-lg border border-[#173838] relative overflow-hidden flex items-center justify-center p-6">
              <svg
                className="w-full h-full"
                viewBox="0 0 600 300"
                style={{ transform: `scale(${zoomLevel})`, transition: 'transform 0.3s ease' }}
              >
                <defs>
                  <linearGradient id="pipeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#0c2324" />
                    <stop offset="50%" stopColor="#19484a" />
                    <stop offset="100%" stopColor="#0c2324" />
                  </linearGradient>
                </defs>

                {/* Outer Pipe Cylinder */}
                <rect
                  x="50"
                  y="80"
                  width="500"
                  height="140"
                  rx="15"
                  fill="url(#pipeGrad)"
                  stroke={isWireframe ? '#5de6ff' : '#1e4b4d'}
                  strokeWidth={isWireframe ? '1' : '3'}
                  strokeDasharray={isWireframe ? '4 2' : 'none'}
                />

                {/* Internal Pipe Rings / Mesh */}
                {[100, 180, 260, 340, 420, 500].map((xPos) => (
                  <ellipse
                    key={xPos}
                    cx={xPos}
                    cy="150"
                    rx="15"
                    ry="70"
                    fill="none"
                    stroke={isWireframe ? '#5de6ff' : '#173838'}
                    strokeWidth="1.5"
                    strokeDasharray="2 2"
                  />
                ))}

                {/* Central Axis Chainage Line */}
                <line x1="50" y1="150" x2="550" y2="150" stroke="#a3e635" strokeWidth="1" strokeDasharray="5 3" />

                {/* Defect Markers along 3D Pipe */}
                {mockFindings.map((finding, idx) => {
                  const xPos = 100 + idx * 140;
                  const yPos = 120 + (idx % 2 === 0 ? -25 : 30);
                  const isSelected = selectedDefect?.frame_index === finding.frame_index;

                  return (
                    <g
                      key={finding.frame_index}
                      onClick={() => setSelectedDefect(finding)}
                      className="cursor-pointer group"
                    >
                      <circle
                        cx={xPos}
                        cy={yPos}
                        r={isSelected ? '9' : '6'}
                        fill={finding.severity === 'critical' ? '#ff5449' : '#ffb4ab'}
                        className="transition-all"
                      >
                        {isSelected && (
                          <animate attributeName="r" values="9;12;9" dur="1.5s" repeatCount="indefinite" />
                        )}
                      </circle>

                      <text
                        x={xPos}
                        y={yPos - 12}
                        fill="#ffffff"
                        fontSize="10"
                        fontFamily="Space Mono"
                        textAnchor="middle"
                        className="font-bold"
                      >
                        {finding.defect} ({finding.distance_m}m)
                      </text>
                    </g>
                  );
                })}
              </svg>

              {/* Zoom Floating Controls */}
              <div className="absolute bottom-4 left-4 bg-[#0a1617]/90 border border-[#1e4848] p-1.5 rounded-lg flex items-center gap-1">
                <button
                  onClick={() => setZoomLevel((z) => Math.min(z + 0.2, 1.8))}
                  className="p-1.5 text-[#649c96] hover:text-white hover:bg-white/10 rounded cursor-pointer"
                >
                  <ZoomIn className="w-4 h-4" />
                </button>
                <span className="text-xs font-['Space_Mono'] text-white px-2">
                  {Math.round(zoomLevel * 100)}%
                </span>
                <button
                  onClick={() => setZoomLevel((z) => Math.max(z - 0.2, 0.6))}
                  className="p-1.5 text-[#649c96] hover:text-white hover:bg-white/10 rounded cursor-pointer"
                >
                  <ZoomOut className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setZoomLevel(1)}
                  className="p-1.5 text-[#649c96] hover:text-white hover:bg-white/10 rounded cursor-pointer"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>

          {/* Selected Anomaly / Inspector Card */}
          <div className="bg-[#0e2425]/90 border border-[#1b3b3a] rounded-xl p-5 shadow-2xl flex flex-col justify-between gap-4">
            <div>
              <div className="flex items-center justify-between pb-3 border-b border-[#183536]">
                <h3 className="font-['Poppins'] text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-[#ff5449]" />
                  <span>Anomaly Inspection Panel</span>
                </h3>
                <span className="text-xs font-['Space_Mono'] text-[#a3e635]">Live Analysis</span>
              </div>

              {selectedDefect ? (
                <div className="flex flex-col gap-3 my-4">
                  <div className="bg-[#071314] p-3.5 rounded-lg border border-[#173838] flex flex-col gap-2">
                    <div className="flex items-center justify-between">
                      <span className="font-['Poppins'] font-bold text-sm text-white">
                        {selectedDefect.defect}
                      </span>
                      <span
                        className={`text-[10px] font-['Space_Mono'] px-2 py-0.5 rounded font-bold uppercase ${
                          selectedDefect.severity === 'critical'
                            ? 'bg-[#ff5449]/20 text-[#ff8c82]'
                            : 'bg-[#ffb4ab]/20 text-[#ffc0b8]'
                        }`}
                      >
                        {selectedDefect.severity || 'HIGH'}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs font-['Space_Mono'] text-[#649c96] mt-2">
                      <div>
                        Chainage: <strong className="text-white">{selectedDefect.distance_m} m</strong>
                      </div>
                      <div>
                        Frame ID: <strong className="text-white">#{selectedDefect.frame_index}</strong>
                      </div>
                      <div>
                        Confidence: <strong className="text-[#a3e635]">{(selectedDefect.confidence * 100).toFixed(0)}%</strong>
                      </div>
                      <div>
                        Clock Pos: <strong className="text-white">12:00</strong>
                      </div>
                    </div>
                  </div>

                  {/* Pipe Specs */}
                  <div className="bg-[#071314] p-3.5 rounded-lg border border-[#173838] flex flex-col gap-2 text-xs font-['Space_Mono'] text-[#649c96]">
                    <div className="text-white font-bold mb-1">Pipe Segment Specifications</div>
                    <div className="flex justify-between">
                      <span>Inner Diameter:</span> <strong className="text-white">450 mm (18 in)</strong>
                    </div>
                    <div className="flex justify-between">
                      <span>Material:</span> <strong className="text-white">Reinforced Concrete</strong>
                    </div>
                    <div className="flex justify-between">
                      <span>Segment Length:</span> <strong className="text-white">61.0 m</strong>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center text-[#649c96] py-10 font-['Space_Mono'] text-xs">
                  Select a defect marker on the 3D pipe to inspect.
                </div>
              )}
            </div>

            <button
              onClick={() => navigate(`/missions/${missionId}/findings`)}
              className="w-full py-2.5 bg-[#5de6ff]/10 hover:bg-[#5de6ff]/20 border border-[#5de6ff]/30 text-[#5de6ff] rounded-lg font-['Space_Mono'] font-bold text-xs flex items-center justify-center gap-2 transition-all cursor-pointer"
            >
              <ShieldAlert className="w-4 h-4" />
              <span>Open Findings Directory</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}