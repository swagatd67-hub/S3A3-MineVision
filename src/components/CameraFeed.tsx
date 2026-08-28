import React, { useRef, useState, useEffect } from 'react';
import { 
  Maximize2, 
  Minimize2,
  CircleDot, 
  Video, 
  Camera, 
  Crosshair,
  ChevronUp,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Square,
  Sun
} from 'lucide-react';
import { CameraId, DefectDetection, RobotDriveState } from '../types';
import { sounds } from '../utils/audio';

interface CameraFeedProps {
  robotState: RobotDriveState;
  activeCamera: CameraId;
  onChangeCamera: (cam: CameraId) => void;
  isRecording: boolean;
  onToggleRecord: () => void;
  recordSeconds: number;
  onTakeSnapshot: () => void;
  defects: DefectDetection[];
  onDrive?: (dir: 'FORWARD' | 'BACKWARD' | 'LEFT' | 'RIGHT') => void;
  onStop?: () => void;
  onToggleLights?: () => void;
}

export const CameraFeed: React.FC<CameraFeedProps> = ({
  robotState,
  activeCamera,
  onChangeCamera,
  isRecording,
  onToggleRecord,
  recordSeconds,
  onTakeSnapshot,
  defects,
  onDrive,
  onStop,
  onToggleLights,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showFloatingControls, setShowFloatingControls] = useState(true);

  // Dynamic sway based on robot drive
  const [cameraOffset, setCameraOffset] = useState({ x: 0, y: 0, tilt: 0 });

  useEffect(() => {
    let targetX = 0;
    let targetY = 0;
    let targetTilt = 0;

    if (robotState.direction === 'FORWARD') {
      targetY = -6;
    } else if (robotState.direction === 'BACKWARD') {
      targetY = 6;
    } else if (robotState.direction === 'LEFT') {
      targetX = 10;
      targetTilt = -2.5;
    } else if (robotState.direction === 'RIGHT') {
      targetX = -10;
      targetTilt = 2.5;
    }

    setCameraOffset({ x: targetX, y: targetY, tilt: targetTilt });
  }, [robotState.direction]);

  // Fullscreen change listener
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  const toggleFullscreen = () => {
    sounds.playClick('tactile');
    if (!isFullscreen) {
      if (containerRef.current) {
        if (containerRef.current.requestFullscreen) {
          containerRef.current.requestFullscreen().catch(() => {
            setIsFullscreen(true);
          });
        } else {
          setIsFullscreen(true);
        }
      } else {
        setIsFullscreen(true);
      }
    } else {
      if (document.fullscreenElement && document.exitFullscreen) {
        document.exitFullscreen().catch(() => {});
      }
      setIsFullscreen(false);
    }
  };

  return (
    <div 
      id="camera-feed-container"
      ref={containerRef}
      className={`relative overflow-hidden bg-[#0d0f12] rounded-xl border border-white/10 shadow-xl flex items-center justify-center select-none ${
        isFullscreen 
          ? 'fixed inset-0 z-50 w-screen h-screen rounded-none border-none' 
          : 'flex-1 min-h-[420px] lg:min-h-[460px] h-full'
      }`}
    >
      {/* Video Content Layer */}
      <div 
        className="absolute inset-0 w-full h-full transition-transform duration-300 ease-out"
        style={{
          transform: `scale(1.02) translate(${cameraOffset.x}px, ${cameraOffset.y}px) rotate(${cameraOffset.tilt}deg)`,
        }}
      >
        <img
          src="https://lh3.googleusercontent.com/aida-public/AB6AXuBvfMfhcz24RmhMYJ7iw5PF7U-Fq1B-49z-fg_6taI15_l9ZrSylVSSgrJ900BXZwz1Xaj9QXrUQSyhX3f9k61JOTr5eKjCWRirHXKpP0kUHLYWUWkPDh3X9t9wJsRbEYrGpn2PyyOz6OTTgdkKl6MTuEclTrS-BTw5Arr9o_JYFzHhUoPha9GnHBQPVSyoNwaiMklf0Ock8moBZlk17cINgvWGxMbVhjlkxsD7RR1AQIDBOMf8RIb25Q"
          alt="Subterranean Pipe Inspection Camera"
          className={`w-full h-full object-cover transition-opacity duration-300 ${
            robotState.lightsOn ? 'opacity-95' : 'opacity-40'
          }`}
        />

        {/* Headlights Spotlight Effect */}
        {robotState.lightsOn && (
          <div 
            className="absolute inset-0 pointer-events-none transition-opacity duration-300"
            style={{
              background: 'radial-gradient(circle at 50% 50%, rgba(204, 255, 128, 0.12) 0%, rgba(93, 230, 255, 0.06) 40%, transparent 70%)',
            }}
          />
        )}
      </div>

      {/* CRT Scanline and Vignette effects */}
      <div className="absolute inset-0 scanlines pointer-events-none opacity-40" />
      <div className="absolute inset-0 vignette pointer-events-none" />

      {/* Top Left Tags: LIVE + CAM 01 */}
      <div className="absolute top-3 left-3 sm:top-4 sm:left-4 flex items-center gap-2 z-20">
        {/* LIVE Badge */}
        <div className="bg-[#2a1313]/80 border border-[#ff5449]/50 px-2 py-0.5 rounded flex items-center gap-1.5 font-['Space_Mono'] text-[11px] text-[#ffb4ab] shadow-lg">
          <span className="w-2 h-2 rounded-full bg-[#ff5449] animate-pulse" />
          <span className="font-bold">LIVE</span>
        </div>

        {/* CAM 01 Badge */}
        <div className="bg-black/60 backdrop-blur-sm border border-white/20 px-2 py-0.5 rounded font-['Space_Mono'] text-[11px] text-white/90 font-semibold shadow-lg">
          CAM 01
        </div>
      </div>

      {/* Top Right Action Buttons: Fullscreen & Snapshot */}
      <div className="absolute top-3 right-3 sm:top-4 sm:right-4 flex items-center gap-2 z-20">
        {/* Fullscreen Toggle */}
        <button
          id="btn-cam-fullscreen"
          onClick={toggleFullscreen}
          title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen View'}
          className="bg-black/60 hover:bg-black/90 border border-white/20 p-2 rounded text-white hover:text-[#5de6ff] transition-all cursor-pointer shadow-lg"
        >
          {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
        </button>

        {/* Snapshot Target Button */}
        <button
          id="btn-cam-snapshot"
          onClick={() => {
            sounds.playClick('shutter');
            onTakeSnapshot();
          }}
          title="Capture Snapshot (S)"
          className="bg-black/60 hover:bg-black/90 border border-white/20 p-2 rounded text-white hover:text-[#a3e635] transition-all cursor-pointer shadow-lg"
        >
          <CircleDot className="w-4 h-4" />
        </button>
      </div>

      {/* Center Circular Reticle */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none select-none">
        <div className="w-32 h-32 sm:w-40 sm:h-40 border border-[#a3e635]/30 rounded-full relative">
          <div className="absolute top-1/2 left-0 w-3 h-[1px] bg-[#a3e635]/60 -translate-y-1/2 -translate-x-full" />
          <div className="absolute top-1/2 right-0 w-3 h-[1px] bg-[#a3e635]/60 -translate-y-1/2 translate-x-full" />
          <div className="absolute left-1/2 top-0 w-[1px] h-3 bg-[#a3e635]/60 -translate-x-1/2 -translate-y-full" />
          <div className="absolute left-1/2 bottom-0 w-[1px] h-3 bg-[#a3e635]/60 -translate-x-1/2 translate-y-full" />
          <div className="absolute top-1/2 left-1/2 w-1.5 h-1.5 bg-[#a3e635]/70 rounded-full -translate-x-1/2 -translate-y-1/2" />
        </div>
      </div>

      {/* HUD Corner Accents */}
      <div className="absolute top-2 left-2 w-3 h-3 border-t-2 border-l-2 border-[#a3e635]/40 pointer-events-none" />
      <div className="absolute top-2 right-2 w-3 h-3 border-t-2 border-r-2 border-[#a3e635]/40 pointer-events-none" />
      <div className="absolute bottom-2 left-2 w-3 h-3 border-b-2 border-l-2 border-[#a3e635]/40 pointer-events-none" />
      <div className="absolute bottom-2 right-2 w-3 h-3 border-b-2 border-r-2 border-[#a3e635]/40 pointer-events-none" />

      {/* Fullscreen Floating Console Controller Overlay (When in Fullscreen) */}
      {isFullscreen && (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-40 bg-[#141619]/90 backdrop-blur-md p-4 rounded-2xl border border-white/20 shadow-2xl flex flex-col items-center gap-3">
          <div className="flex items-center justify-between w-full border-b border-white/10 pb-2 px-1">
            <span className="font-['Space_Mono'] text-[10px] font-bold text-[#ccff80] tracking-wider uppercase">
              FULLSCREEN ROV CONTROL
            </span>
            <div className="flex items-center gap-3">
              {onToggleLights && (
                <button
                  onClick={onToggleLights}
                  className={`px-2 py-0.5 rounded text-[10px] font-['Space_Mono'] border flex items-center gap-1 ${
                    robotState.lightsOn ? 'bg-[#a3e635]/20 border-[#a3e635] text-[#ccff80]' : 'bg-black/40 border-white/20 text-white/50'
                  }`}
                >
                  <Sun className="w-3 h-3" />
                  <span>LIGHTS</span>
                </button>
              )}
              <span className="font-['Space_Mono'] text-[10px] text-white/60">
                DIST: +{robotState.distanceTraveledM.toFixed(1)}m
              </span>
            </div>
          </div>

          {/* Floating D-Pad for Fullscreen Operation */}
          <div className="relative w-44 h-44 flex items-center justify-center select-none">
            {/* Center Stop */}
            <button
              onClick={() => onStop && onStop()}
              className="z-20 w-14 h-14 rounded-full bg-[#201515] active:scale-95 border border-[#ff5449]/50 flex flex-col items-center justify-center cursor-pointer text-[#ffb4ab]"
            >
              <Square className="w-3.5 h-3.5 fill-[#ffb4ab]" />
              <span className="font-['Space_Mono'] text-[8px] font-bold tracking-widest mt-0.5">STOP</span>
            </button>

            {/* Forward */}
            <button
              onClick={() => onDrive && onDrive('FORWARD')}
              className={`absolute top-0 left-1/2 -translate-x-1/2 w-10 h-10 rounded-full bg-[#1b1e22] active:scale-95 border border-white/10 flex items-center justify-center ${
                robotState.direction === 'FORWARD' ? 'border-[#a3e635] text-[#a3e635]' : 'text-white/80'
              }`}
            >
              <ChevronUp className="w-5 h-5" />
            </button>

            {/* Backward */}
            <button
              onClick={() => onDrive && onDrive('BACKWARD')}
              className={`absolute bottom-0 left-1/2 -translate-x-1/2 w-10 h-10 rounded-full bg-[#1b1e22] active:scale-95 border border-white/10 flex items-center justify-center ${
                robotState.direction === 'BACKWARD' ? 'border-[#a3e635] text-[#a3e635]' : 'text-white/80'
              }`}
            >
              <ChevronDown className="w-5 h-5" />
            </button>

            {/* Left */}
            <button
              onClick={() => onDrive && onDrive('LEFT')}
              className={`absolute left-0 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-[#1b1e22] active:scale-95 border border-white/10 flex items-center justify-center ${
                robotState.direction === 'LEFT' ? 'border-[#a3e635] text-[#a3e635]' : 'text-white/80'
              }`}
            >
              <ChevronLeft className="w-5 h-5" />
            </button>

            {/* Right */}
            <button
              onClick={() => onDrive && onDrive('RIGHT')}
              className={`absolute right-0 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-[#1b1e22] active:scale-95 border border-white/10 flex items-center justify-center ${
                robotState.direction === 'RIGHT' ? 'border-[#a3e635] text-[#a3e635]' : 'text-white/80'
              }`}
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>

          <div className="font-['Space_Mono'] text-[9px] text-white/50">
            Keyboard: <span className="text-[#ccff80]">W A S D</span> | <span className="text-[#ffb4ab]">SPACE = STOP</span> | <span className="text-[#5de6ff]">ESC / [ ] = Exit</span>
          </div>
        </div>
      )}
    </div>
  );
};
