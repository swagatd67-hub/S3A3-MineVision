import React from 'react';
import type { RobotDriveState } from '../types';
import { sounds } from '../utils/audio';

interface StatusPanelProps {
  robotState: RobotDriveState;
  onToggleLights: () => void;
  onChangeLightIntensity?: (val: number) => void;
}

export const StatusPanel: React.FC<StatusPanelProps> = ({
  robotState,
  onToggleLights,
}) => {
  return (
    <div
      id="status-panel"
      className="bg-[#141619] rounded-xl p-4 sm:p-5 flex items-center justify-between gap-4 border border-white/10 shadow-lg"
    >
      {/* Ready Status & Live Distance */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#a3e635] shadow-[0_0_8px_#a3e635]" />
          <span className="font-['Space_Mono'] text-xs sm:text-sm font-bold text-[#ccff80] tracking-wider uppercase">
            {robotState.isReady ? 'ROBOT: READY' : 'ROBOT: STANDBY'}
          </span>
        </div>
        <span className="text-white/30 text-xs">•</span>
        <span className="font-['Space_Mono'] text-xs sm:text-sm font-bold text-[#5de6ff] tracking-wider">
          {robotState.distanceTraveledM == null ? '--' : `${robotState.distanceTraveledM.toFixed(1)}m`}
        </span>
      </div>

      {/* Lights Toggle Switch */}
      <button
        id="btn-toggle-lights"
        onClick={() => {
          sounds.playClick('light');
          onToggleLights();
        }}
        className="flex items-center gap-2 cursor-pointer select-none group"
        title="Toggle ROV Headlights"
      >
        <span className="font-['Space_Mono'] text-[11px] font-bold text-white/70 tracking-widest uppercase">
          LIGHTS
        </span>
        <div className={`w-9 h-5 rounded-full relative transition-colors border ${
          robotState.lightsOn ? 'bg-[#a3e635]/20 border-[#a3e635]/60' : 'bg-black/50 border-white/20'
        }`}>
          <div
            className={`absolute top-1/2 -translate-y-1/2 w-3.5 h-3.5 rounded-full transition-all ${
              robotState.lightsOn
                ? 'right-1 bg-[#a3e635] shadow-[0_0_8px_#a3e635]'
                : 'left-1 bg-white/40'
            }`}
          />
        </div>
      </button>
    </div>
  );
};
