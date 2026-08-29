import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Eye,
  FileText,
  MessageSquare,
  Search,
  ShieldAlert,
  X,
} from 'lucide-react';
import { mockFindings } from '../mocks/findings';
import type { FindingSeverity } from '../types/finding';

interface ExtendedFinding {
  id: string;
  mission_id: string;
  frame_index: number;
  timestamp: string;
  distance_m: number;
  defect: string;
  confidence: number;
  severity: FindingSeverity;
  status: 'UNRESOLVED' | 'IN_REVIEW' | 'RESOLVED';
  clockPosition: string;
  notes: string[];
}

const EXTENDED_FINDINGS: ExtendedFinding[] = [
  ...mockFindings.map((f, idx) => ({
    id: `FIND-${101 + idx}`,
    mission_id: f.mission_id,
    frame_index: f.frame_index,
    timestamp: f.timestamp,
    distance_m: f.distance_m,
    defect: f.defect,
    confidence: f.confidence,
    severity: (f.severity || 'high') as FindingSeverity,
    status: (idx === 0 ? 'UNRESOLVED' : idx === 1 ? 'IN_REVIEW' : 'RESOLVED') as 'UNRESOLVED' | 'IN_REVIEW' | 'RESOLVED',
    clockPosition: idx === 0 ? '12:00' : idx === 1 ? '03:00' : '06:00',
    notes: idx === 0 ? ['Severe longitudinal crack extending 1.2 meters. High jetting pressure required.'] : [],
  })),
  {
    id: 'FIND-104',
    mission_id: 'M-DAY5-DEMO',
    frame_index: 580,
    timestamp: '2026-08-18T11:49:15.000Z',
    distance_m: 45.2,
    defect: 'Pipe Deformation',
    confidence: 0.87,
    severity: 'critical',
    status: 'UNRESOLVED',
    clockPosition: '09:00',
    notes: ['Ovality deformation detected exceeding 5% threshold.'],
  },
  {
    id: 'FIND-105',
    mission_id: 'M-DAY5-DEMO',
    frame_index: 612,
    timestamp: '2026-08-18T11:49:40.000Z',
    distance_m: 54.8,
    defect: 'Silt Deposit Accumulation',
    confidence: 0.95,
    severity: 'medium',
    status: 'RESOLVED',
    clockPosition: '06:00',
    notes: ['Cleared during jetting cycle.'],
  },
];

export default function Findings() {
  const { missionId = 'M-DAY5-DEMO' } = useParams<{ missionId: string }>();
  const navigate = useNavigate();

  const [findingsList, setFindingsList] = useState<ExtendedFinding[]>(EXTENDED_FINDINGS);
  const [searchTerm, setSearchTerm] = useState('');
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');

  // Note Modal state
  const [activeFindingForNote, setActiveFindingForNote] = useState<ExtendedFinding | null>(null);
  const [newNoteText, setNewNoteText] = useState('');

  const filteredFindings = findingsList.filter((f) => {
    const matchesSearch =
      f.defect.toLowerCase().includes(searchTerm.toLowerCase()) ||
      f.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      f.mission_id.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesSeverity = severityFilter === 'ALL' || f.severity.toLowerCase() === severityFilter.toLowerCase();

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
    setFindingsList((prev) =>
      prev.map((item) => {
        if (item.id === activeFindingForNote.id) {
          return { ...item, notes: [...item.notes, newNoteText.trim()] };
        }
        return item;
      })
    );
    setNewNoteText('');
    setActiveFindingForNote(null);
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
              AI Vision Detections • Bounding Boxes • Severity Classification • Mission {missionId}
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
            {findingsList.length}
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
            placeholder="Search defect type, frame ID, or mission..."
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
                  ? 'bg-[#5de6ff] text-[#001f25]'
                  : 'bg-[#071314] text-[#649c96] hover:text-white border border-[#173838]'
              }`}
            >
              {sev}
            </button>
          ))}
        </div>
      </div>

      {/* Findings Cards List */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredFindings.map((finding) => {
          const isCritical = finding.severity === 'critical';
          const isHigh = finding.severity === 'high';
          const isResolved = finding.status === 'RESOLVED';

          return (
            <div
              key={finding.id}
              className="bg-[#0e2425]/90 border border-[#1b3b3a] rounded-xl p-5 shadow-xl flex flex-col justify-between gap-4 hover:border-[#2a5754] transition-all"
            >
              <div>
                {/* Defect Bounding Box Thumbnail */}
                <div className="w-full h-40 bg-[#061011] rounded-lg border border-[#173838] relative overflow-hidden mb-4 flex items-center justify-center p-2">
                  <div className="absolute inset-0 opacity-20 bg-[radial-gradient(#5de6ff_1px,transparent_1px)] [background-size:16px_16px]" />

                  {/* Mock Camera Frame Defect Bounding Box */}
                  <div className="w-32 h-24 border-2 border-dashed border-[#ff5449] rounded relative flex items-center justify-center bg-[#ff5449]/10">
                    <span className="text-[10px] font-['Space_Mono'] font-bold text-[#ff8c82] bg-black/80 px-1.5 py-0.5 rounded absolute -top-3 left-2">
                      {finding.defect} ({ (finding.confidence * 100).toFixed(0) }%)
                    </span>
                  </div>

                  <span className="absolute bottom-2 right-2 text-[10px] font-['Space_Mono'] text-[#649c96] bg-black/80 px-2 py-0.5 rounded">
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

                <h3 className="font-['Poppins'] font-bold text-base text-white mb-2">
                  {finding.defect}
                </h3>

                <div className="grid grid-cols-2 gap-2 text-xs font-['Space_Mono'] text-[#649c96] my-2">
                  <div>Clock Pos: <strong className="text-white">{finding.clockPosition}</strong></div>
                  <div>Confidence: <strong className="text-[#a3e635]">{(finding.confidence * 100).toFixed(1)}%</strong></div>
                </div>

                {/* Notes list */}
                {finding.notes.length > 0 && (
                  <div className="mt-3 p-2.5 rounded bg-[#071314] border border-[#173838] text-xs font-['Space_Mono'] text-[#649c96] flex flex-col gap-1">
                    <span className="text-[10px] text-[#5de6ff] font-bold uppercase">Engineering Notes:</span>
                    {finding.notes.map((note, i) => (
                      <p key={i} className="text-white italic">"{note}"</p>
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

      {/* Engineering Note Modal */}
      {activeFindingForNote && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0e2425] border border-[#1b3b3a] rounded-xl p-6 max-w-md w-full flex flex-col gap-4 shadow-2xl animate-fade-in">
            <div className="flex items-center justify-between">
              <h3 className="font-['Poppins'] text-base font-bold text-white uppercase tracking-wider">
                Add Engineering Note • {activeFindingForNote.id}
              </h3>
              <button onClick={() => setActiveFindingForNote(null)} className="text-[#649c96] hover:text-white cursor-pointer">
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