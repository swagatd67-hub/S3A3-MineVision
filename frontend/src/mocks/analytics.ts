export interface NetworkNode {
  id: string;
  name: string;
  x: number; // percentage along width
  y: number; // percentage along height
  depthM: number;
  flowPct: number;
  siltDepthMm: number;
}

export interface CriticalPrioritySegment {
  id: string;
  pipeId: string;
  locationM: number;
  defectType: string;
  severity: "CRITICAL" | "MAJOR" | "MODERATE";
  radialAngle: string;
  wallLossPct: number;
}

export interface AnalyticsKpiData {
  totalInspectedM: number;
  totalInspectedTrendPct: number;
  defectsFound: number;
  defectsFoundTrendPct: number;
  criticalIssues: number;
  severityIndex: number;
  maxSeverityIndex: number;
}

export interface CleaningLifecyclePreset {
  jetPressurePsi: number;
  waterFlowLpm: number;
  nozzleRpm: number;
  debrisBeforePct: number;
  debrisAfterPct: number;
}

export const MOCK_NETWORK_NODES: NetworkNode[] = [
  { id: "mh-112", name: "MH-112", x: 13, y: 65, depthM: 3.4, flowPct: 22, siltDepthMm: 12 },
  { id: "mh-114", name: "MH-114", x: 33, y: 35, depthM: 4.1, flowPct: 35, siltDepthMm: 28 },
  { id: "mh-116", name: "MH-116", x: 57, y: 70, depthM: 4.8, flowPct: 48, siltDepthMm: 65 },
  { id: "mh-118", name: "MH-118", x: 79, y: 35, depthM: 3.9, flowPct: 15, siltDepthMm: 18 },
  { id: "mh-120", name: "MH-120", x: 91, y: 65, depthM: 3.2, flowPct: 10, siltDepthMm: 8 },
];

export const MOCK_CRITICAL_PRIORITY_SEGMENTS: CriticalPrioritySegment[] = [
  {
    id: "seg-1",
    pipeId: "LN-A-1024",
    locationM: 1245.5,
    defectType: "Longitudinal Crack",
    severity: "CRITICAL",
    radialAngle: "315°",
    wallLossPct: 34.2,
  },
  {
    id: "seg-2",
    pipeId: "LN-A-1089",
    locationM: 1890.2,
    defectType: "Joint Displacement",
    severity: "MAJOR",
    radialAngle: "270°",
    wallLossPct: 22.0,
  },
  {
    id: "seg-3",
    pipeId: "LN-B-0042",
    locationM: 45.0,
    defectType: "Corrosion Zone",
    severity: "CRITICAL",
    radialAngle: "190°",
    wallLossPct: 38.5,
  },
  {
    id: "seg-4",
    pipeId: "LN-A-0744",
    locationM: 744.1,
    defectType: "Weld Seam Separation",
    severity: "CRITICAL",
    radialAngle: "135°",
    wallLossPct: 29.8,
  },
  {
    id: "seg-5",
    pipeId: "LN-C-0210",
    locationM: 912.8,
    defectType: "Ovality Deformation",
    severity: "MAJOR",
    radialAngle: "045°",
    wallLossPct: 18.4,
  },
];

export const MOCK_ANALYTICS_KPIS: Record<"7D" | "30D" | "YTD", AnalyticsKpiData> = {
  "7D": {
    totalInspectedM: 14205,
    totalInspectedTrendPct: 12,
    defectsFound: 342,
    defectsFoundTrendPct: 5,
    criticalIssues: 18,
    severityIndex: 2.4,
    maxSeverityIndex: 10,
  },
  "30D": {
    totalInspectedM: 58430,
    totalInspectedTrendPct: 18,
    defectsFound: 1120,
    defectsFoundTrendPct: 3,
    criticalIssues: 45,
    severityIndex: 3.1,
    maxSeverityIndex: 10,
  },
  YTD: {
    totalInspectedM: 421800,
    totalInspectedTrendPct: 24,
    defectsFound: 8430,
    defectsFoundTrendPct: -2,
    criticalIssues: 210,
    severityIndex: 2.8,
    maxSeverityIndex: 10,
  },
};

export const MOCK_PIPE_SECTORS = [
  { id: "sector-7g", name: "Sector 7G Trunk" },
  { id: "line-a-sigma", name: "Line A-Sigma" },
  { id: "line-b-theta", name: "Line B-Theta" },
];

export const MOCK_CLEANING_PRESETS: Record<string, CleaningLifecyclePreset> = {
  IDLE: {
    jetPressurePsi: 0,
    waterFlowLpm: 0,
    nozzleRpm: 0,
    debrisBeforePct: 31,
    debrisAfterPct: 31,
  },
  APPROACH: {
    jetPressurePsi: 450,
    waterFlowLpm: 10.2,
    nozzleRpm: 200,
    debrisBeforePct: 31,
    debrisAfterPct: 28,
  },
  JETTING: {
    jetPressurePsi: 2850,
    waterFlowLpm: 48.2,
    nozzleRpm: 1420,
    debrisBeforePct: 31,
    debrisAfterPct: 6,
  },
  VERIFY: {
    jetPressurePsi: 120,
    waterFlowLpm: 5.0,
    nozzleRpm: 100,
    debrisBeforePct: 31,
    debrisAfterPct: 5,
  },
  COMPLETE: {
    jetPressurePsi: 0,
    waterFlowLpm: 0,
    nozzleRpm: 0,
    debrisBeforePct: 31,
    debrisAfterPct: 4,
  },
};
