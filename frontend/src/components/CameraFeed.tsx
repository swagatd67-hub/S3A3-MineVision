import React, { useRef, useState, useEffect } from 'react';
import {
  Maximize2,
  Minimize2,
  CircleDot,
  ChevronUp,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Square,
  Sun,
  RefreshCw,
  VideoOff,
} from 'lucide-react';
import type { CameraId, DefectDetection, RobotDriveState } from '../types';
import { sounds } from '../utils/audio';
import { getLiveStreamUrl } from '../api/video';

interface CameraFeedProps {
  missionId?: string;
  robotState: RobotDriveState;
  activeCamera: CameraId;
  onChangeCamera: (cam: CameraId) => void;
  isRecording: boolean;
  recordingStatus?: 'IDLE' | 'STARTING' | 'RECORDING' | 'STOPPING' | 'ERROR';
  onToggleRecord: () => void;
  recordSeconds: number;
  onTakeSnapshot: () => void;
  defects: DefectDetection[];
  onDrive?: (dir: 'FORWARD' | 'BACKWARD' | 'LEFT' | 'RIGHT') => void;
  onStop?: () => void;
  onToggleLights?: () => void;
  onStreamStatusChange?: (online: boolean) => void;
}

export const CameraFeed: React.FC<CameraFeedProps> = ({
  missionId = 'M-104',
  robotState,
  activeCamera,
  onChangeCamera,
  isRecording,
  recordingStatus = 'IDLE',
  onToggleRecord,
  recordSeconds,
  onTakeSnapshot,
  onDrive,
  onStop,
  onToggleLights,
  onStreamStatusChange,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Stream status & retry handling
  const [streamError, setStreamError] = useState(false);
  const [streamRetryKey, setStreamRetryKey] = useState(0);

  // Derive stream URL using real backend helper
  const streamUrl = `${getLiveStreamUrl(missionId, 10, activeCamera, true)}&_k=${streamRetryKey}`;

  const handleChangeCamera = (cam: CameraId) => {
    setStreamError(false);
    onStreamStatusChange?.(false);
    onChangeCamera(cam);
  };

  // Dynamic sway based on robot drive derived directly during render
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

  const cameraOffset = { x: targetX, y: targetY, tilt: targetTilt };

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

  const handleRetryStream = () => {
    sounds.playClick('tactile');
    setStreamError(false);
    onStreamStatusChange?.(false);
    setStreamRetryKey((prev) => prev + 1);
  };

  const cameraLabels: Record<CameraId, string> = {
    'cam-01': 'CAM 01 (FRONT)',
    'cam-02': 'CAM 02 (REAR)',
    'cam-03': 'CAM 03 (PAN-TILT)',
    thermal: 'THERMAL VISION',
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
        className="absolute inset-0 w-full h-full transition-transform duration-300 ease-out flex items-center justify-center"
        style={{
          transform: `scale(1.02) translate(${cameraOffset.x}px, ${cameraOffset.y}px) rotate(${cameraOffset.tilt}deg)`,
        }}
      >
        {!streamError ? (
          <img
            key={streamUrl}
            src={streamUrl}
            alt={`Live Mission ${missionId} Camera Feed (${activeCamera})`}
            onLoad={() => {
              setStreamError(false);
              onStreamStatusChange?.(true);
            }}
            onError={() => {
              setStreamError(true);
              onStreamStatusChange?.(false);
            }}
            className={`w-full h-full object-cover transition-opacity duration-300 ${
              robotState.lightsOn ? 'opacity-95' : 'opacity-40'
            }`}
          />
        ) : (
          /* Tactical Offline / Stream Error Overlay */
          <div className="absolute inset-0 bg-[#0c0d10] flex flex-col items-center justify-center gap-4 p-6 text-center z-10">
            <div className="p-4 rounded-full bg-[#ff5449]/10 border border-[#ff5449]/30 text-[#ff5449] animate-pulse">
              <VideoOff className="w-10 h-10" />
            </div>
            <div>
              <h3 className="font-['Poppins'] text-lg font-bold text-white uppercase tracking-wider">
                CAMERA OFFLINE / STREAM UNAVAILABLE
              </h3>
              <p className="font-['Space_Mono'] text-xs text-[#ff8c82] mt-1 max-w-sm">
                Backend stream at <code className="text-white bg-black/60 px-1 py-0.5 rounded">/api/v1/video/missions/{missionId}/stream</code> is disconnected or unavailable.
              </p>
            </div>
            <button
              onClick={handleRetryStream}
              className="px-4 py-2 rounded-lg bg-[#a3e635] hover:bg-[#b6f059] text-black font-['Space_Mono'] text-xs font-bold uppercase tracking-wider flex items-center gap-2 transition-all cursor-pointer shadow-lg"
            >
              <RefreshCw className="w-4 h-4" />
              <span>Retry Camera Feed</span>
            </button>
          </div>
        )}

        {/* Headlights Spotlight Effect */}
        {robotState.lightsOn && !streamError && (
          <div
            className="absolute inset-0 pointer-events-none transition-opacity duration-300"
            style={{
              background:
                'radial-gradient(circle at 50% 50%, rgba(204, 255, 128, 0.12) 0%, rgba(93, 230, 255, 0.06) 40%, transparent 70%)',
            }}
          />
        )}
      </div>

      {/* CRT Scanline and Vignette effects */}
      <div className="absolute inset-0 scanlines pointer-events-none opacity-40" />
      <div className="absolute inset-0 vignette pointer-events-none" />

      {/* Top Left Tags: LIVE/OFFLINE Badge + Camera Selector */}
      <div className="absolute top-3 left-3 sm:top-4 sm:left-4 flex flex-wrap items-center gap-2 z-20">
        {/* Stream Status Badge */}
        {!streamError ? (
          <div className="bg-[#1a2e1a]/80 border border-[#a3e635]/50 px-2 py-0.5 rounded flex items-center gap-1.5 font-['Space_Mono'] text-[11px] text-[#ccff80] shadow-lg">
            <span className="w-2 h-2 rounded-full bg-[#a3e635] animate-pulse" />
            <span className="font-bold">LIVE STREAM</span>
          </div>
        ) : (
          <div className="bg-[#2a1313]/80 border border-[#ff5449]/50 px-2 py-0.5 rounded flex items-center gap-1.5 font-['Space_Mono'] text-[11px] text-[#ffb4ab] shadow-lg">
            <span className="w-2 h-2 rounded-full bg-[#ff5449]" />
            <span className="font-bold">OFFLINE</span>
          </div>
        )}

        {/* Camera Selector Dropdown / Badge */}
        <select
          value={activeCamera}
          onChange={(e) => {
            sounds.playClick('tactile');
            handleChangeCamera(e.target.value as CameraId);
          }}
          className="bg-black/70 backdrop-blur-sm border border-white/20 px-2 py-0.5 rounded font-['Space_Mono'] text-[11px] text-white font-semibold shadow-lg focus:outline-none focus:border-[#5de6ff] cursor-pointer"
        >
          <option value="cam-01">CAM 01 (FRONT)</option>
          <option value="cam-02">CAM 02 (REAR)</option>
          <option value="cam-03">CAM 03 (PAN-TILT)</option>
          <option value="thermal">THERMAL VISION</option>
        </select>

        {/* Recording Status Badge */}
        {isRecording && (
          <div className="bg-[#ff5449]/20 border border-[#ff5449]/60 px-2 py-0.5 rounded flex items-center gap-1.5 font-['Space_Mono'] text-[11px] text-[#ff8c82] animate-pulse shadow-lg">
            <span className="w-2 h-2 rounded-full bg-[#ff5449]" />
            <span className="font-bold uppercase">
              {recordingStatus === 'STARTING'
                ? 'STARTING REC...'
                : recordingStatus === 'STOPPING'
                ? 'STOPPING REC...'
                : `REC ${Math.floor(recordSeconds / 60)
                    .toString()
                    .padStart(2, '0')}:${(recordSeconds % 60).toString().padStart(2, '0')}`}
            </span>
          </div>
        )}
      </div>

      {/* Top Right Action Buttons: Record, Fullscreen & Snapshot */}
      <div className="absolute top-3 right-3 sm:top-4 sm:right-4 flex items-center gap-2 z-20">
        {/* Record Toggle */}
        <button
          id="btn-cam-record"
          onClick={onToggleRecord}
          disabled={recordingStatus === 'STARTING' || recordingStatus === 'STOPPING'}
          title={isRecording ? 'Stop Recording' : 'Start Recording'}
          className={`border p-2 rounded transition-all cursor-pointer shadow-lg flex items-center gap-1.5 ${
            isRecording
              ? 'bg-[#ff5449]/20 hover:bg-[#ff5449]/40 border-[#ff5449] text-[#ff8c82]'
              : 'bg-black/60 hover:bg-black/90 border-white/20 text-white hover:text-[#ff5449]'
          } ${
            recordingStatus === 'STARTING' || recordingStatus === 'STOPPING'
              ? 'opacity-50 cursor-not-allowed'
              : ''
          }`}
        >
          <Square className={`w-4 h-4 ${isRecording ? 'fill-[#ff5449]' : ''}`} />
        </button>

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
              FULLSCREEN ROV CONTROL • {cameraLabels[activeCamera]}
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
                DIST: {robotState.distanceTraveledM == null ? '--' : `+${robotState.distanceTraveledM.toFixed(1)}m`}
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
