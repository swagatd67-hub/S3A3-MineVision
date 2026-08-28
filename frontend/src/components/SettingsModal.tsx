import React, { useState } from 'react';
import { X, Settings, RefreshCw, Check } from 'lucide-react';
import { sounds } from '../utils/audio';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCalibrateImu: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  onCalibrateImu,
}) => {
  const [videoQuality, setVideoQuality] = useState('1080p60');
  const [autoStabilize, setAutoStabilize] = useState(true);
  const [tetherWarningMeters, setTetherWarningMeters] = useState(250);
  const [calibrating, setCalibrating] = useState(false);
  const [calibratedSuccess, setCalibratedSuccess] = useState(false);

  if (!isOpen) return null;

  const handleCalibrate = () => {
    sounds.playClick('switch');
    setCalibrating(true);
    setCalibratedSuccess(false);
    setTimeout(() => {
      setCalibrating(false);
      setCalibratedSuccess(true);
      onCalibrateImu();
      setTimeout(() => setCalibratedSuccess(false), 3000);
    }, 1200);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
      <div
        id="settings-modal"
        className="w-full max-w-lg bg-[#131417] rounded-2xl border border-white/15 p-6 flex flex-col gap-6 shadow-2xl"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/10 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-[#202226] border border-[#a3e635]/30">
              <Settings className="w-5 h-5 text-[#ccff80]" />
            </div>
            <div>
              <h3 className="font-['Poppins'] text-lg font-bold text-white">
                ROV-01 System Configuration
              </h3>
              <p className="font-['Space_Mono'] text-xs text-white/50">
                Firmware v4.2.1 • Subterranean Protocol
              </p>
            </div>
          </div>
          <button
            onClick={() => {
              sounds.playClick('tactile');
              onClose();
            }}
            className="p-2 rounded-lg hover:bg-white/10 text-white/70 hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Options List */}
        <div className="flex flex-col gap-4 font-['Space_Mono'] text-xs">
          {/* Video Stream Quality */}
          <div className="flex items-center justify-between p-3 rounded-xl bg-black/40 border border-white/5">
            <div>
              <div className="text-white font-bold">Video Stream Resolution</div>
              <div className="text-[11px] text-white/40">H.265 Ultra-Low Latency Feed</div>
            </div>
            <select
              value={videoQuality}
              onChange={(e) => setVideoQuality(e.target.value)}
              className="bg-[#202226] text-[#ccff80] border border-white/20 rounded-lg px-3 py-1.5 outline-none font-bold"
            >
              <option value="1080p60">1080p @ 60 FPS</option>
              <option value="720p60">720p @ 60 FPS</option>
              <option value="4k30">4K UHD @ 30 FPS</option>
            </select>
          </div>

          {/* Auto IMU Gyro Zero-Offset Calibration */}
          <div className="flex items-center justify-between p-3 rounded-xl bg-black/40 border border-white/5">
            <div>
              <div className="text-white font-bold">MPU6050 Zero-Offset Calibration</div>
              <div className="text-[11px] text-white/40">Reset level baseline on static ground</div>
            </div>
            <button
              onClick={handleCalibrate}
              disabled={calibrating}
              className={`px-3.5 py-2 rounded-lg font-bold border flex items-center gap-1.5 transition-all ${
                calibratedSuccess
                  ? 'bg-[#a3e635] text-[#121f00] border-[#a3e635]'
                  : 'bg-white/10 hover:bg-[#a3e635]/20 text-white hover:text-[#ccff80] border-white/20'
              }`}
            >
              {calibrating ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Calibrating...</span>
                </>
              ) : calibratedSuccess ? (
                <>
                  <Check className="w-3.5 h-3.5" />
                  <span>Zeroed!</span>
                </>
              ) : (
                <span>Zero Calibrate</span>
              )}
            </button>
          </div>

          {/* Auto Stabilize Tilt */}
          <div className="flex items-center justify-between p-3 rounded-xl bg-black/40 border border-white/5">
            <div>
              <div className="text-white font-bold">Active Pipe Inversion Assist</div>
              <div className="text-[11px] text-white/40">Auto counter-roll stabilization in curved conduits</div>
            </div>
            <input
              type="checkbox"
              checked={autoStabilize}
              onChange={(e) => setAutoStabilize(e.target.checked)}
              className="w-5 h-5 accent-[#a3e635] rounded cursor-pointer"
            />
          </div>

          {/* Tether Alarm */}
          <div className="flex flex-col gap-2 p-3 rounded-xl bg-black/40 border border-white/5">
            <div className="flex justify-between items-center">
              <span className="text-white font-bold">Tether Range Limit Alarm</span>
              <span className="text-[#5de6ff] font-bold">{tetherWarningMeters}m / 300m</span>
            </div>
            <input
              type="range"
              min="50"
              max="290"
              value={tetherWarningMeters}
              onChange={(e) => setTetherWarningMeters(Number(e.target.value))}
              className="w-full accent-[#5de6ff] cursor-pointer"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-white/10 pt-4 flex justify-end gap-3 font-['Space_Mono'] text-xs">
          <button
            onClick={() => {
              sounds.playClick('tactile');
              onClose();
            }}
            className="px-4 py-2 rounded-lg bg-white/10 hover:bg-white/15 text-white font-bold"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
