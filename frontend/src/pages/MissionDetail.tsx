import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowLeft,
  Box,
  FileText,
  Play,
  ShieldAlert,
  RefreshCw,
  AlertOctagon,
  Activity,
  Layers,
} from 'lucide-react';
import { getMission } from '../api/missions';
import { getMissionDigitalTwin, getMissionSnapshot, getMission3DReconstruction } from '../api/digitalTwin';
import { getMissionObservations } from '../api/findings';
import ThreeDPipeViewer from '../components/ThreeDPipeViewer';
import type { Mission } from '../types/mission';
import type {
  DigitalTwinState,
  MapObservation,
  MissionSnapshot,
  Reconstruction3DOutput,
  ReconstructionDefect,
} from '../types/digitalTwin';

/**
 * Calculates a client-derived 12-hour clock position from observation 2D bounding box.
 */
function deriveClockPosition(obs: MapObservation): { clockStr: string; normU: number } {
  if (!obs.box) {
    return { clockStr: '12:00 (Center)', normU: 0.5 };
  }

  let u1 = 0.5;
  let u2 = 0.5;

  if (Array.isArray(obs.box)) {
    u1 = (obs.box as number[])[1] ?? 0.5;
    u2 = (obs.box as number[])[3] ?? 0.5;
  } else if (typeof obs.box === 'object') {
    const b = obs.box as { x1?: number; x2?: number; xmin?: number; xmax?: number };
    u1 = b.x1 ?? b.xmin ?? 0.5;
    u2 = b.x2 ?? b.xmax ?? 0.5;
  }

  const uCenter = (u1 + u2) / 2;
  // If box coordinates are normalized (0..1), normU = uCenter, else assume 1920px width
  const normU = uCenter <= 1.0 ? uCenter : uCenter / 1920;
  const hour = Math.round(normU * 12) % 12;
  const displayHour = hour === 0 ? 12 : hour;
  return { clockStr: `${displayHour}:00`, normU };
}

