import { X, Download, Trash2, Camera } from 'lucide-react';
import type { SnapshotItem } from '../types';
import { sounds } from '../utils/audio';

interface SnapshotDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  snapshots: SnapshotItem[];
  onDeleteSnapshot: (id: string) => void;
}

export const SnapshotDrawer: React.FC<SnapshotDrawerProps> = ({
  isOpen,
  onClose,
  snapshots,
  onDeleteSnapshot,
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
          <button
            onClick={() => {
              sounds.playClick('tactile');
              onClose();
            }}
            className="p-1.5 rounded-lg hover:bg-white/10 text-white/70 hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Snapshots List */}
        {snapshots.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-8 text-white/40 font-['Space_Mono']">
            <Camera className="w-12 h-12 mb-3 opacity-30 text-[#ccff80]" />
            <p className="text-sm">No inspection snapshots captured yet.</p>
            <p className="text-xs text-white/30 mt-1">Press the Camera button or 'S' key on camera HUD to capture frames.</p>
          </div>
        ) : (
          <div className="flex-1 flex flex-col gap-4 overflow-y-auto">
            {snapshots.map((item) => (
              <div
                key={item.id}
                className="glass-panel rounded-xl p-3 border border-white/10 flex flex-col gap-2.5 hover:border-[#a3e635]/40 transition-colors"
              >
                <div className="relative rounded-lg overflow-hidden h-36 bg-black">
                  <img
                    src={item.thumbnail}
                    alt="Captured inspection frame"
                    className="w-full h-full object-cover"
                  />
                  <div className="absolute top-2 left-2 bg-black/70 backdrop-blur px-2 py-0.5 rounded text-[10px] font-['Space_Mono'] text-[#ccff80]">
                    {item.camera}
                  </div>
                  <div className="absolute bottom-2 right-2 bg-black/70 backdrop-blur px-2 py-0.5 rounded text-[10px] font-['Space_Mono'] text-white">
                    DIST: {item.distance}
                  </div>
                </div>

                <div className="flex items-center justify-between text-xs font-['Space_Mono'] text-white/70">
                  <span>{item.timestamp}</span>
                  {item.defectCount > 0 ? (
                    <span className="text-[#ffb4ab] font-bold">
                      {item.defectCount} Defect{item.defectCount > 1 ? 's' : ''} Tagged
                    </span>
                  ) : (
                    <span className="text-[#a3e635]">Clear Conduit</span>
                  )}
                </div>

                <div className="flex items-center gap-2 pt-1 border-t border-white/10">
                  <a
                    href={item.thumbnail}
                    download={`pipevision_${item.id}.jpg`}
                    className="flex-1 py-1.5 px-3 rounded-lg bg-white/5 hover:bg-[#a3e635]/20 hover:text-[#ccff80] border border-white/10 text-xs font-['Space_Mono'] flex items-center justify-center gap-1.5 transition-colors"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>Download</span>
                  </a>
                  <button
                    onClick={() => {
                      sounds.playClick('tactile');
                      onDeleteSnapshot(item.id);
                    }}
                    className="p-1.5 rounded-lg bg-white/5 hover:bg-[#ff5449]/20 hover:text-[#ffb4ab] border border-white/10 transition-colors"
                    title="Delete snapshot"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
