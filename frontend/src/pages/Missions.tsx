import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  Compass,
  FileText,
  Plus,
  Play,
  Search,
  ShieldAlert,
  RefreshCw,
  AlertOctagon,
  Inbox,
  Pause,
  CheckCircle2,
  X,
} from 'lucide-react';
import {
  listMissions,
  createMission,
  startMission,
  pauseMission,
  completeMission,
} from '../api/missions';
import type { Mission } from '../types/mission';

export default function Missions() {
  const navigate = useNavigate();
  const [missions, setMissions] = useState<Mission[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

  // New Mission Modal State
  const [isNewMissionModalOpen, setIsNewMissionModalOpen] = useState(false);
  const [selectedRobot, setSelectedRobot] = useState('ROV-01');
  const [selectedObjective, setSelectedObjective] = useState<'INSPECT' | 'INSPECT_AND_CLEAN' | 'INSPECT_SAMPLE'>('INSPECT');
  const [targetNotes, setTargetNotes] = useState('Sector 4B • Pipe MH-112 to MH-116');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const fetchMissions = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listMissions();
      setMissions(data);
    } catch (err: unknown) {
      console.error('Failed to load missions:', err);
      setError(err instanceof Error ? err.message : 'Unable to fetch mission list from PipeVision API server.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let isMounted = true;

    listMissions()
      .then((data) => {
        if (isMounted) {
          setMissions(data);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          console.error('Failed to load missions:', err);
          setError(err instanceof Error ? err.message : 'Unable to fetch mission list from PipeVision API server.');
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleCreateMission = async () => {
    setCreating(true);
    setCreateError(null);
    try {
      const newMission = await createMission({
        robot_id: selectedRobot,
        objective: selectedObjective,
        notes: targetNotes,
      });
      setMissions((prev) => [newMission, ...prev]);
      setIsNewMissionModalOpen(false);
      navigate(`/missions/${newMission.mission_id}/live`);
    } catch (err: unknown) {
      console.error('Failed to create mission:', err);
      setCreateError(err instanceof Error ? err.message : 'Failed to create mission.');
    } finally {
      setCreating(false);
    }
  };

  const handleAction = async (
    e: React.MouseEvent,
    missionId: string,
    action: 'start' | 'pause' | 'complete'
  ) => {
    e.stopPropagation();
    setActionLoadingId(missionId);
    setActionError(null);
    try {
      let updated: Mission;
      if (action === 'start') {
        updated = await startMission(missionId);
      } else if (action === 'pause') {
        updated = await pauseMission(missionId);
      } else {
        updated = await completeMission(missionId);
      }
      setMissions((prev) =>
        prev.map((m) => (m.mission_id === missionId ? updated : m))
      );
    } catch (err: unknown) {
      console.error(`Failed to ${action} mission:`, err);
      setActionError(err instanceof Error ? err.message : `Failed to ${action} mission.`);
    } finally {
      setActionLoadingId(null);
    }
  };

  const filteredMissions = missions.filter((m) => {
    const searchLower = searchTerm.toLowerCase();
    const matchesSearch =
      m.mission_id.toLowerCase().includes(searchLower) ||
      (m.location && m.location.toLowerCase().includes(searchLower)) ||
      (m.source && m.source.toLowerCase().includes(searchLower)) ||
      (m.robot_id && m.robot_id.toLowerCase().includes(searchLower));

    const matchesStatus =
      statusFilter === 'ALL' || m.status.toLowerCase() === statusFilter.toLowerCase();

    return matchesSearch && matchesStatus;
  });

  return (
    <div className="min-h-screen bg-[#0a1617] text-white p-4 sm:p-6 lg:p-8 font-['Inter'] selection:bg-[#a3e635] selection:text-black">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-[#183536]">
        <div>
          <div className="flex items-center gap-3">
            <Compass className="w-6 h-6 text-[#a3e635]" />
            <h1 className="font-['Poppins'] text-2xl sm:text-3xl font-black uppercase tracking-wider text-white">
              Mission Directory & Orchestration
            </h1>
          </div>
          <p className="text-[#649c96] text-xs sm:text-sm mt-1 font-['Space_Mono']">
            Autonomous Crawler Missions • Real FastAPI Backend • Inspection Log History
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchMissions}
            disabled={loading}
            className="p-2 rounded-lg bg-[#0e2425] hover:bg-[#153837] border border-[#1b3b3a] text-[#5de6ff] transition-all cursor-pointer disabled:opacity-50"
            title="Refresh Missions"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>

          <button
            onClick={() => {
              setCreateError(null);
              setIsNewMissionModalOpen(true);
            }}
            className="px-4 py-2 rounded-lg bg-[#a3e635] hover:bg-[#b6f059] text-black font-['Poppins'] font-bold text-xs sm:text-sm uppercase tracking-wider flex items-center gap-2 transition-all shadow-[0_0_15px_rgba(163,230,53,0.3)] cursor-pointer"
          >
            <Plus className="w-4 h-4 stroke-[3]" />
            <span>New Inspection Mission</span>
          </button>
        </div>
      </div>

      {/* Action Error Toast / Banner */}
      {actionError && (
        <div className="my-4 bg-[#1f0f11] border border-[#ff5449]/40 rounded-xl p-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <AlertOctagon className="w-5 h-5 text-[#ff5449] shrink-0" />
            <span className="font-['Space_Mono'] text-xs text-[#ff8c82]">{actionError}</span>
          </div>
          <button
            onClick={() => setActionError(null)}
            className="text-[#649c96] hover:text-white p-1"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 my-6">
        <div className="bg-[#0e2425]/90 border border-[#1b3b3a] p-4 rounded-xl">
          <div className="text-[#649c96] text-xs font-['Space_Mono'] uppercase">Total Missions</div>
          <div className="font-['Space_Mono'] text-xl sm:text-2xl font-black text-white mt-1">
            {missions.length}
          </div>
        </div>
        <div className="bg-[#0e2425]/90 border border-[#1b3b3a] p-4 rounded-xl">
          <div className="text-[#649c96] text-xs font-['Space_Mono'] uppercase">Active Inspections</div>
          <div className="font-['Space_Mono'] text-xl sm:text-2xl font-black text-[#a3e635] mt-1">
            {missions.filter((m) => m.status === 'active').length}
          </div>
        </div>
        <div className="bg-[#0e2425]/90 border border-[#1b3b3a] p-4 rounded-xl">
          <div className="text-[#649c96] text-xs font-['Space_Mono'] uppercase">Distance Surveyed</div>
          <div className="font-['Space_Mono'] text-xl sm:text-2xl font-black text-[#5de6ff] mt-1">
            {missions.reduce((acc, m) => acc + (m.distance_m || 0), 0).toFixed(1)} m
          </div>
        </div>
        <div className="bg-[#0e2425]/90 border border-[#1b3b3a] p-4 rounded-xl">
          <div className="text-[#649c96] text-xs font-['Space_Mono'] uppercase">Logged Defects</div>
          <div className="font-['Space_Mono'] text-xl sm:text-2xl font-black text-[#ff5449] mt-1">
            {missions.reduce((acc, m) => acc + (m.defectsCount || 0), 0)}
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-[#0e2425]/80 border border-[#1b3b3a] p-4 rounded-xl mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-[#649c96] absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search mission ID, location, or crawler source..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-[#071314] border border-[#173838] rounded-lg text-xs font-['Space_Mono'] text-white focus:outline-none focus:border-[#5de6ff]"
          />
        </div>

        {/* Status Filters */}
        <div className="flex flex-wrap items-center gap-2">
          {['ALL', 'ACTIVE', 'COMPLETED', 'PLANNED', 'PAUSED', 'FAILED'].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1.5 rounded-md text-xs font-['Space_Mono'] font-bold transition-all cursor-pointer ${
                statusFilter === st
                  ? 'bg-[#a3e635] text-black shadow-[0_0_10px_#a3e635]'
                  : 'bg-[#071314] text-[#649c96] hover:text-white border border-[#173838]'
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content Area: Loading / Error / Empty / Missions Grid */}
      {loading ? (
        <div className="bg-[#0e2425]/90 border border-[#1b3b3a] rounded-xl p-12 flex flex-col items-center justify-center gap-4 text-center">
          <RefreshCw className="w-8 h-8 text-[#5de6ff] animate-spin" />
          <div className="font-['Space_Mono'] text-sm text-[#5de6ff]">
            Fetching Mission Registry from PipeVision Backend...
          </div>
        </div>
      ) : error ? (
        <div className="bg-[#1f0f11] border border-[#ff5449]/40 rounded-xl p-8 flex flex-col items-center justify-center gap-4 text-center">
          <AlertOctagon className="w-10 h-10 text-[#ff5449]" />
          <div>
            <div className="font-['Poppins'] font-bold text-white text-base">
              Backend Connection Error
            </div>
            <div className="font-['Space_Mono'] text-xs text-[#ff8c82] mt-1 max-w-md">
              {error}
            </div>
          </div>
          <button
            onClick={fetchMissions}
            className="px-4 py-2 rounded-lg bg-[#ff5449]/20 hover:bg-[#ff5449]/30 border border-[#ff5449]/40 text-white font-['Space_Mono'] text-xs font-bold flex items-center gap-2 transition-all cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Retry Connection</span>
          </button>
        </div>
      ) : filteredMissions.length === 0 ? (
        <div className="bg-[#0e2425]/90 border border-[#1b3b3a] rounded-xl p-12 flex flex-col items-center justify-center gap-4 text-center">
          <Inbox className="w-12 h-12 text-[#649c96]" />
          <div>
            <div className="font-['Poppins'] font-bold text-white text-base">
              No Missions Found
            </div>
            <div className="font-['Space_Mono'] text-xs text-[#649c96] mt-1">
              {searchTerm || statusFilter !== 'ALL'
                ? 'No missions match your current filter parameters.'
                : 'No inspection missions have been created in the backend registry.'}
            </div>
          </div>
          {searchTerm || statusFilter !== 'ALL' ? (
            <button
              onClick={() => {
                setSearchTerm('');
                setStatusFilter('ALL');
              }}
              className="px-4 py-2 rounded bg-[#071314] border border-[#173838] text-[#5de6ff] text-xs font-['Space_Mono'] cursor-pointer"
            >
              Reset Filters
            </button>
          ) : (
            <button
              onClick={() => setIsNewMissionModalOpen(true)}
              className="px-4 py-2 rounded bg-[#a3e635] text-black font-['Poppins'] font-bold text-xs uppercase cursor-pointer"
            >
              Create First Mission
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredMissions.map((mission) => {
            const isActive = mission.status === 'active';
            const isCompleted = mission.status === 'completed';
            const isPlanned = mission.status === 'planned';
            const isPaused = mission.status === 'paused';
            const isActionLoading = actionLoadingId === mission.mission_id;

            return (
              <div
                key={mission.mission_id}
                className="bg-[#0e2425]/90 border border-[#1b3b3a] rounded-xl p-5 shadow-xl flex flex-col justify-between gap-4 hover:border-[#2a5754] transition-all"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-3">
                    <span className="font-['Space_Mono'] font-bold text-sm text-[#5de6ff]">
                      {mission.mission_id}
                    </span>
                    <span
                      className={`px-2.5 py-0.5 rounded text-[10px] font-['Space_Mono'] font-bold uppercase ${
                        isActive
                          ? 'bg-[#a3e635]/20 text-[#a3e635] border border-[#a3e635]/40 animate-pulse'
                          : isCompleted
                          ? 'bg-[#5de6ff]/20 text-[#5de6ff] border border-[#5de6ff]/40'
                          : isPlanned
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                          : isPaused
                          ? 'bg-orange-500/20 text-orange-300 border border-orange-500/40'
                          : 'bg-gray-500/20 text-gray-300'
                      }`}
                    >
                      {mission.status}
                    </span>
                  </div>

                  <div className="text-white font-['Poppins'] font-bold text-sm mb-1">
                    {mission.location || 'Sector 4B • Pipeline Survey'}
                  </div>

                  <div className="flex flex-col gap-1 text-xs font-['Space_Mono'] text-[#649c96] my-3">
                    <div className="flex items-center justify-between">
                      <span>Crawler ID:</span>
                      <span className="text-white">{mission.robot_id || mission.source || 'ROV-01'}</span>
                    </div>
                    {mission.objective && (
                      <div className="flex items-center justify-between">
                        <span>Objective:</span>
                        <span className="text-[#5de6ff]">{mission.objective}</span>
                      </div>
                    )}
                    <div className="flex items-center justify-between">
                      <span>Distance Covered:</span>
                      <span className="text-[#a3e635] font-bold">{mission.distance_m || 0} m</span>
                    </div>
                  </div>
                </div>

                {/* Lifecycle Actions */}
                <div className="flex items-center gap-2 pt-2 border-t border-[#183536]">
                  {isActive && (
                    <button
                      onClick={(e) => handleAction(e, mission.mission_id, 'pause')}
                      disabled={isActionLoading}
                      className="py-1 px-2.5 bg-orange-500/20 hover:bg-orange-500/30 border border-orange-500/40 text-orange-300 text-[11px] font-['Space_Mono'] rounded flex items-center gap-1 cursor-pointer disabled:opacity-50"
                    >
                      {isActionLoading ? (
                        <RefreshCw className="w-3 h-3 animate-spin" />
                      ) : (
                        <Pause className="w-3 h-3" />
                      )}
                      <span>Pause</span>
                    </button>
                  )}
                  {(isPlanned || isPaused) && (
                    <button
                      onClick={(e) => handleAction(e, mission.mission_id, 'start')}
                      disabled={isActionLoading}
                      className="py-1 px-2.5 bg-[#a3e635]/20 hover:bg-[#a3e635]/30 border border-[#a3e635]/40 text-[#a3e635] text-[11px] font-['Space_Mono'] rounded flex items-center gap-1 cursor-pointer disabled:opacity-50"
                    >
                      {isActionLoading ? (
                        <RefreshCw className="w-3 h-3 animate-spin" />
                      ) : (
                        <Play className="w-3 h-3 fill-current" />
                      )}
                      <span>Start</span>
                    </button>
                  )}
                  {isActive && (
                    <button
                      onClick={(e) => handleAction(e, mission.mission_id, 'complete')}
                      disabled={isActionLoading}
                      className="py-1 px-2.5 bg-[#5de6ff]/20 hover:bg-[#5de6ff]/30 border border-[#5de6ff]/40 text-[#5de6ff] text-[11px] font-['Space_Mono'] rounded flex items-center gap-1 cursor-pointer disabled:opacity-50"
                    >
                      {isActionLoading ? (
                        <RefreshCw className="w-3 h-3 animate-spin" />
                      ) : (
                        <CheckCircle2 className="w-3 h-3" />
                      )}
                      <span>Complete</span>
                    </button>
                  )}
                </div>

                {/* Action Navigation Buttons */}
                <div className="grid grid-cols-2 gap-2 pt-2 border-t border-[#183536]">
                  <button
                    onClick={() => navigate(`/missions/${mission.mission_id}/live`)}
                    className="py-1.5 px-3 bg-[#a3e635]/10 hover:bg-[#a3e635]/20 border border-[#a3e635]/30 text-[#ccff80] text-xs font-['Space_Mono'] rounded font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer"
                  >
                    <Play className="w-3 h-3 fill-current" />
                    <span>Cockpit</span>
                  </button>

                  <button
                    onClick={() => navigate(`/missions/${mission.mission_id}`)}
                    className="py-1.5 px-3 bg-[#5de6ff]/10 hover:bg-[#5de6ff]/20 border border-[#5de6ff]/30 text-[#5de6ff] text-xs font-['Space_Mono'] rounded font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer"
                  >
                    <Activity className="w-3 h-3" />
                    <span>Details</span>
                  </button>

                  <button
                    onClick={() => navigate(`/missions/${mission.mission_id}/findings`)}
                    className="py-1.5 px-3 bg-white/5 hover:bg-white/10 border border-white/10 text-white/80 text-xs font-['Space_Mono'] rounded transition-all flex items-center justify-center gap-1.5 cursor-pointer"
                  >
                    <ShieldAlert className="w-3 h-3 text-[#ff5449]" />
                    <span>Findings</span>
                  </button>

                  <button
                    onClick={() => navigate(`/reports/${mission.mission_id}`)}
                    className="py-1.5 px-3 bg-white/5 hover:bg-white/10 border border-white/10 text-white/80 text-xs font-['Space_Mono'] rounded transition-all flex items-center justify-center gap-1.5 cursor-pointer"
                  >
                    <FileText className="w-3 h-3 text-[#a3e635]" />
                    <span>Report</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* New Mission Modal */}
      {isNewMissionModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0e2425] border border-[#1b3b3a] rounded-xl p-6 max-w-md w-full flex flex-col gap-4 shadow-2xl animate-fade-in relative">
            <button
              onClick={() => setIsNewMissionModalOpen(false)}
              className="absolute top-4 right-4 text-[#649c96] hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="font-['Poppins'] text-lg font-bold text-white uppercase tracking-wider">
              Initialize New Inspection Mission
            </h3>

            {createError && (
              <div className="bg-[#1f0f11] border border-[#ff5449]/40 text-[#ff8c82] text-xs p-3 rounded font-['Space_Mono'] flex items-center gap-2">
                <AlertOctagon className="w-4 h-4 shrink-0 text-[#ff5449]" />
                <span>{createError}</span>
              </div>
            )}

            <div className="flex flex-col gap-3 text-xs font-['Space_Mono']">
              <div>
                <label className="text-[#649c96] block mb-1">Assigned Crawler / Robot</label>
                <select
                  value={selectedRobot}
                  onChange={(e) => setSelectedRobot(e.target.value)}
                  className="w-full bg-[#071314] border border-[#173838] rounded p-2 text-white font-['Space_Mono']"
                >
                  <option value="ROV-01">ROV-01 (Registered Autonomous Crawler)</option>
                  <option value="PV-TEST-001">PV-TEST-001 (Registered Test Unit)</option>
                  <option value="PV-SIM-001">PV-SIM-001 (Registered Simulation Unit)</option>
                  <option value="UNREGISTERED-BOT">UNREGISTERED-BOT (Test Error Handling)</option>
                </select>
              </div>

              <div>
                <label className="text-[#649c96] block mb-1">Mission Objective</label>
                <select
                  value={selectedObjective}
                  onChange={(e) => setSelectedObjective(e.target.value as 'INSPECT' | 'INSPECT_AND_CLEAN' | 'INSPECT_SAMPLE')}
                  className="w-full bg-[#071314] border border-[#173838] rounded p-2 text-white font-['Space_Mono']"
                >
                  <option value="INSPECT">INSPECT (Standard Defect Survey)</option>
                  <option value="INSPECT_AND_CLEAN">INSPECT_AND_CLEAN (High-Pressure Jetting)</option>
                  <option value="INSPECT_SAMPLE">INSPECT_SAMPLE (Quality Assessment)</option>
                </select>
              </div>

              <div>
                <label className="text-[#649c96] block mb-1">Pipe Segment Target / Notes</label>
                <input
                  type="text"
                  value={targetNotes}
                  onChange={(e) => setTargetNotes(e.target.value)}
                  placeholder="e.g. Sector 5A • Pipe DN500"
                  className="w-full bg-[#071314] border border-[#173838] rounded p-2 text-white font-['Space_Mono']"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-[#183536]">
              <button
                onClick={() => setIsNewMissionModalOpen(false)}
                disabled={creating}
                className="px-4 py-2 rounded bg-white/5 hover:bg-white/10 text-white text-xs font-['Space_Mono'] cursor-pointer disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateMission}
                disabled={creating}
                className="px-4 py-2 rounded bg-[#a3e635] hover:bg-[#b6f059] text-black font-['Poppins'] font-bold text-xs uppercase cursor-pointer flex items-center gap-2 disabled:opacity-50"
              >
                {creating ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin text-black" />
                    <span>Creating...</span>
                  </>
                ) : (
                  <span>Create Mission</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}