export default function MissionDetail() {
  const { missionId = 'M-104' } = useParams<{ missionId: string }>();
  const navigate = useNavigate();

  const [mission, setMission] = useState<Mission | null>(null);
  const [snapshot, setSnapshot] = useState<MissionSnapshot | null>(null);
  const [digitalTwin, setDigitalTwin] = useState<DigitalTwinState | null>(null);
  const [reconstruction, setReconstruction] = useState<Reconstruction3DOutput | null>(null);
  const [fallbackObservations, setFallbackObservations] = useState<MapObservation[]>([]);
  const [selectedObservation, setSelectedObservation] = useState<MapObservation | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadTrigger, setReloadTrigger] = useState<number>(0);

  // 3D Digital Twin Viewer controls
  const [isWireframe, setIsWireframe] = useState<boolean>(false);

  useEffect(() => {
    let isMounted = true;

    Promise.allSettled([
      getMission(missionId),
      getMissionSnapshot(missionId),
      getMissionDigitalTwin(missionId),
      getMissionObservations(missionId),
      getMission3DReconstruction(missionId),
    ])
      .then(([missionRes, snapshotRes, twinRes, obsRes, reconRes]) => {
        if (!isMounted) return;

        let hasData = false;
        let loadedObs: MapObservation[] = [];

        if (missionRes.status === 'fulfilled') {
          setMission(missionRes.value);
          hasData = true;
        }

        if (snapshotRes.status === 'fulfilled') {
          setSnapshot(snapshotRes.value);
          hasData = true;
        }

        if (twinRes.status === 'fulfilled') {
          setDigitalTwin(twinRes.value);
          hasData = true;
          const twinObs = twinRes.value?.inspection_map?.observations || twinRes.value?.latest_observations || [];
          if (twinObs.length > 0) {
            loadedObs = twinObs;
          }
        }

        if (reconRes.status === 'fulfilled') {
          setReconstruction(reconRes.value);
          hasData = true;
        }

        if (obsRes.status === 'fulfilled' && obsRes.value?.observations) {
          hasData = true;
          const mappedFromApi: MapObservation[] = obsRes.value.observations.map((o) => ({
            observation_id: o.observation_id,
            frame_index: o.frame_index,
            class_code: o.class_code,
            confidence: o.confidence,
            distance_m: o.distance_m ?? 0,
            box: o.box as MapObservation['box'],
            localization_quality: o.localization_quality ?? undefined,
          }));
          setFallbackObservations(mappedFromApi);
          if (loadedObs.length === 0) {
            loadedObs = mappedFromApi;
          }
        }

        if (loadedObs.length > 0) {
          setSelectedObservation(loadedObs[0]);
        }

        if (!hasData) {
          setError(`Mission '${missionId}' could not be fetched from PipeVision API server.`);
        }
        setLoading(false);
      })
      .catch((err) => {
        if (!isMounted) return;
        console.error(`Failed to fetch mission data for ${missionId}:`, err);
        setError(`Failed to connect to PipeVision backend API.`);
        setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [missionId, reloadTrigger]);

  // Observations list from real backend InspectionMap or DigitalTwinState or direct observations API
  const observations: MapObservation[] =
    digitalTwin?.inspection_map?.observations?.length
      ? digitalTwin.inspection_map.observations
      : digitalTwin?.latest_observations?.length
      ? digitalTwin.latest_observations
      : snapshot?.digital_twin?.inspection_map?.observations?.length
      ? snapshot.digital_twin.inspection_map.observations
      : fallbackObservations;

  // Total inspected distance from snapshot or digital twin mission state
  const totalInspectedDistance =
    snapshot?.progress?.total_inspected_distance_m ??
    digitalTwin?.mission?.total_inspected_distance_m ??
    digitalTwin?.robot?.distance_m ??
    null;

  // Pipe Diameter metrics from Morphology or Robot Body
  const morphologyMetrics = digitalTwin?.morphology_summary?.metrics;
  const meanDiameterMm = morphologyMetrics?.mean_observed_diameter_mm;
  const maxDeformationPct = morphologyMetrics?.max_deformation_percent;
  const robotBodyDiameterMm = digitalTwin?.robot?.body_diameter_mm;

  // Synchronization status
  const syncStatus = digitalTwin?.system?.synchronization_status || 'INITIALIZING';

  // Derived selected observation details
  const selectedClock = selectedObservation ? deriveClockPosition(selectedObservation) : null;

  const missionStatusLower = mission?.status ? String(mission.status).toLowerCase() : '';

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
                    missionStatusLower === 'active' || missionStatusLower === 'running'
                      ? 'bg-[#a3e635]/20 text-[#a3e635] border border-[#a3e635]/40 animate-pulse'
                      : missionStatusLower === 'completed'
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

              {/* Digital Twin Synchronization Status Badge */}
              <span
                className={`px-2.5 py-0.5 rounded text-[10px] font-['Space_Mono'] font-bold uppercase ${
                  syncStatus === 'SYNCHRONIZED'
                    ? 'bg-[#a3e635]/20 text-[#a3e635] border border-[#a3e635]/40'
                    : syncStatus === 'INITIALIZING'
                    ? 'bg-[#5de6ff]/20 text-[#5de6ff] border border-[#5de6ff]/40'
                    : syncStatus === 'STALE' || syncStatus === 'DEGRADED'
                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                    : 'bg-red-500/20 text-red-300 border border-red-500/40'
                }`}
              >
                SYNC: {syncStatus}
              </span>
            </div>
            <h1 className="font-['Poppins'] text-xl sm:text-2xl font-black uppercase tracking-wider text-white mt-1">
              Digital Twin & Pipe Reconstruction
            </h1>
            {mission && (
              <p className="text-xs font-['Space_Mono'] text-[#649c96] mt-0.5">
                {mission.notes || 'Pipeline Inspection Task'} • Robot:{' '}
                <strong className="text-white">{mission.robot_id || snapshot?.robot_id || 'ROV-01'}</strong>
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
              Digital Twin Fetch Error
            </div>
            <div className="font-['Space_Mono'] text-xs text-[#ff8c82] mt-1 max-w-md">
              {error}
            </div>
          </div>
          <button
            onClick={() => {
              setLoading(true);
              setError(null);
              setReloadTrigger((prev) => prev + 1);
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
                  Sewer Cylinder Spatial Map
                </h3>
              </div>

              <div className="flex items-center gap-2 bg-[#071314] p-1 rounded-lg border border-[#173838]">
                <button
                  onClick={() => setIsWireframe(!isWireframe)}
                  className={`px-2.5 py-1 rounded text-[11px] font-['Space_Mono'] transition-all cursor-pointer ${
                    isWireframe ? 'bg-[#5de6ff] text-[#001f25] font-bold' : 'text-[#649c96] hover:text-white'
                  }`}
                >
                  Wireframe
                </button>
              </div>
            </div>

            {/* Interactive 3D WebGL Pipe Reconstruction Canvas Container */}
            <ThreeDPipeViewer
              reconstruction={reconstruction}
              selectedDefectId={selectedObservation?.observation_id}
              onSelectDefect={(defect: ReconstructionDefect) => {
                const match = observations.find((o) => o.observation_id === defect.id);
                if (match) {
                  setSelectedObservation(match);
                } else {
                  setSelectedObservation({
                    observation_id: defect.id,
                    frame_index: defect.frame_index || 0,
                    class_code: defect.class_code,
                    confidence: defect.confidence,
                    distance_m: defect.distance_m,
                    box: defect.box as MapObservation['box'],
                  });
                }
              }}
              isWireframe={isWireframe}
            />

          </div>

          {/* Selected Anomaly / Inspector Card */}
          <div className="bg-[#0e2425]/90 border border-[#1b3b3a] rounded-xl p-5 shadow-2xl flex flex-col justify-between gap-4">
            <div>
              <div className="flex items-center justify-between pb-3 border-b border-[#183536]">
                <h3 className="font-['Poppins'] text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-[#ff5449]" />
                  <span>Anomaly Inspector</span>
                </h3>
                <span className="text-xs font-['Space_Mono'] text-[#a3e635]">Real Observation</span>
              </div>

              {selectedObservation ? (
                <div className="flex flex-col gap-3 my-4">
                  <div className="bg-[#071314] p-3.5 rounded-lg border border-[#173838] flex flex-col gap-2">
                    <div className="flex items-center justify-between">
                      <span className="font-['Poppins'] font-bold text-sm text-white uppercase">
                        {selectedObservation.class_code}
                      </span>
                      <span
                        className={`text-[10px] font-['Space_Mono'] px-2 py-0.5 rounded font-bold uppercase ${
                          selectedObservation.confidence > 0.8
                            ? 'bg-[#ff5449]/20 text-[#ff8c82]'
                            : 'bg-[#ffb4ab]/20 text-[#ffc0b8]'
                        }`}
                      >
                        {selectedObservation.confidence > 0.8 ? 'HIGH CONF' : 'MEDIUM'}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs font-['Space_Mono'] text-[#649c96] mt-2">
                      <div>
                        Chainage: <strong className="text-white">{selectedObservation.distance_m.toFixed(2)} m</strong>
                      </div>
                      <div>
                        Frame ID: <strong className="text-white">#{selectedObservation.frame_index}</strong>
                      </div>
                      <div>
                        Confidence: <strong className="text-[#a3e635]">{(selectedObservation.confidence * 100).toFixed(1)}%</strong>
                      </div>
                      <div>
                        Clock Pos:{' '}
                        <strong className="text-white" title="Client derived from 2D observation bounding box">
                          {selectedClock?.clockStr}
                        </strong>
                      </div>
                      <div className="col-span-2">
                        Obs ID: <strong className="text-white">{selectedObservation.observation_id}</strong>
                      </div>
                      <div className="col-span-2">
                        Localization:{' '}
                        <strong className="text-[#5de6ff]">{selectedObservation.localization_quality}</strong>
                      </div>
                    </div>
                  </div>

                  {/* Pipe Specifications from Real Backend Morphology */}
                  <div className="bg-[#071314] p-3.5 rounded-lg border border-[#173838] flex flex-col gap-2 text-xs font-['Space_Mono'] text-[#649c96]">
                    <div className="text-white font-bold mb-1 flex items-center justify-between">
                      <span>Pipe Segment Specifications</span>
                      <Activity className="w-3.5 h-3.5 text-[#5de6ff]" />
                    </div>
                    <div className="flex justify-between">
                      <span>Inner Diameter:</span>{' '}
                      <strong className="text-white">
                        {meanDiameterMm != null
                          ? `${Math.round(meanDiameterMm)} mm (Observed Mean)`
                          : robotBodyDiameterMm != null
                          ? `${Math.round(robotBodyDiameterMm)} mm (Body Estimate)`
                          : 'Unavailable (Uncalibrated)'}
                      </strong>
                    </div>
                    <div className="flex justify-between">
                      <span>Material:</span> <strong className="text-white">Not available</strong>
                    </div>
                    <div className="flex justify-between">
                      <span>Inspected Distance:</span>{' '}
                      <strong className="text-white">
                        {totalInspectedDistance != null
                          ? `${totalInspectedDistance.toFixed(1)} m`
                          : 'Unavailable'}
                      </strong>
                    </div>
                    {maxDeformationPct != null && (
                      <div className="flex justify-between">
                        <span>Max Deformation:</span>{' '}
                        <strong className="text-amber-300">{maxDeformationPct.toFixed(1)}%</strong>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="text-center text-[#649c96] py-10 font-['Space_Mono'] text-xs flex flex-col items-center gap-2">
                  <Layers className="w-6 h-6 text-[#649c96]/50" />
                  <span>Select an observation marker on the spatial map to inspect details.</span>
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