import React from 'react';
import { X, Download, Trash2, Camera, RefreshCw, AlertTriangle } from 'lucide-react';
import type { SnapshotRecord } from '../types/video';
import { getSnapshotImageUrl } from '../api/video';
import { sounds } from '../utils/audio';

interface SnapshotDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  missionId: string;
  snapshots: SnapshotRecord[];
  loading?: boolean;
  error?: string | null;
  onDeleteSnapshot: (snapshotId: string) => void;
  onRefreshSnapshots?: () => void;
}

export const SnapshotDrawer: React.FC<SnapshotDrawerProps> = ({
  isOpen,
  onClose,
  missionId,
  snapshots,
  loading = false,
  error = null,
  onDeleteSnapshot,
  onRefreshSnapshots,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm animate-fade-in">
      <div
        id="snapshot-drawer"
        className="w-full max-w-md bg-[#131416] h-full border-l border-white/10 p-6 flex flex-col gap-5 shadow-2xl overflow-y-auto"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/10 pb-4">
          <div className="flex items-center gap-2">
            <Camera className="w-5 h-5 text-[#5de6ff]" />
            <h3 className="font-['Poppins'] text-lg font-bold text-white">
              Inspection Snapshots
            </h3>
            <span className="px-2 py-0.5 rounded-full text-xs font-['Space_Mono'] bg-[#5de6ff]/20 text-[#5de6ff] border border-[#5de6ff]/40">
              {snapshots.length}
            </span>
          </div>

          <div className="flex items-center gap-2">
            {onRefreshSnapshots && (
              <button
                onClick={() => {
                  sounds.playClick('tactile');
                  onRefreshSnapshots();
                }}
                title="Refresh Snapshots"
                className="p-1.5 rounded-lg hover:bg-white/10 text-white/70 hover:text-white transition-colors"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-[#5de6ff]' : ''}`} />
              </button>
            )}
            <button
              onClick={() => {
                sounds.playClick('tactile');
                onClose();
              }}
              className="p-1.5 rounded-lg hover:bg-white/10 text-white/70 hover:text-white transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content State: Loading, Error, Empty, or List */}
        {loading && snapshots.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-8 text-white/50 font-['Space_Mono'] gap-3">
            <RefreshCw className="w-8 h-8 text-[#5de6ff] animate-spin" />
            <p className="text-sm font-bold">Loading Backend Snapshots...</p>
          </div>
        ) : error ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-8 text-[#ff8c82] font-['Space_Mono'] gap-3">
            <AlertTriangle className="w-10 h-10 text-[#ff5449]" />
            <p className="text-sm font-bold">Failed to load snapshots</p>
            <p className="text-xs text-white/40">{error}</p>
            {onRefreshSnapshots && (
              <button
                onClick={onRefreshSnapshots}
                className="px-3 py-1.5 rounded bg-[#ff5449]/20 border border-[#ff5449]/40 text-white text-xs font-bold mt-2"
              >
                Retry Fetch
              </button>
            )}
          </div>
        ) : snapshots.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-8 text-white/40 font-['Space_Mono']">
            <Camera className="w-12 h-12 mb-3 opacity-30 text-[#ccff80]" />
            <p className="text-sm font-bold text-white/70">No inspection snapshots captured yet.</p>
            <p className="text-xs text-white/40 mt-1">
              Press the Reticle button or 'S' key on camera HUD to capture persistent backend frame snapshots.
            </p>
          </div>
        ) : (
          <div className="flex-1 flex flex-col gap-4 overflow-y-auto">
            {snapshots.map((item) => {
              const imageUrl = item.image_url.startsWith('http')
                ? item.image_url
                : getSnapshotImageUrl(missionId, item.snapshot_id);

              const formattedTime = item.timestamp
                ? new Date(item.timestamp).toLocaleTimeString('en-US', { hour12: false })
                : new Date(item.created_at).toLocaleTimeString('en-US', { hour12: false });

              return (
                <div
                  key={item.snapshot_id}
                  className="glass-panel rounded-xl p-3 border border-white/10 flex flex-col gap-2.5 hover:border-[#a3e635]/40 transition-colors"
                >
                  <div className="relative rounded-lg overflow-hidden h-36 bg-black">
                    <img
                      src={imageUrl}
                      alt={`Snapshot ${item.snapshot_id}`}
                      className="w-full h-full object-cover"
                    />
                    <div className="absolute top-2 left-2 bg-black/80 backdrop-blur px-2 py-0.5 rounded text-[10px] font-['Space_Mono'] text-[#ccff80]">
                      {item.camera_id ? item.camera_id.toUpperCase() : 'CAM 01'}
                    </div>
                    <div className="absolute bottom-2 right-2 bg-black/80 backdrop-blur px-2 py-0.5 rounded text-[10px] font-['Space_Mono'] text-white">
                      FRAME #{item.frame_index}
                    </div>
                    {item.distance_m !== null && item.distance_m !== undefined && (
                      <div className="absolute top-2 right-2 bg-black/80 backdrop-blur px-2 py-0.5 rounded text-[10px] font-['Space_Mono'] text-[#5de6ff]">
                        {item.distance_m.toFixed(1)}m
                      </div>
                    )}
                  </div>

                  <div className="flex items-center justify-between text-xs font-['Space_Mono'] text-white/70">
                    <span className="text-white font-bold">{item.snapshot_id}</span>
                    <span>{formattedTime}</span>
                  </div>

                  {item.notes && (
                    <div className="text-[11px] font-['Space_Mono'] text-[#649c96] italic bg-black/30 p-1.5 rounded border border-white/5">
                      "{item.notes}"
                    </div>
                  )}

                  <div className="flex items-center gap-2 pt-1 border-t border-white/10">
                    <a
                      href={imageUrl}
                      download={`pipevision_${item.snapshot_id}.jpg`}
                      className="flex-1 py-1.5 px-3 rounded-lg bg-white/5 hover:bg-[#a3e635]/20 hover:text-[#ccff80] border border-white/10 text-xs font-['Space_Mono'] flex items-center justify-center gap-1.5 transition-colors"
                    >
                      <Download className="w-3.5 h-3.5" />
                      <span>Download</span>
                    </a>
                    <button
                      onClick={() => {
                        sounds.playClick('tactile');
                        onDeleteSnapshot(item.snapshot_id);
                      }}
                      className="p-1.5 rounded-lg bg-white/5 hover:bg-[#ff5449]/20 hover:text-[#ffb4ab] border border-white/10 transition-colors"
                      title="Delete snapshot"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
