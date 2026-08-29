import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  AlertOctagon,
  ArrowLeft,
  Eye,
  FileText,
  MessageSquare,
  RefreshCw,
  Search,
  ShieldAlert,
  X,
} from 'lucide-react';
import { getMissionObservations, normalizeObservation } from '../api/findings';
import type { BackendObservationsResponse, ExtendedFinding } from '../types/finding';

export default function Findings() {
  const { missionId = 'M-104' } = useParams<{ missionId: string }>();
  const navigate = useNavigate();

  const [observationsResponse, setObservationsResponse] =
    useState<BackendObservationsResponse | null>(null);
  const [findingsList, setFindingsList] = useState<ExtendedFinding[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [searchTerm, setSearchTerm] = useState('');
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');

  // Note Modal state
  const [activeFindingForNote, setActiveFindingForNote] = useState<ExtendedFinding | null>(null);
  const [newNoteText, setNewNoteText] = useState('');

  // Broken image fallback state for frame URLs
  const [failedImageUrls, setFailedImageUrls] = useState<Record<string, boolean>>({});

  const fetchObservations = (targetMissionId: string) => {
    setLoading(true);
    setError(null);

    getMissionObservations(targetMissionId)
      .then((res) => {
        setObservationsResponse(res);
        const normalized = res.observations.map((obs, idx) => {
          return normalizeObservation(obs, idx, targetMissionId, 'UNRESOLVED', []);
        });
        setFindingsList(normalized);
        setLoading(false);
      })
      .catch((err) => {
        console.error(`Failed to fetch observations for ${targetMissionId}:`, err);
        setError(
          `Observations for mission '${targetMissionId}' could not be loaded from PipeVision API server.`
        );
        setLoading(false);
      });
  };

  useEffect(() => {
    let isMounted = true;

    getMissionObservations(missionId)
      .then((res) => {
        if (!isMounted) return;
        setObservationsResponse(res);
        const normalized = res.observations.map((obs, idx) => {
          return normalizeObservation(obs, idx, missionId, 'UNRESOLVED', []);
        });
        setFindingsList(normalized);
        setError(null);
        setLoading(false);
      })
      .catch((err) => {
        if (!isMounted) return;
        console.error(`Failed to fetch observations for ${missionId}:`, err);
        setError(
          `Observations for mission '${missionId}' could not be loaded from PipeVision API server.`
        );
        setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [missionId]);

  const filteredFindings = findingsList.filter((f) => {
    const matchesSearch =
      f.defect.toLowerCase().includes(searchTerm.toLowerCase()) ||
      f.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      f.class_code.toLowerCase().includes(searchTerm.toLowerCase()) ||
      f.mission_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      String(f.frame_index).includes(searchTerm);

    const matchesSeverity =
      severityFilter === 'ALL' || f.severity.toLowerCase() === severityFilter.toLowerCase();

    return matchesSearch && matchesSeverity;
  });

  const toggleFindingStatus = (id: string) => {
    setFindingsList((prev) =>
      prev.map((item) => {
        if (item.id === id) {
          const nextStatus = item.status === 'RESOLVED' ? 'UNRESOLVED' : 'RESOLVED';
          return { ...item, status: nextStatus };
        }
        return item;
      })
    );
  };

  const handleAddNote = () => {
    if (!activeFindingForNote || !newNoteText.trim()) return;
    const id = activeFindingForNote.id;
    const note = newNoteText.trim();

    setFindingsList((prev) =>
      prev.map((item) => {
        if (item.id === id) {
          return { ...item, notes: [...item.notes, note] };
        }
        return item;
      })
    );
    setNewNoteText('');
    setActiveFindingForNote(null);
  };

  const handleImageError = (id: string) => {
    setFailedImageUrls((prev) => ({ ...prev, [id]: true }));
  };

  return (
    <div className="min-h-screen bg-[#0a1617] text-white p-4 sm:p-6 lg:p-8 font-['Inter'] selection:bg-[#a3e635] selection:text-black">
      {/* Header Banner */}
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
              <ShieldAlert className="w-6 h-6 text-[#ff5449]" />
              <h1 className="font-['Poppins'] text-2xl sm:text-3xl font-black uppercase tracking-wider text-white">
                Defect Detection & Analysis Browser
              </h1>
            </div>
            <p className="text-[#649c96] text-xs sm:text-sm mt-1 font-['Space_Mono']">
              AI Vision Detections • Sewer-ML Classifications • Bounding Boxes • Mission {missionId}
            </p>
          </div>
        </div>

        <button
          onClick={() => navigate(`/reports/${missionId}`)}
          className="px-4 py-2 rounded-lg bg-[#a3e635] hover:bg-[#b6f059] text-black font-['Poppins'] font-bold text-xs sm:text-sm uppercase tracking-wider flex items-center gap-2 transition-all shadow-[0_0_15px_rgba(163,230,53,0.3)] cursor-pointer"
        >
          <FileText className="w-4 h-4" />
          <span>Export Findings Report</span>
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 my-6">
        <div className="bg-[#0e2425]/90 border border-[#1b3b3a] p-4 rounded-xl">
          <div className="text-[#649c96] text-xs font-['Space_Mono'] uppercase">Total Defects</div>
          <div className="font-['Space_Mono'] text-2xl font-black text-white mt-1">
            {observationsResponse ? observationsResponse.count : findingsList.length}
          </div>
        </div>

        <div className="bg-[#0e2425]/90 border border-[#1b3b3a] p-4 rounded-xl">
          <div className="text-[#649c96] text-xs font-['Space_Mono'] uppercase">Critical Severity</div>
          <div className="font-['Space_Mono'] text-2xl font-black text-[#ff5449] mt-1">
            {findingsList.filter((f) => f.severity === 'critical').length}
          </div>
        </div>

        <div className="bg-[#0e2425]/90 border border-[#1b3b3a] p-4 rounded-xl">
          <div className="text-[#649c96] text-xs font-['Space_Mono'] uppercase">High Severity</div>
          <div className="font-['Space_Mono'] text-2xl font-black text-[#ffb4ab] mt-1">
            {findingsList.filter((f) => f.severity === 'high').length}
          </div>
        </div>

        <div className="bg-[#0e2425]/90 border border-[#1b3b3a] p-4 rounded-xl">
          <div className="text-[#649c96] text-xs font-['Space_Mono'] uppercase">Resolved Findings</div>
          <div className="font-['Space_Mono'] text-2xl font-black text-[#a3e635] mt-1">
            {findingsList.filter((f) => f.status === 'RESOLVED').length}
          </div>
        </div>
      </div>

      {/* Filters and Search Bar */}
      <div className="bg-[#0e2425]/80 border border-[#1b3b3a] p-4 rounded-xl mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-[#649c96] absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search defect type, class code, frame ID, or mission..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-[#071314] border border-[#173838] rounded-lg text-xs font-['Space_Mono'] text-white focus:outline-none focus:border-[#5de6ff]"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-['Space_Mono'] text-[#649c96] mr-1">Severity:</span>
          {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((sev) => (
            <button
              key={sev}
              onClick={() => setSeverityFilter(sev)}
              className={`px-2.5 py-1 rounded text-xs font-['Space_Mono'] font-bold transition-all cursor-pointer ${
                severityFilter === sev
                  ? 'bg-[#a3e635] text-black shadow-[0_0_10px_#a3e635]'
                  : 'bg-[#071314] text-[#649c96] hover:text-white border border-[#173838]'
              }`}
            >
              {sev}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content Area: Loading, Error, Empty, or Findings Grid */}
      {loading ? (
        <div className="my-12 bg-[#0e2425]/90 border border-[#1b3b3a] rounded-xl p-12 flex flex-col items-center justify-center gap-4 text-center">
          <RefreshCw className="w-8 h-8 text-[#5de6ff] animate-spin" />
          <div>
            <div className="font-['Poppins'] font-bold text-white text-base">
              Fetching Inspection Observations from API...
            </div>
            <div className="font-['Space_Mono'] text-xs text-[#649c96] mt-1">
              GET /api/v1/missions/{missionId}/observations
            </div>
          </div>
        </div>
      ) : error ? (
        <div className="my-12 bg-[#1f0f11] border border-[#ff5449]/40 rounded-xl p-8 flex flex-col items-center justify-center gap-4 text-center">
          <AlertOctagon className="w-10 h-10 text-[#ff5449]" />
          <div>
            <div className="font-['Poppins'] font-bold text-white text-base">
              Backend Observation Integration Error
            </div>
            <div className="font-['Space_Mono'] text-xs text-[#ff8c82] mt-1 max-w-md">
              {error}
            </div>
          </div>
          <button
            onClick={() => fetchObservations(missionId)}
            className="px-4 py-2 rounded-lg bg-[#ff5449]/20 hover:bg-[#ff5449]/30 border border-[#ff5449]/40 text-white font-['Space_Mono'] text-xs font-bold flex items-center gap-2 transition-all cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Retry Observations Fetch</span>
          </button>
        </div>
      ) : findingsList.length === 0 ? (
        <div className="my-12 bg-[#0e2425]/90 border border-[#1b3b3a] rounded-xl p-12 flex flex-col items-center justify-center gap-4 text-center">
          <ShieldAlert className="w-10 h-10 text-[#649c96]" />
          <div>
            <div className="font-['Poppins'] font-bold text-white text-base uppercase tracking-wider">
              No Observations Found
            </div>
            <div className="font-['Space_Mono'] text-xs text-[#649c96] mt-1">
              Mission '{missionId}' contains 0 registered defect observations in backend database.
            </div>
          </div>
        </div>
      ) : (
        /* Findings Cards List */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredFindings.map((finding) => {
            const isCritical = finding.severity === 'critical';
            const isHigh = finding.severity === 'high';
            const isResolved = finding.status === 'RESOLVED';
            const hasImageError = failedImageUrls[finding.id];

            return (
              <div
                key={finding.id}
                className="bg-[#0e2425]/90 border border-[#1b3b3a] rounded-xl p-5 shadow-xl flex flex-col justify-between gap-4 hover:border-[#2a5754] transition-all"
              >
                <div>
                  {/* Defect Frame / Bounding Box Thumbnail */}
                  <div className="w-full h-40 bg-[#061011] rounded-lg border border-[#173838] relative overflow-hidden mb-4 flex items-center justify-center p-2">
                    <div className="absolute inset-0 opacity-20 bg-[radial-gradient(#5de6ff_1px,transparent_1px)] [background-size:16px_16px]" />

                    {finding.image_url && !hasImageError ? (
                      <img
                        src={finding.image_url}
                        alt={`Frame #${finding.frame_index} for ${finding.defect}`}
                        onError={() => handleImageError(finding.id)}
                        className="w-full h-full object-cover rounded relative z-10"
                      />
                    ) : (
                      /* Fallback Camera Frame Defect Bounding Box Canvas */
                      <div className="w-32 h-24 border-2 border-dashed border-[#ff5449] rounded relative flex items-center justify-center bg-[#ff5449]/10">
                        <span className="text-[10px] font-['Space_Mono'] font-bold text-[#ff8c82] bg-black/80 px-1.5 py-0.5 rounded absolute -top-3 left-2">
                          {finding.defect} ({(finding.confidence * 100).toFixed(0)}%)
                        </span>
                      </div>
                    )}

                    <span className="absolute bottom-2 right-2 text-[10px] font-['Space_Mono'] text-[#649c96] bg-black/80 px-2 py-0.5 rounded z-20">
                      Chainage: {finding.distance_m}m
                    </span>
                  </div>

                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="font-['Space_Mono'] font-bold text-xs text-[#5de6ff]">
                      {finding.id} • Frame #{finding.frame_index}
                    </span>
                    <span
                      className={`px-2.5 py-0.5 rounded text-[10px] font-['Space_Mono'] font-bold uppercase ${
                        isCritical
                          ? 'bg-[#ff5449]/20 text-[#ff8c82] border border-[#ff5449]/40'
                          : isHigh
                          ? 'bg-[#ffb4ab]/20 text-[#ffc0b8] border border-[#ffb4ab]/40'
                          : 'bg-[#5de6ff]/20 text-[#5de6ff] border border-[#5de6ff]/40'
                      }`}
                    >
                      {finding.severity}
                    </span>
                  </div>

                  <h3 className="font-['Poppins'] font-bold text-base text-white mb-1">
                    {finding.defect}
                  </h3>
                  <div className="text-[11px] font-['Space_Mono'] text-[#649c96] mb-2">
                    Class Code: <span className="text-[#5de6ff] font-bold">{finding.class_code}</span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs font-['Space_Mono'] text-[#649c96] my-2">
                    <div>
                      Clock Pos: <strong className="text-white">{finding.clockPosition}</strong>
                    </div>
                    <div>
                      Confidence: <strong className="text-[#a3e635]">{(finding.confidence * 100).toFixed(1)}%</strong>
                    </div>
                  </div>

                  {/* Notes list */}
                  {finding.notes.length > 0 && (
                    <div className="mt-3 p-2.5 rounded bg-[#071314] border border-[#173838] text-xs font-['Space_Mono'] text-[#649c96] flex flex-col gap-1">
                      <span className="text-[10px] text-[#5de6ff] font-bold uppercase">Engineering Notes:</span>
                      {finding.notes.map((note, i) => (
                        <p key={i} className="text-white italic">
                          "{note}"
                        </p>
                      ))}
                    </div>
                  )}
                </div>

                {/* Action Toolbar */}
                <div className="flex items-center gap-2 pt-3 border-t border-[#183536]">
                  <button
                    onClick={() => toggleFindingStatus(finding.id)}
                    className={`flex-1 py-1.5 rounded text-xs font-['Space_Mono'] font-bold transition-all cursor-pointer ${
                      isResolved
                        ? 'bg-[#a3e635]/20 text-[#a3e635] border border-[#a3e635]/40'
                        : 'bg-white/5 hover:bg-white/10 text-white border border-white/10'
                    }`}
                  >
                    {isResolved ? '✓ Resolved' : 'Mark Resolved'}
                  </button>

                  <button
                    onClick={() => setActiveFindingForNote(finding)}
                    className="p-2 rounded bg-[#0e2425] hover:bg-[#153837] border border-[#1b3b3a] text-[#5de6ff] cursor-pointer"
                    title="Add Engineering Note"
                  >
                    <MessageSquare className="w-4 h-4" />
                  </button>

                  <button
                    onClick={() => navigate(`/missions/${finding.mission_id}`)}
                    className="p-2 rounded bg-[#0e2425] hover:bg-[#153837] border border-[#1b3b3a] text-[#a3e635] cursor-pointer"
                    title="View in 3D Digital Twin"
                  >
                    <Eye className="w-4 h-4" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Engineering Note Modal */}
      {activeFindingForNote && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0e2425] border border-[#1b3b3a] rounded-xl p-6 max-w-md w-full flex flex-col gap-4 shadow-2xl animate-fade-in">
            <div className="flex items-center justify-between">
              <h3 className="font-['Poppins'] text-base font-bold text-white uppercase tracking-wider">
                Add Engineering Note • {activeFindingForNote.id}
              </h3>
              <button
                onClick={() => setActiveFindingForNote(null)}
                className="text-[#649c96] hover:text-white cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <textarea
              rows={4}
              placeholder="Enter field observation or remediation instructions..."
              value={newNoteText}
              onChange={(e) => setNewNoteText(e.target.value)}
              className="w-full bg-[#071314] border border-[#173838] rounded-lg p-3 text-xs font-['Space_Mono'] text-white focus:outline-none focus:border-[#5de6ff]"
            />

            <div className="flex justify-end gap-2">
              <button
                onClick={() => setActiveFindingForNote(null)}
                className="px-4 py-2 rounded bg-white/5 text-white text-xs font-['Space_Mono'] cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleAddNote}
                className="px-4 py-2 rounded bg-[#5de6ff] text-[#001f25] font-['Poppins'] font-bold text-xs uppercase cursor-pointer"
              >
                Save Note
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}