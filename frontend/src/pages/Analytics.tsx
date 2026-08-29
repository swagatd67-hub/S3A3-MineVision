import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Ruler,
  Bug,
  AlertTriangle,
  Gauge,
  Download,
  Eye,
  ArrowUp,
  Play,
  Pause,
  RotateCcw,
  X,
  ChevronDown,
  Check,
  RefreshCw,
  AlertOctagon,
  Inbox,
  Lock,
} from 'lucide-react';
import {
  MOCK_NETWORK_NODES,
  MOCK_CRITICAL_PRIORITY_SEGMENTS,
  MOCK_ANALYTICS_KPIS,
  MOCK_PIPE_SECTORS,
  MOCK_CLEANING_PRESETS,
} from '../mocks/analytics';
import type {
  NetworkNode,
  CriticalPrioritySegment,
} from '../mocks/analytics';

type LifecycleState = 'IDLE' | 'APPROACH' | 'JETTING' | 'VERIFY' | 'COMPLETE';
type PageState = 'ready' | 'loading' | 'empty' | 'unavailable' | 'error';

interface AnalyticsProps {
  onSelectSegment?: (pipeId: string) => void;
  onNavigateToDigitalTwin?: (pipeId: string) => void;
}

export const Analytics: React.FC<AnalyticsProps> = ({
  onSelectSegment,
  onNavigateToDigitalTwin,
}) => {
  const navigate = useNavigate();

  // Primary filters
  const [timeRange, setTimeRange] = useState<'7D' | '30D' | 'YTD'>('7D');
  const [selectedPipe, setSelectedPipe] = useState('Sector 7G Trunk');
  const [showExportModal, setShowExportModal] = useState(false);
  const [copiedExport, setCopiedExport] = useState(false);

  // UI state simulation toggle (loading, empty, unavailable, error)
  const [pageState, setPageState] = useState<PageState>('ready');

  // 1. Interactive Pipe Network Map State
  const [selectedNode, setSelectedNode] = useState<NetworkNode | null>(MOCK_NETWORK_NODES[1]);
  const [isSimulatingRobot, setIsSimulatingRobot] = useState(false);
  const [robotProgress, setRobotProgress] = useState(0.42); // 0 to 1 along surveyed path
  const [selectedDefectPopup, setSelectedDefectPopup] = useState<'moderate' | 'severe' | null>(null);

  // 2. Interactive Pipe Wall Scan Unrolled Profile State
  const [chainageM, setChainageM] = useState(25.6);
  const maxChainageM = 61.0;
  const [isDraggingScan, setIsDraggingScan] = useState(false);
  const scanTrackRef = useRef<HTMLDivElement>(null);
  const [isAutoScanning, setIsAutoScanning] = useState(false);

  // 3. Interactive Cleaning Effectiveness Jetting Cycle State
  const [lifecycleState, setLifecycleState] = useState<LifecycleState>('JETTING');
  const [jettingTelemetry, setJettingTelemetry] = useState<{
    jetPressurePsi: number;
    waterFlowLpm: number;
    nozzleRpm: number;
  }>({
    jetPressurePsi: 2850,
    waterFlowLpm: 48.2,
    nozzleRpm: 1420,
  });

  // Derived telemetry from preset & active jetting cycle
  const currentPreset = MOCK_CLEANING_PRESETS[lifecycleState] ?? MOCK_CLEANING_PRESETS.IDLE;
  const debrisBefore = currentPreset.debrisBeforePct;
  const debrisAfter = currentPreset.debrisAfterPct;
  const jetPressurePsi = lifecycleState === 'JETTING' ? jettingTelemetry.jetPressurePsi : currentPreset.jetPressurePsi;
  const waterFlowLpm = lifecycleState === 'JETTING' ? jettingTelemetry.waterFlowLpm : currentPreset.waterFlowLpm;
  const nozzleRpm = lifecycleState === 'JETTING' ? jettingTelemetry.nozzleRpm : currentPreset.nozzleRpm;

  // Active KPI dataset based on time range
  const kpiData = MOCK_ANALYTICS_KPIS[timeRange];

  // Navigation helper to Digital Twin
  const handleNavigateToTwin = (pipeId: string) => {
    if (onNavigateToDigitalTwin) {
      onNavigateToDigitalTwin(pipeId);
    } else {
      navigate('/missions/M-104');
    }
  };

  // Segment selection handler
  const handleSegmentClick = (segment: CriticalPrioritySegment) => {
    if (onSelectSegment) {
      onSelectSegment(segment.pipeId);
    }
  };

  // Robot simulation and auto-scanning loop
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;
    if ((isSimulatingRobot || isAutoScanning) && pageState === 'ready') {
      interval = setInterval(() => {
        setRobotProgress((prev) => {
          const next = prev + 0.006;
          return next >= 1 ? 0 : next;
        });
        setChainageM((prev) => {
          const next = +(prev + 0.35).toFixed(1);
          return next >= maxChainageM ? 0.0 : next;
        });
      }, 100);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isSimulatingRobot, isAutoScanning, pageState]);

  // Jetting cycle dynamic telemetry update during JETTING
  useEffect(() => {
    if (pageState !== 'ready' || lifecycleState !== 'JETTING') return;

    const interval = setInterval(() => {
      setJettingTelemetry({
        jetPressurePsi: 2800 + Math.floor(Math.random() * 120),
        waterFlowLpm: +(47.5 + Math.random() * 1.8).toFixed(1),
        nozzleRpm: 1400 + Math.floor(Math.random() * 60),
      });
    }, 300);

    return () => clearInterval(interval);
  }, [lifecycleState, pageState]);

  // Compute 2D coordinates for surveyed path MH-112 -> MH-114 -> MH-116
  const getRobotCoordinates = () => {
    const p1 = MOCK_NETWORK_NODES[0];
    const p2 = MOCK_NETWORK_NODES[1];
    const p3 = MOCK_NETWORK_NODES[2];

    if (robotProgress <= 0.5) {
      const t = robotProgress / 0.5;
      return {
        x: p1.x + (p2.x - p1.x) * t,
        y: p1.y + (p2.y - p1.y) * t,
      };
    } else {
      const t = (robotProgress - 0.5) / 0.5;
      return {
        x: p2.x + (p3.x - p2.x) * t,
        y: p2.y + (p3.y - p2.y) * t,
      };
    }
  };

  const robotPos = getRobotCoordinates();

  // Scrubber drag & point handler
  const handleScanTrackPointer = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!scanTrackRef.current) return;
    const rect = scanTrackRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
    const pct = x / rect.width;
    const newM = +(pct * maxChainageM).toFixed(1);
    setChainageM(newM);
  };

  const csvContent =
    `PIPE_ID,LOCATION_M,DEFECT_TYPE,SEVERITY,STATUS\n` +
    MOCK_CRITICAL_PRIORITY_SEGMENTS.map(
      (s) => `${s.pipeId},${s.locationM},"${s.defectType}",${s.severity},ACTION_REQUIRED`
    ).join('\n');

  const copyToClipboard = () => {
    navigator.clipboard.writeText(csvContent);
    setCopiedExport(true);
    setTimeout(() => setCopiedExport(false), 2000);
  };

  return (
    <div id="analytics-screen-container" className="flex flex-col gap-6 max-w-[1600px] mx-auto w-full pb-10 px-4 md:px-6 pt-4">
      {/* Dashboard Header & Controls */}
      <header className="flex flex-col lg:flex-row justify-between items-start lg:items-end gap-6 border-b border-white/10 pb-4">
        <div>
          <h1 className="font-['Poppins'] text-3xl md:text-5xl lg:text-[44px] font-bold text-[#e5e2e1] tracking-tight mb-2">
            Inspection Analytics
          </h1>
          <p className="font-['Space_Mono'] text-xs md:text-[13px] text-[#c2cab0] flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#a3e635] shadow-[0_0_8px_#a3e635] animate-pulse" />
            <span>CONTINUOUS SPATIAL & DIAGNOSTIC ANALYTICS</span>
          </p>
        </div>

        <div className="flex flex-wrap gap-3 items-center">
          {/* State Mode Selector for UI Testing (loading, empty, unavailable, error) */}
          <div className="flex items-center gap-1 bg-[#121417] border border-white/10 rounded p-1 font-['Space_Mono'] text-[11px]">
            <span className="text-white/40 px-2">STATE:</span>
            {(['ready', 'loading', 'empty', 'unavailable', 'error'] as const).map((st) => (
              <button
                key={st}
                onClick={() => setPageState(st)}
                className={`px-2 py-1 rounded capitalize transition-colors ${
                  pageState === st ? 'bg-[#a3e635] text-[#121f00] font-bold' : 'text-white/60 hover:text-white'
                }`}
              >
                {st}
              </button>
            ))}
          </div>

          {/* Time Range Filter */}
          <div className="flex bg-[#1c1b1b]/60 backdrop-blur-md rounded border border-white/10 p-1">
            {(['7D', '30D', 'YTD'] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTimeRange(t)}
                className={`font-['Space_Mono'] text-xs px-3.5 py-1.5 rounded transition-colors ${
                  timeRange === t
                    ? 'bg-[#a3e635] text-black font-bold shadow-[0_0_10px_#a3e635]'
                    : 'text-[#c2cab0] hover:text-[#e5e2e1]'
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          {/* Pipe Selector */}
          <div className="relative">
            <select
              value={selectedPipe}
              onChange={(e) => setSelectedPipe(e.target.value)}
              className="appearance-none bg-[#1c1b1b]/60 backdrop-blur-md border border-white/10 rounded py-2 pl-4 pr-10 font-['Space_Mono'] text-xs text-[#e5e2e1] focus:outline-none focus:border-[#ccff80] focus:ring-1 focus:ring-[#ccff80] h-[38px]"
            >
              {MOCK_PIPE_SECTORS.map((sector) => (
                <option key={sector.id} value={sector.name} className="bg-[#1c1b1b] text-white">
                  {sector.name}
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-[#c2cab0] pointer-events-none w-4 h-4" />
          </div>

          {/* Live Survey Control */}
          <button
            onClick={() => {
              setIsSimulatingRobot(!isSimulatingRobot);
              setIsAutoScanning(!isAutoScanning);
            }}
            className="neo-btn rounded px-4 py-2 flex items-center gap-2 font-['Space_Mono'] text-xs text-[#ccff80] bg-[#1c1b1b] border border-[#ccff80]/40 h-[38px] hover:bg-[#ccff80]/10 hover:border-[#ccff80] cursor-pointer transition-all"
          >
            {isSimulatingRobot ? <Pause className="w-4 h-4 text-[#ccff80]" /> : <Play className="w-4 h-4 text-[#ccff80]" />}
            <span>{isSimulatingRobot ? 'PAUSE SURVEY' : 'LIVE SURVEY RUN'}</span>
          </button>
        </div>
      </header>

      {/* UI State Overlays: Loading / Empty / Unavailable / Error */}
      {pageState === 'loading' && (
        <div className="w-full bg-[#0a1617] border border-[#1b3b3a] rounded-xl p-16 flex flex-col items-center justify-center gap-4 text-center">
          <RefreshCw className="w-10 h-10 text-[#5de6ff] animate-spin" />
          <h3 className="font-['Poppins'] text-xl font-bold text-white">Loading Analytics Stream...</h3>
          <p className="font-['Space_Mono'] text-xs text-[#5de6ff]/70 max-w-md">
            Aggregating spatial network telemetry, sonar unrolled traces, and defect density metrics.
          </p>
        </div>
      )}

      {pageState === 'empty' && (
        <div className="w-full bg-[#0a1617] border border-[#1b3b3a] rounded-xl p-16 flex flex-col items-center justify-center gap-4 text-center">
          <Inbox className="w-10 h-10 text-[#c2cab0]/50" />
          <h3 className="font-['Poppins'] text-xl font-bold text-white">No Survey Data Available</h3>
          <p className="font-['Space_Mono'] text-xs text-[#c2cab0]/70 max-w-md">
            No inspection traces recorded for {selectedPipe} during the {timeRange} time range window.
          </p>
        </div>
      )}

      {pageState === 'unavailable' && (
        <div className="w-full bg-[#0a1617] border border-[#1b3b3a] rounded-xl p-16 flex flex-col items-center justify-center gap-4 text-center">
          <Lock className="w-10 h-10 text-[#f59e0b]" />
          <h3 className="font-['Poppins'] text-xl font-bold text-white">Sector Stream Offline</h3>
          <p className="font-['Space_Mono'] text-xs text-[#f59e0b]/80 max-w-md">
            Telemetry stream for {selectedPipe} is currently offline. Reconnect crawler hardware or switch sectors.
          </p>
        </div>
      )}

      {pageState === 'error' && (
        <div className="w-full bg-[#180a0a] border border-[#551b1b] rounded-xl p-16 flex flex-col items-center justify-center gap-4 text-center">
          <AlertOctagon className="w-10 h-10 text-[#ff5555]" />
          <h3 className="font-['Poppins'] text-xl font-bold text-[#ff5555]">Analytics Processing Error</h3>
          <p className="font-['Space_Mono'] text-xs text-[#ff5555]/80 max-w-md">
            Failed to parse spatial node graph. Check diagnostic log pipeline or retry connection.
          </p>
        </div>
      )}

      {/* Main Ready State Content */}
      {pageState === 'ready' && (
        <>
          {/* Top KPI Cards (Bento Grid Style) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* KPI 1 */}
            <div className="bg-[#121417] border border-white/10 rounded-lg p-5 relative group hover:border-[#ccff80]/30 transition-all">
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-[#ccff80]/50 to-transparent opacity-50 group-hover:opacity-100 transition-opacity" />
              <div className="flex justify-between items-start mb-4">
                <span className="font-['Space_Mono'] text-xs text-[#c2cab0] uppercase">Total Inspected</span>
                <Ruler className="w-5 h-5 text-[#c2cab0] opacity-50" />
              </div>
              <div className="font-['Space_Mono'] text-[32px] text-[#e5e2e1] leading-none font-bold">
                {kpiData.totalInspectedM.toLocaleString()} <span className="text-[16px] text-[#c2cab0]">m</span>
              </div>
              <div className="mt-3 font-['Space_Mono'] text-[12px] text-[#ccff80] flex items-center gap-1">
                <ArrowUp className="w-3.5 h-3.5" /> {kpiData.totalInspectedTrendPct}% vs last period
              </div>
            </div>

            {/* KPI 2 */}
            <div className="bg-[#121417] border border-white/10 rounded-lg p-5 relative group hover:border-[#00cbe6]/30 transition-all">
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-[#00cbe6]/50 to-transparent opacity-50 group-hover:opacity-100 transition-opacity" />
              <div className="flex justify-between items-start mb-4">
                <span className="font-['Space_Mono'] text-xs text-[#c2cab0] uppercase">Defects Found</span>
                <Bug className="w-5 h-5 text-[#c2cab0] opacity-50" />
              </div>
              <div className="font-['Space_Mono'] text-[32px] text-[#e5e2e1] leading-none font-bold">
                {kpiData.defectsFound.toLocaleString()}
              </div>
              <div className="mt-3 font-['Space_Mono'] text-[12px] text-[#ffb4ab] flex items-center gap-1">
                <ArrowUp className="w-3.5 h-3.5" /> {kpiData.defectsFoundTrendPct}% vs baseline
              </div>
            </div>

            {/* KPI 3 */}
            <div className="bg-[#121417] border border-white/10 rounded-lg p-5 relative group hover:border-[#ffb4ab]/30 transition-all">
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-[#ffb4ab]/50 to-transparent opacity-50 group-hover:opacity-100 transition-opacity" />
              <div className="flex justify-between items-start mb-4">
                <span className="font-['Space_Mono'] text-xs text-[#c2cab0] uppercase">Critical Issues</span>
                <AlertTriangle className="w-5 h-5 text-[#ffb4ab] opacity-80" />
              </div>
              <div className="font-['Space_Mono'] text-[32px] text-[#ffb4ab] leading-none font-bold">
                {kpiData.criticalIssues}
              </div>
              <div className="mt-3 font-['Space_Mono'] text-[12px] text-[#c2cab0]">
                Requires immediate action
              </div>
            </div>

            {/* KPI 4 */}
            <div className="bg-[#121417] border border-white/10 rounded-lg p-5 relative group hover:border-[#a3e635]/30 transition-all">
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-[#a3e635]/50 to-transparent opacity-50 group-hover:opacity-100 transition-opacity" />
              <div className="flex justify-between items-start mb-4">
                <span className="font-['Space_Mono'] text-xs text-[#c2cab0] uppercase">Severity Index</span>
                <Gauge className="w-5 h-5 text-[#c2cab0] opacity-50" />
              </div>
              <div className="flex items-end gap-2 leading-none">
                <div className="font-['Space_Mono'] text-[32px] text-[#ccff80] font-bold">{kpiData.severityIndex}</div>
                <div className="font-['Space_Mono'] text-[16px] text-[#c2cab0] mb-0.5">/ {kpiData.maxSeverityIndex}</div>
              </div>
              <div className="w-full bg-black/50 h-1 mt-3 rounded overflow-hidden">
                <div
                  className="bg-[#ccff80] h-full shadow-[0_0_8px_#a3e635] transition-all duration-300"
                  style={{ width: `${(kpiData.severityIndex / kpiData.maxSeverityIndex) * 100}%` }}
                />
              </div>
            </div>
          </div>

          {/* ========================================================================= */}
          {/* 1. Pipe Network Map (SPATIAL / MAPPING LAYER) */}
          {/* ========================================================================= */}
          <div
            id="pipe-network-map-panel"
            className="w-full bg-[#0a1617] border border-[#1b3b3a] rounded-xl p-6 relative overflow-hidden shadow-2xl flex flex-col gap-4"
            style={{
              backgroundImage: 'radial-gradient(#153837 1px, transparent 1px)',
              backgroundSize: '24px 24px',
            }}
          >
            {/* Map Header */}
            <div className="flex justify-between items-start z-10">
              <div>
                <h2 className="text-xl md:text-2xl font-bold text-[#e5e2e1] tracking-tight font-['Poppins']">
                  Pipe Network Map
                </h2>
                <div className="text-[11px] font-['Space_Mono'] text-[#5de6ff] mt-0.5 opacity-80">
                  Interactive Section: Click manhole nodes or drag crawler
                </div>
              </div>
              <div className="font-['Space_Mono'] text-xs text-[#4e8e89] tracking-widest uppercase">
                SPATIAL / MAPPING LAYER
              </div>
            </div>

            {/* SVG Interactive Map Visualizer */}
            <div className="relative w-full h-[280px] md:h-[340px] flex items-center justify-center my-2 select-none">
              <svg className="w-full h-full" viewBox="0 0 1000 350" preserveAspectRatio="none">
                <defs>
                  <filter id="glowCyan" x="-20%" y="-20%" width="140%" height="140%">
                    <feGaussianBlur stdDeviation="4" result="blur" />
                    <feComposite in="SourceGraphic" in2="blur" operator="over" />
                  </filter>
                </defs>

                {/* Segment 1: MH-112 to MH-114 (Surveyed) */}
                <line
                  x1="130"
                  y1="227"
                  x2="330"
                  y2="122"
                  stroke="#2dd4bf"
                  strokeWidth="4"
                  strokeLinecap="round"
                  className="opacity-85"
                />

                {/* Segment 2: MH-114 to MH-116 (Surveyed with Crawler) */}
                <line
                  x1="330"
                  y1="122"
                  x2="570"
                  y2="245"
                  stroke="#5de6ff"
                  strokeWidth="4"
                  strokeLinecap="round"
                  className="opacity-95"
                />

                {/* Segment 3: MH-116 to MH-118 (Unsurveyed Dotted) */}
                <line
                  x1="570"
                  y1="245"
                  x2="790"
                  y2="122"
                  stroke="#1f655e"
                  strokeWidth="3.5"
                  strokeDasharray="6 8"
                  strokeLinecap="round"
                />

                {/* Segment 4: MH-118 to MH-120 (Unsurveyed Dotted) */}
                <line
                  x1="790"
                  y1="122"
                  x2="910"
                  y2="227"
                  stroke="#1f655e"
                  strokeWidth="3.5"
                  strokeDasharray="6 8"
                  strokeLinecap="round"
                />

                {/* Moderate Defect Marker */}
                <g
                  className="cursor-pointer group"
                  onClick={() => setSelectedDefectPopup('moderate')}
                >
                  <circle cx="438" cy="177" r="9" fill="#f59e0b" className="transition-transform group-hover:scale-125" />
                  <circle cx="438" cy="177" r="14" fill="#f59e0b" opacity="0.25" className="animate-pulse" />
                </g>

                {/* Severe Defect Marker */}
                <g
                  className="cursor-pointer group"
                  onClick={() => setSelectedDefectPopup('severe')}
                >
                  <circle cx="669" cy="190" r="9" fill="#ff5555" className="transition-transform group-hover:scale-125" />
                  <circle cx="669" cy="190" r="15" fill="#ff5555" opacity="0.3" className="animate-pulse" />
                </g>

                {/* Robot Position Marker */}
                <g
                  transform={`translate(${robotPos.x * 10}, ${robotPos.y * 3.5})`}
                  className="cursor-pointer"
                  filter="url(#glowCyan)"
                >
                  <circle cx="0" cy="0" r="18" fill="#5de6ff" opacity="0.2" className="animate-ping" />
                  <circle cx="0" cy="0" r="10" fill="#5de6ff" opacity="0.4" />
                  <circle cx="0" cy="0" r="6" fill="#a2eeff" stroke="#001f25" strokeWidth="2" />
                </g>

                {/* Manhole Nodes */}
                {MOCK_NETWORK_NODES.map((node) => {
                  const isSelected = selectedNode?.id === node.id;
                  const cx = node.x * 10;
                  const cy = node.y * 3.5;
                  return (
                    <g
                      key={node.id}
                      onClick={() => setSelectedNode(node)}
                      className="cursor-pointer group"
                    >
                      <circle
                        cx={cx}
                        cy={cy}
                        r={isSelected ? '14' : '11'}
                        fill="#0a1617"
                        stroke="#5de6ff"
                        strokeWidth={isSelected ? '3.5' : '2.5'}
                        className="transition-all group-hover:stroke-[#ccff80]"
                      />
                      <circle
                        cx={cx}
                        cy={cy}
                        r="4"
                        fill={isSelected ? '#ccff80' : '#2dd4bf'}
                      />
                      <text
                        x={cx}
                        y={cy < 150 ? cy - 20 : cy + 30}
                        textAnchor="middle"
                        fill="#75b2ab"
                        fontSize="13"
                        fontFamily="Space Mono, monospace"
                        fontWeight="bold"
                        className="group-hover:fill-white transition-colors"
                      >
                        {node.name}
                      </text>
                    </g>
                  );
                })}
              </svg>

              {/* Node Telemetry Flyout Card */}
              {selectedNode && (
                <div className="absolute top-2 right-2 md:right-4 bg-[#081213]/90 border border-[#2dd4bf]/40 p-3 rounded-lg backdrop-blur-md shadow-xl text-xs font-['Space_Mono'] z-20 max-w-[210px]">
                  <div className="flex justify-between items-center text-[#5de6ff] font-bold border-b border-white/10 pb-1 mb-1.5">
                    <span>STATION: {selectedNode.name}</span>
                    <button onClick={() => setSelectedNode(null)} className="text-white/40 hover:text-white">
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                  <div className="flex flex-col gap-1 text-[#c2cab0] text-[11px]">
                    <div className="flex justify-between">
                      <span>Depth:</span>
                      <span className="text-white font-bold">{selectedNode.depthM} m</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Hydraulic Flow:</span>
                      <span className="text-[#5de6ff] font-bold">{selectedNode.flowPct}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Silt Deposit:</span>
                      <span className="text-[#f59e0b] font-bold">{selectedNode.siltDepthMm} mm</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Defect Popup Overlay */}
              {selectedDefectPopup && (
                <div className="absolute bottom-16 left-1/2 -translate-x-1/2 bg-[#0e0e0e] border border-white/20 p-3 rounded-xl shadow-2xl z-30 flex items-center gap-3 font-['Space_Mono'] text-xs">
                  <div className={`w-3 h-3 rounded-full ${selectedDefectPopup === 'severe' ? 'bg-[#ff5555]' : 'bg-[#f59e0b]'}`} />
                  <div className="text-white">
                    <span className="font-bold uppercase">
                      {selectedDefectPopup === 'severe' ? 'CRITICAL SEVERE DEFECT' : 'MODERATE STRUCTURAL ANOMALY'}
                    </span>
                    <span className="text-[#c2cab0] ml-2">
                      @ {selectedDefectPopup === 'severe' ? 'Chainage 40.5m' : 'Chainage 25.6m'}
                    </span>
                  </div>
                  <button
                    onClick={() => setSelectedDefectPopup(null)}
                    className="ml-2 text-white/50 hover:text-white p-1"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
            </div>

            {/* Map Legend Bar */}
            <div className="flex flex-wrap items-center justify-start gap-6 pt-3 border-t border-[#153837] font-['Space_Mono'] text-[12px] text-[#7eb3ad]">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm bg-[#5de6ff] shadow-[0_0_8px_#5de6ff]" />
                <span>Robot position</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm bg-[#f59e0b]" />
                <span>Defect — moderate</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm bg-[#ff5555]" />
                <span>Defect — severe</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm bg-[#1f655e] border border-[#2dd4bf]/40" />
                <span>Unsurveyed segment</span>
              </div>
            </div>
          </div>

          {/* ========================================================================= */}
          {/* 2. Pipe Wall Scan & 3. Cleaning Effectiveness (2-Column Grid) */}
          {/* ========================================================================= */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Pipe Wall Scan — Unrolled Profile */}
            <div
              id="pipe-wall-scan-panel"
              className="bg-[#0a1617] border border-[#1b3b3a] rounded-xl p-6 relative overflow-hidden shadow-2xl flex flex-col justify-between gap-4"
            >
              <div className="flex justify-between items-start">
                <h2 className="text-xl font-bold text-[#e5e2e1] tracking-tight font-['Poppins']">
                  Pipe Wall Scan — Unrolled Profile
                </h2>
                <div className="font-['Space_Mono'] text-[11px] text-[#4e8e89] tracking-widest uppercase">
                  CONTINUOUS SURVEY TRACE
                </div>
              </div>

              {/* Unrolled Trace Viewport */}
              <div className="flex flex-col gap-3 my-2">
                <div
                  ref={scanTrackRef}
                  onPointerDown={(e) => {
                    setIsDraggingScan(true);
                    handleScanTrackPointer(e);
                  }}
                  onPointerMove={(e) => {
                    if (isDraggingScan) handleScanTrackPointer(e);
                  }}
                  onPointerUp={() => setIsDraggingScan(false)}
                  className="relative w-full h-36 bg-[#061011] border border-[#153837] rounded-lg overflow-hidden cursor-crosshair select-none"
                  style={{
                    backgroundImage:
                      'linear-gradient(to right, rgba(37, 117, 108, 0.15) 1px, transparent 1px), linear-gradient(to bottom, rgba(37, 117, 108, 0.08) 1px, transparent 1px)',
                    backgroundSize: '16.66% 20px',
                  }}
                >
                  <svg className="absolute inset-0 w-full h-full opacity-20 pointer-events-none" preserveAspectRatio="none">
                    <path d="M0,70 Q75,30 150,70 T300,70 T450,70 T600,70" fill="none" stroke="#2dd4bf" strokeWidth="1.5" />
                    <path d="M0,85 Q100,110 200,85 T400,85 T600,85" fill="none" stroke="#5de6ff" strokeWidth="1" />
                  </svg>

                  {/* Moderate Defect Caliper @ 25m */}
                  <div className="absolute top-2 bottom-2 w-[2px] bg-[#f59e0b] left-[41%] flex items-center justify-center pointer-events-none">
                    <div className="w-2.5 h-2.5 rounded-full bg-[#f59e0b] shadow-[0_0_8px_#f59e0b]" />
                  </div>

                  {/* Severe Defect Caliper @ 40.5m */}
                  <div className="absolute top-2 bottom-2 w-[2px] bg-[#ff5555] left-[66%] flex items-center justify-center pointer-events-none">
                    <div className="w-2.5 h-2.5 rounded-full bg-[#ff5555] shadow-[0_0_8px_#ff5555]" />
                  </div>

                  {/* Active Laser Head / Scanner Beam */}
                  <div
                    className="absolute top-0 bottom-0 w-4 -ml-2 bg-gradient-to-r from-transparent via-[#5de6ff]/60 to-[#5de6ff] shadow-[0_0_15px_#5de6ff] pointer-events-none transition-all duration-75"
                    style={{ left: `${(chainageM / maxChainageM) * 100}%` }}
                  >
                    <div className="w-[2px] h-full bg-white ml-auto" />
                  </div>

                  {/* Scrubber Tooltip */}
                  <div
                    className="absolute bottom-2 font-['Space_Mono'] text-[10px] text-[#5de6ff] px-2 py-0.5 bg-black/80 rounded border border-[#5de6ff]/40 pointer-events-none -translate-x-1/2"
                    style={{ left: `${(chainageM / maxChainageM) * 100}%` }}
                  >
                    {chainageM}m
                  </div>
                </div>

                {/* Distance Axis Markers */}
                <div className="flex justify-between font-['Space_Mono'] text-[11px] text-[#528782] px-1">
                  <span>0m</span>
                  <span>10m</span>
                  <span>20m</span>
                  <span>30m</span>
                  <span>40m</span>
                  <span>50m</span>
                  <span>60m</span>
                </div>
              </div>

              {/* Chainage Readout & Scan Controls */}
              <div className="flex justify-between items-center pt-2 border-t border-[#153837]">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setIsAutoScanning(!isAutoScanning)}
                    className="px-3 py-1 rounded bg-[#153837] hover:bg-[#25756c] text-white font-['Space_Mono'] text-xs flex items-center gap-1.5 transition-colors cursor-pointer"
                  >
                    {isAutoScanning ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 text-[#5de6ff]" />}
                    <span>{isAutoScanning ? 'PAUSE' : 'SCAN TRACE'}</span>
                  </button>
                  <button
                    onClick={() => setChainageM(0)}
                    className="p-1.5 rounded bg-[#153837] hover:bg-[#25756c] text-white transition-colors cursor-pointer"
                    title="Reset Scan to 0m"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                  </button>
                </div>

                <div className="font-['Space_Mono'] text-sm md:text-base font-bold tracking-wider text-[#5de6ff]">
                  CHAINAGE <span className="text-white font-black">{chainageM.toFixed(1)} m</span> / {maxChainageM.toFixed(1)} m
                </div>
              </div>
            </div>

            {/* Cleaning Effectiveness (JETTING CYCLE) */}
            <div
              id="cleaning-effectiveness-panel"
              className="bg-[#0a1617] border border-[#1b3b3a] rounded-xl p-6 relative overflow-hidden shadow-2xl flex flex-col justify-between gap-4"
            >
              <div className="flex justify-between items-start">
                <h2 className="text-xl font-bold text-[#e5e2e1] tracking-tight font-['Poppins']">
                  Cleaning Effectiveness
                </h2>
                <div className="font-['Space_Mono'] text-[11px] text-[#4e8e89] tracking-widest uppercase">
                  JETTING CYCLE
                </div>
              </div>

              {/* Debris Bar Chart */}
              <div className="flex items-end justify-center gap-16 md:gap-24 h-44 my-2 px-8">
                <div className="flex flex-col items-center gap-2 flex-1 max-w-[120px] h-full justify-end">
                  <div
                    className="w-full bg-gradient-to-t from-[#d97706] to-[#f59e0b] rounded-t-sm shadow-[0_0_15px_rgba(245,158,11,0.3)] transition-all duration-500"
                    style={{ height: `${(debrisBefore / 40) * 100}%` }}
                  />
                  <div className="font-['Space_Mono'] text-xl md:text-2xl font-bold text-white leading-none">
                    {debrisBefore}%
                  </div>
                  <div className="font-['Space_Mono'] text-[11px] text-[#7eb3ad] tracking-wider uppercase whitespace-nowrap">
                    DEBRIS — BEFORE
                  </div>
                </div>

                <div className="flex flex-col items-center gap-2 flex-1 max-w-[120px] h-full justify-end">
                  <div
                    className="w-full bg-gradient-to-t from-[#0284c7] to-[#5de6ff] rounded-t-sm shadow-[0_0_15px_rgba(93,230,255,0.4)] transition-all duration-500"
                    style={{ height: `${(debrisAfter / 40) * 100}%` }}
                  />
                  <div className="font-['Space_Mono'] text-xl md:text-2xl font-bold text-[#5de6ff] leading-none">
                    {debrisAfter}%
                  </div>
                  <div className="font-['Space_Mono'] text-[11px] text-[#7eb3ad] tracking-wider uppercase whitespace-nowrap">
                    DEBRIS — AFTER
                  </div>
                </div>
              </div>

              {/* Jetting Specs */}
              <div className="grid grid-cols-3 gap-2 py-2 px-3 bg-[#061011] rounded-lg border border-[#153837] font-['Space_Mono'] text-[11px]">
                <div>
                  <span className="text-[#528782] block">PRESSURE</span>
                  <span className="text-[#5de6ff] font-bold">{jetPressurePsi} PSI</span>
                </div>
                <div>
                  <span className="text-[#528782] block">FLOW RATE</span>
                  <span className="text-white font-bold">{waterFlowLpm} L/min</span>
                </div>
                <div>
                  <span className="text-[#528782] block">NOZZLE HEAD</span>
                  <span className="text-[#ccff80] font-bold">{nozzleRpm} RPM</span>
                </div>
              </div>

              {/* Lifecycle State Buttons */}
              <div className="flex flex-col gap-2 pt-2 border-t border-[#153837]">
                <div className="font-['Space_Mono'] text-[10px] text-[#528782] uppercase tracking-wider">
                  LIFECYCLE STATE
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {(['IDLE', 'APPROACH', 'JETTING', 'VERIFY', 'COMPLETE'] as LifecycleState[]).map((st) => {
                    const isActive = lifecycleState === st;
                    return (
                      <button
                        key={st}
                        onClick={() => setLifecycleState(st)}
                        className={`font-['Space_Mono'] text-xs px-3.5 py-1.5 rounded transition-all cursor-pointer ${
                          isActive
                            ? 'bg-[#a3e635] text-black font-bold shadow-[0_0_12px_#a3e635]'
                            : 'bg-[#0e2425] text-[#7eb3ad] hover:text-white hover:bg-[#153837] border border-[#1b3b3a]'
                        }`}
                      >
                        {st}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>

          {/* Priority Segments Table Area */}
          <div className="bg-[#121417] border border-white/10 rounded-xl p-5 md:p-6 flex flex-col">
            <div className="flex justify-between items-center mb-6">
              <h2 className="font-['Poppins'] text-2xl text-[#e5e2e1] font-bold">
                Critical Priority Segments
              </h2>
              <button
                onClick={() => setShowExportModal(true)}
                className="px-3.5 py-1.5 rounded bg-[#1c1b1b] border border-[#ccff80]/40 text-[#ccff80] font-['Space_Mono'] text-xs flex items-center gap-1.5 hover:bg-[#ccff80]/10 hover:border-[#ccff80] cursor-pointer transition-all"
              >
                <span>EXPORT</span>
                <Download className="w-3.5 h-3.5 text-[#ccff80]" />
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-white/10 text-[#c2cab0] font-['Space_Mono'] text-xs">
                    <th className="pb-3 pl-2 font-normal">PIPE ID</th>
                    <th className="pb-3 font-normal">LOCATION (M)</th>
                    <th className="pb-3 font-normal">DEFECT TYPE</th>
                    <th className="pb-3 font-normal">SEVERITY</th>
                    <th className="pb-3 text-right pr-2 font-normal">ACTION</th>
                  </tr>
                </thead>
                <tbody className="font-['Space_Mono'] text-[13px]">
                  {MOCK_CRITICAL_PRIORITY_SEGMENTS.map((seg) => (
                    <tr
                      key={seg.id}
                      onClick={() => handleSegmentClick(seg)}
                      className="border-b border-white/5 hover:bg-white/5 transition-colors group cursor-pointer"
                    >
                      <td className="py-4 pl-2 text-[#ccff80] font-bold">{seg.pipeId}</td>
                      <td className="py-4 text-[#e5e2e1]">{seg.locationM.toLocaleString()}</td>
                      <td className="py-4 text-[#e5e2e1]">{seg.defectType}</td>
                      <td className="py-4">
                        <span
                          className={`inline-flex items-center gap-2 px-2 py-1 rounded text-[10px] uppercase font-bold border ${
                            seg.severity === 'CRITICAL'
                              ? 'bg-[#ffb4ab]/10 text-[#ffb4ab] border-[#ffb4ab]/20'
                              : 'bg-[#2fd9f4]/10 text-[#2fd9f4] border-[#2fd9f4]/20'
                          }`}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${
                              seg.severity === 'CRITICAL' ? 'bg-[#ffb4ab] animate-pulse' : 'bg-[#2fd9f4]'
                            }`}
                          />
                          {seg.severity}
                        </span>
                      </td>
                      <td className="py-4 text-right pr-2">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleNavigateToTwin(seg.pipeId);
                          }}
                          className="text-[#c2cab0] hover:text-[#ccff80] transition-colors opacity-80 group-hover:opacity-100 p-1"
                          title="View Digital Twin"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* Export CSV Modal */}
      {showExportModal && (
        <div className="fixed inset-0 bg-black/85 backdrop-blur-md z-50 flex items-center justify-center p-4">
          <div className="bg-[#1c1b1b] border border-white/20 rounded-xl max-w-lg w-full p-6 shadow-2xl relative">
            <button
              onClick={() => setShowExportModal(false)}
              className="absolute top-4 right-4 text-[#c2cab0] hover:text-white p-1"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="font-['Poppins'] font-bold text-xl text-[#e5e2e1] uppercase tracking-tight mb-2 flex items-center gap-2">
              <Download className="w-5 h-5 text-[#ccff80]" />
              <span>Export Critical Priority Segments</span>
            </div>

            <p className="text-xs font-['Space_Mono'] text-[#c2cab0] mb-4">
              Generated structured CSV dataset formatted for pipeline engineering dispatch and GIS systems.
            </p>

            <pre className="bg-[#0e0e0e] p-3 rounded border border-white/10 font-['Space_Mono'] text-[11px] text-[#ccff80] overflow-x-auto max-h-48 mb-4">
              {csvContent}
            </pre>

            <div className="flex justify-end gap-3 font-['Space_Mono'] text-xs">
              <button
                onClick={() => setShowExportModal(false)}
                className="px-4 py-2 rounded bg-white/5 border border-white/10 text-[#c2cab0] hover:text-white cursor-pointer"
              >
                CLOSE
              </button>
              <button
                onClick={copyToClipboard}
                className="px-4 py-2 rounded bg-[#ccff80] text-black font-bold flex items-center gap-1.5 hover:bg-white transition-all shadow-[0_0_12px_rgba(204,255,128,0.4)] cursor-pointer"
              >
                {copiedExport ? <Check className="w-3.5 h-3.5" /> : <Download className="w-3.5 h-3.5" />}
                <span>{copiedExport ? 'COPIED TO CLIPBOARD' : 'COPY CSV DATA'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Analytics;
