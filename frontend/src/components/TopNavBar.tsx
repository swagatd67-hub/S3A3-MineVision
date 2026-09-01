import React from 'react';
import { Link } from 'react-router-dom';
import {
  Video,
  Radio,
  Settings,
  User,
} from 'lucide-react';
import type { RobotDriveState } from '../types';
import type { RuntimeMode } from '../api/system';

interface TopNavBarProps {
  robotState: RobotDriveState;
  onToggleSound: () => void;
  soundEnabled: boolean;
  onOpenSettings: () => void;
  onOpenGallery?: () => void;
  snapshotCount?: number;
  onToggleAiOverlay?: () => void;
  runtimeMode?: RuntimeMode;
  connectionStatus?: string;
  cameraOnline?: boolean | null;
  imuAvailable?: boolean;
  telemetryDataLabel?: string;
}

export const TopNavBar: React.FC<TopNavBarProps> = ({
  robotState,
  onToggleSound,
  soundEnabled,
  onOpenSettings,
  runtimeMode = 'UNKNOWN',
  connectionStatus = 'DISCONNECTED',
  cameraOnline = null,
  imuAvailable = false,
  telemetryDataLabel = 'NO DATA',
}) => {
  const connected = connectionStatus === 'CONNECTED';
  const connecting = connectionStatus === 'CONNECTING' || connectionStatus === 'RECONNECTING';
  const battery = robotState.batteryPercent == null ? '--' : `${robotState.batteryPercent}%`;
  return (
    <nav
      id="top-navbar"
      className="fixed top-0 left-0 w-full z-50 flex justify-between items-center px-4 sm:px-6 h-16 bg-[#131416] border-b border-white/10"
    >
      {/* Brand */}
      <div className="flex items-center gap-3">
        <Link
          to="/dashboard"
          className="font-['Poppins'] text-2xl sm:text-3xl font-extrabold tracking-tight text-[#ccff80] hover:opacity-80 transition-opacity"
        >
          PIPEVISION
        </Link>
        <span className="font-['Space_Mono'] text-xs text-white/50 bg-white/5 px-2 py-0.5 rounded border border-white/10 hidden md:inline">
          LIVE COCKPIT
        </span>
      </div>

      {/* Right Status & Controls */}
      <div className="flex items-center gap-4 sm:gap-6">
        {/* Connected Indicator */}
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-[#CCFF80]' : connecting ? 'bg-amber-300 animate-pulse' : 'bg-[#ff5449]'}`} />
          <span className={`font-['Inter'] text-xs font-bold tracking-wider hidden sm:inline ${connected ? 'text-[#CCFF80]' : connecting ? 'text-amber-300' : 'text-[#ff8c82]'}`}>
            {connectionStatus} ({battery})
          </span>
        </div>

        <div className={`font-['Space_Mono'] text-[10px] font-bold tracking-wider px-2 py-1 rounded border ${runtimeMode === 'HARDWARE' ? 'text-amber-200 border-amber-300/40 bg-amber-300/10' : runtimeMode === 'SIMULATOR' ? 'text-[#ccff80] border-[#a3e635]/40 bg-[#a3e635]/10' : 'text-white/60 border-white/20'}`}>
          {runtimeMode} MODE
        </div>
        <div className="hidden md:block font-['Space_Mono'] text-[10px] font-bold tracking-wider text-amber-200 border border-amber-300/30 bg-amber-300/5 px-2 py-1 rounded">
          {telemetryDataLabel}
        </div>

        {/* Camera Status */}
        <div className="flex items-center gap-2 text-xs font-['Space_Mono'] text-white/70">
          <Video className="w-4 h-4 text-white/60" />
          <span className="hidden sm:inline">CAMERA:</span>
          <span className={`font-semibold ${cameraOnline === true ? 'text-[#ccff80]' : cameraOnline === false ? 'text-[#ff8c82]' : 'text-white/50'}`}>{cameraOnline === true ? 'LIVE' : cameraOnline === false ? 'OFFLINE' : 'UNKNOWN'}</span>
        </div>

        <div className="hidden lg:flex items-center gap-1.5 text-xs font-['Inter'] text-white/70">
          <span>IMU:</span><span className={imuAvailable ? 'text-[#ccff80] font-semibold' : 'text-white/50 font-semibold'}>{imuAvailable ? 'LIVE' : 'NO DATA'}</span>
        </div>

        {/* Sensor/Radio Icon */}
        <button
          onClick={onToggleSound}
          className="p-1.5 text-white/60 hover:text-white transition-colors"
          title={soundEnabled ? 'Mute Sounds' : 'Unmute Sounds'}
        >
          <Radio className="w-4 h-4" />
        </button>

        {/* Settings Gear */}
        <button
          onClick={onOpenSettings}
          className="p-1.5 text-white/60 hover:text-white transition-colors"
          title="System Settings"
        >
          <Settings className="w-4 h-4" />
        </button>

        {/* User Avatar */}
        <div className="w-7 h-7 rounded-full bg-white/10 border border-white/20 flex items-center justify-center text-white/80">
          <User className="w-4 h-4" />
        </div>
      </div>
    </nav>
  );
};
