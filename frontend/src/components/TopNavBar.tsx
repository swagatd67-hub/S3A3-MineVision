import React from 'react';
import { Link } from 'react-router-dom';
import {
  Video,
  Radio,
  Settings,
  User,
} from 'lucide-react';
import type { RobotDriveState } from '../types';

interface TopNavBarProps {
  robotState: RobotDriveState;
  onToggleSound: () => void;
  soundEnabled: boolean;
  onOpenSettings: () => void;
  onOpenGallery?: () => void;
  snapshotCount?: number;
  onToggleAiOverlay?: () => void;
}

export const TopNavBar: React.FC<TopNavBarProps> = ({
  robotState,
  onToggleSound,
  soundEnabled,
  onOpenSettings,
}) => {
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
        <span className="font-['Inter'] text-xs text-white/50 bg-white/5 px-2 py-0.5 rounded border border-white/10 hidden md:inline">
          LIVE COCKPIT
        </span>
      </div>

      {/* Right Status & Controls */}
      <div className="flex items-center gap-4 sm:gap-6">
        {/* Connected Indicator */}
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#CCFF80]" />
          <span className="font-['Inter'] text-xs font-bold text-[#CCFF80] tracking-wider hidden sm:inline">
            CONNECTED ({robotState.batteryPercent}%)
          </span>
        </div>

        {/* Camera Status */}
        <div className="flex items-center gap-2 text-xs font-['Inter'] text-white/70">
          <Video className="w-4 h-4 text-white/60" />
          <span className="hidden sm:inline">CAMERA:</span>
          <span className="text-white font-semibold">OK</span>
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
