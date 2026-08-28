import React from 'react';
import { 
  ChevronUp, 
  ChevronDown, 
  ChevronLeft, 
  ChevronRight, 
  Square
} from 'lucide-react';
import { RobotDriveState } from '../types';
import { sounds } from '../utils/audio';

interface ControlConsoleProps {
  robotState: RobotDriveState;
  onDrive: (dir: 'FORWARD' | 'BACKWARD' | 'LEFT' | 'RIGHT') => void;
  onStop: () => void;
  onChangeThrottle?: (throttle: number) => void;
  onChangeGear?: (gear: 'CRAWL' | 'CRUISE' | 'TURBO') => void;
  onToggleScanMode?: () => void;
  onToggleArm?: () => void;
}

export const ControlConsole: React.FC<ControlConsoleProps> = ({
  robotState,
  onDrive,
  onStop,
}) => {
  return (
    <div 
      id="robot-control-console"
      className="bg-[#141619] rounded-xl p-5 sm:p-6 flex flex-col gap-6 shadow-xl border border-white/10"
    >
      {/* Console Header */}
      <div className="flex flex-wrap justify-between items-center border-b border-white/10 pb-3 gap-3">
        <h3 className="font-['Space_Mono'] text-xs sm:text-sm font-bold text-[#c2cab0] tracking-widest uppercase">
          ROBOT CONTROL CONSOLE
        </h3>

        <div className="flex items-center gap-4 sm:gap-6 font-['Space_Mono'] text-[10px] sm:text-xs">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[#a3e635] shadow-[0_0_8px_#a3e635]" />
            <span className="text-[#a3e635] font-bold">ROBOT: READY</span>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[#eab308] shadow-[0_0_8px_#eab308]" />
            <span className="text-[#eab308] font-bold">CONNECTION: CONNECTED</span>
          </div>
        </div>
      </div>

      {/* Centered Circular D-Pad Controller */}
      <div className="flex flex-col items-center justify-center py-4">
        <div className="relative w-64 h-64 sm:w-72 sm:h-72 flex items-center justify-center select-none">
          {/* Subtle concentric rings */}
          <div className="absolute inset-0 border border-white/5 rounded-full" />
          <div className="absolute inset-8 border border-white/10 rounded-full" />
          <div className="absolute inset-16 border border-white/5 rounded-full" />

          {/* Central Emergency STOP Button */}
          <button
            id="btn-emergency-stop"
            onClick={() => {
              sounds.playStopAlert();
              onStop();
            }}
            className="z-20 w-20 h-20 sm:w-24 sm:h-24 rounded-full bg-[#201515] hover:bg-[#301c1c] active:scale-95 border border-[#ff5449]/40 flex flex-col items-center justify-center cursor-pointer select-none transition-all shadow-[0_0_20px_rgba(255,84,73,0.2)] group"
            title="Emergency Stop (Spacebar)"
          >
            <div className="w-6 h-6 rounded-full border-2 border-[#ffb4ab] flex items-center justify-center mb-0.5">
              <Square className="w-2.5 h-2.5 fill-[#ffb4ab] text-[#ffb4ab]" />
            </div>
            <span className="font-['Space_Mono'] text-[10px] font-bold text-[#ffb4ab] tracking-widest">
              STOP
            </span>
          </button>

          {/* FORWARD (W) */}
          <button
            id="btn-drive-forward"
            onClick={() => {
              sounds.playClick('tactile');
              onDrive('FORWARD');
            }}
            className={`absolute top-2 left-1/2 -translate-x-1/2 w-14 h-14 sm:w-16 sm:h-16 rounded-full bg-[#1b1e22] hover:bg-[#252a30] active:scale-95 border border-white/10 flex flex-col items-center justify-center cursor-pointer transition-all ${
              robotState.direction === 'FORWARD' ? 'border-[#a3e635] text-[#a3e635] shadow-[0_0_15px_rgba(163,230,53,0.4)]' : 'text-white/70 hover:text-white'
            }`}
            title="Drive Forward (W)"
          >
            <ChevronUp className="w-5 h-5 sm:w-6 sm:h-6" />
            <span className="font-['Space_Mono'] text-[7px] sm:text-[8px] font-bold tracking-wider">
              FORWARD
            </span>
          </button>

          {/* BACKWARD (S) */}
          <button
            id="btn-drive-backward"
            onClick={() => {
              sounds.playClick('tactile');
              onDrive('BACKWARD');
            }}
            className={`absolute bottom-2 left-1/2 -translate-x-1/2 w-14 h-14 sm:w-16 sm:h-16 rounded-full bg-[#1b1e22] hover:bg-[#252a30] active:scale-95 border border-white/10 flex flex-col items-center justify-center cursor-pointer transition-all ${
              robotState.direction === 'BACKWARD' ? 'border-[#a3e635] text-[#a3e635] shadow-[0_0_15px_rgba(163,230,53,0.4)]' : 'text-white/70 hover:text-white'
            }`}
            title="Drive Backward (S)"
          >
            <span className="font-['Space_Mono'] text-[7px] sm:text-[8px] font-bold tracking-wider">
              BACKWARD
            </span>
            <ChevronDown className="w-5 h-5 sm:w-6 sm:h-6" />
          </button>

          {/* LEFT (A) */}
          <button
            id="btn-drive-left"
            onClick={() => {
              sounds.playClick('tactile');
              onDrive('LEFT');
            }}
            className={`absolute left-2 top-1/2 -translate-y-1/2 w-14 h-14 sm:w-16 sm:h-16 rounded-full bg-[#1b1e22] hover:bg-[#252a30] active:scale-95 border border-white/10 flex flex-col items-center justify-center cursor-pointer transition-all ${
              robotState.direction === 'LEFT' ? 'border-[#a3e635] text-[#a3e635] shadow-[0_0_15px_rgba(163,230,53,0.4)]' : 'text-white/70 hover:text-white'
            }`}
            title="Turn Left (A)"
          >
            <ChevronLeft className="w-5 h-5 sm:w-6 sm:h-6" />
            <span className="font-['Space_Mono'] text-[7px] sm:text-[8px] font-bold tracking-wider">
              LEFT
            </span>
          </button>

          {/* RIGHT (D) */}
          <button
            id="btn-drive-right"
            onClick={() => {
              sounds.playClick('tactile');
              onDrive('RIGHT');
            }}
            className={`absolute right-2 top-1/2 -translate-y-1/2 w-14 h-14 sm:w-16 sm:h-16 rounded-full bg-[#1b1e22] hover:bg-[#252a30] active:scale-95 border border-white/10 flex flex-col items-center justify-center cursor-pointer transition-all ${
              robotState.direction === 'RIGHT' ? 'border-[#a3e635] text-[#a3e635] shadow-[0_0_15px_rgba(163,230,53,0.4)]' : 'text-white/70 hover:text-white'
            }`}
            title="Turn Right (D)"
          >
            <ChevronRight className="w-5 h-5 sm:w-6 sm:h-6" />
            <span className="font-['Space_Mono'] text-[7px] sm:text-[8px] font-bold tracking-wider">
              RIGHT
            </span>
          </button>
        </div>

        {/* Keyboard hint footer */}
        <div className="font-['Space_Mono'] text-[10px] sm:text-xs text-white/40 tracking-wider mt-2">
          Keyboard: <span className="text-[#ccff80]">W A S D</span> | <span className="text-[#ffb4ab]">SPACE = STOP</span>
        </div>
      </div>
    </div>
  );
};
