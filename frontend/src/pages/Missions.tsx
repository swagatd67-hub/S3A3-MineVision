import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  Compass,
  FileText,
  Plus,
  Play,
  Search,
  ShieldAlert,
} from 'lucide-react';
import { mockMissions } from '../mocks/missions';
import type { Mission } from '../types/mission';

// Augmented mock missions for display
const EXTENDED_MISSIONS: (Mission & { location: string; defectsCount: number })[] = [
  {
    mission_id: 'M-104',
    status: 'active',
    source: 'ROV-01 (Tactical)',
    created_at: '2026-08-29T08:15:00Z',
    started_at: '2026-08-29T08:20:00Z',
    distance_m: 142.8,
    location: 'Sector 4B • Pipe MH-112 to MH-116',
    defectsCount: 4,
  },
  ...mockMissions.map((m, idx) => ({
    ...m,
    location: idx === 0 ? 'Sector 2A • Main Trunk' : idx === 1 ? 'Sector 1C • Outfall' : 'Sector 3D • Lateral',
    defectsCount: idx === 0 ? 3 : idx === 1 ? 5 : 0,
  })),
  {
    mission_id: 'PV-2026-001',
    status: 'completed',
    source: 'Crawler-02',
    created_at: '2026-08-26T10:00:00Z',
    started_at: '2026-08-26T10:10:00Z',
    completed_at: '2026-08-26T11:45:00Z',
    distance_m: 310.5,
    location: 'Downtown Grid • Pipe DN600',
    defectsCount: 8,
  },
];

export default function Missions() {
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [isNewMissionModalOpen, setIsNewMissionModalOpen] = useState(false);
  const [newMissionId, setNewMissionId] = useState('M-NEW-2026');

  const filteredMissions = EXTENDED_MISSIONS.filter((m) => {
    const matchesSearch =
      m.mission_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      m.location.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (m.source && m.source.toLowerCase().includes(searchTerm.toLowerCase()));

    const matchesStatus = statusFilter === 'ALL' || m.status.toLowerCase() === statusFilter.toLowerCase();

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
            Autonomous Crawler Missions • Offline Video Runs • Inspection Log History
          </p>
        </div>

        <button
          onClick={() => setIsNewMissionModalOpen(true)}
          className="px-4 py-2 rounded-lg bg-[#a3e635] hover:bg-[#b6f059] text-black font-['Poppins'] font-bold text-xs sm:text-sm uppercase tracking-wider flex items-center gap-2 transition-all shadow-[0_0_15px_rgba(163,230,53,0.3)] cursor-pointer"
        >
          <Plus className="w-4 h-4 stroke-[3]" />
          <span>New Inspection Mission</span>
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 my-6">
        <div className="bg-[#0e2425]/90 border border-[#1b3b3a] p-4 rounded-xl">
          <div className="text-[#649c96] text-xs font-['Space_Mono'] uppercase">Total Missions</div>
          <div className="font-['Space_Mono'] text-xl sm:text-2xl font-black text-white mt-1">
            {EXTENDED_MISSIONS.length}
          </div>
        </div>
        <div className="bg-[#0e2425]/90 border border-[#1b3b3a] p-4 rounded-xl">
          <div className="text-[#649c96] text-xs font-['Space_Mono'] uppercase">Active Inspections</div>
          <div className="font-['Space_Mono'] text-xl sm:text-2xl font-black text-[#a3e635] mt-1">
            {EXTENDED_MISSIONS.filter((m) => m.status === 'active').length}
          </div>
        </div>
        <div className="bg-[#0e2425]/90 border border-[#1b3b3a] p-4 rounded-xl">
          <div className="text-[#649c96] text-xs font-['Space_Mono'] uppercase">Distance Surveyed</div>
          <div className="font-['Space_Mono'] text-xl sm:text-2xl font-black text-[#5de6ff] mt-1">
            {EXTENDED_MISSIONS.reduce((acc, m) => acc + (m.distance_m || 0), 0).toFixed(1)} m
          </div>
        </div>
        <div className="bg-[#0e2425]/90 border border-[#1b3b3a] p-4 rounded-xl">
          <div className="text-[#649c96] text-xs font-['Space_Mono'] uppercase">Logged Defects</div>
          <div className="font-['Space_Mono'] text-xl sm:text-2xl font-black text-[#ff5449] mt-1">
            {EXTENDED_MISSIONS.reduce((acc, m) => acc + m.defectsCount, 0)}
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
          {['ALL', 'ACTIVE', 'COMPLETED', 'PLANNED', 'PAUSED'].map((st) => (
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

      {/* Missions Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredMissions.map((mission) => {
          const isActive = mission.status === 'active';
          const isCompleted = mission.status === 'completed';
          const isPlanned = mission.status === 'planned';

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
                        : 'bg-gray-500/20 text-gray-300'
                    }`}
                  >
                    {mission.status}
                  </span>
                </div>

                <div className="text-white font-['Poppins'] font-bold text-sm mb-1">
                  {mission.location}
                </div>

                <div className="flex flex-col gap-1 text-xs font-['Space_Mono'] text-[#649c96] my-3">
                  <div className="flex items-center justify-between">
                    <span>Source:</span>
                    <span className="text-white">{mission.source || 'ROV-01'}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Distance Covered:</span>
                    <span className="text-[#a3e635] font-bold">{mission.distance_m || 0} m</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Detections Logged:</span>
                    <span className="text-[#ff5449] font-bold">{mission.defectsCount} defects</span>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="grid grid-cols-2 gap-2 pt-3 border-t border-[#183536]">
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

      {/* New Mission Modal */}
      {isNewMissionModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0e2425] border border-[#1b3b3a] rounded-xl p-6 max-w-md w-full flex flex-col gap-4 shadow-2xl animate-fade-in">
            <h3 className="font-['Poppins'] text-lg font-bold text-white uppercase tracking-wider">
              Initialize New Inspection Mission
            </h3>
            <div className="flex flex-col gap-3 text-xs font-['Space_Mono']">
              <div>
                <label className="text-[#649c96] block mb-1">Mission Identifier</label>
                <input
                  type="text"
                  value={newMissionId}
                  onChange={(e) => setNewMissionId(e.target.value)}
                  className="w-full bg-[#071314] border border-[#173838] rounded p-2 text-white font-['Space_Mono']"
                />
              </div>
              <div>
                <label className="text-[#649c96] block mb-1">Pipe Segment Target</label>
                <input
                  type="text"
                  defaultValue="Sector 5A • Pipe DN500"
                  className="w-full bg-[#071314] border border-[#173838] rounded p-2 text-white font-['Space_Mono']"
                />
              </div>
              <div>
                <label className="text-[#649c96] block mb-1">Assigned Crawler</label>
                <select className="w-full bg-[#071314] border border-[#173838] rounded p-2 text-white font-['Space_Mono']">
                  <option>ROV-01 (Tactical Autonomous Crawler)</option>
                  <option>Crawler-02 (Heavy Jetting Unit)</option>
                  <option>Offline Video Ingestion Gateway</option>
                </select>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-[#183536]">
              <button
                onClick={() => setIsNewMissionModalOpen(false)}
                className="px-4 py-2 rounded bg-white/5 hover:bg-white/10 text-white text-xs font-['Space_Mono'] cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setIsNewMissionModalOpen(false);
                  navigate(`/missions/${newMissionId}/live`);
                }}
                className="px-4 py-2 rounded bg-[#a3e635] text-black font-['Poppins'] font-bold text-xs uppercase cursor-pointer"
              >
                Start Mission
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}