import React, { useState } from 'react';
import { Sliders, RefreshCw, CheckCircle, Wind, Compass } from 'lucide-react';
import { sounds } from '../utils/audio';

interface CalibrationViewProps {
  onReturnToTelemetry: () => void;
  onCalibrateImu: () => void;
}

export const CalibrationView: React.FC<CalibrationViewProps> = ({
  onReturnToTelemetry,
  onCalibrateImu,
}) => {
  const [calibrating, setCalibrating] = useState(false);
  const [calibrated, setCalibrated] = useState(false);

  const startCalib = () => {
    sounds.playClick('switch');
    setCalibrating(true);
    setCalibrated(false);
    setTimeout(() => {
      setCalibrating(false);
      setCalibrated(true);
      onCalibrateImu();
    }, 1500);
  };

  return (
    <div className="flex-1 flex flex-col gap-6 animate-fade-in">
      <div className="glass-panel rounded-2xl p-6 flex items-center justify-between border border-white/10">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-[#a3e635]/20 border border-[#a3e635]/40 flex items-center justify-center text-[#ccff80]">
            <Sliders className="w-6 h-6" />
          </div>
          <div>
            <h2 className="font-['Poppins'] text-xl font-bold text-white">
              Sensor Diagnostics & Calibration
            </h2>
            <p className="font-['Space_Mono'] text-xs text-white/50">
              Hardware verification, zero-offset trimming & gas sensor calibration
            </p>
          </div>
        </div>

        <button
          onClick={() => {
            sounds.playClick('tactile');
            onReturnToTelemetry();
          }}
          className="px-4 py-2 rounded-xl bg-[#a3e635] text-[#121f00] font-['Space_Mono'] text-xs font-bold"
        >
          Live Telemetry
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 font-['Space_Mono']">
        {/* IMU Calibration Card */}
        <div className="glass-panel rounded-2xl p-6 border border-white/10 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h3 className="font-['Poppins'] text-base font-bold text-white flex items-center gap-2">
              <Compass className="w-5 h-5 text-[#a3e635]" />
              MPU6050 6-Axis Gyro & Accel
            </h3>
            <span className="text-[10px] text-[#a3e635] px-2 py-0.5 rounded bg-[#a3e635]/15 border border-[#a3e635]/30">
              OPERATIONAL
            </span>
          </div>

          <p className="text-xs text-white/60">
            Performs a 100-sample static gravity reading to calculate zero-g and zero-rate bias offsets. Ensure the robot is parked flat on the conduit floor before initiating.
          </p>

          <div className="p-3 bg-black/40 rounded-xl text-xs flex flex-col gap-1 border border-white/5">
            <div className="flex justify-between">
              <span>Accelerometer Bias:</span>
              <span className="text-[#a3e635]">X: +0.02, Y: -0.01, Z: +9.81 m/s²</span>
            </div>
            <div className="flex justify-between">
              <span>Gyroscope Drift:</span>
              <span className="text-[#5de6ff]">X: 0.04°/s, Y: -0.02°/s, Z: 0.01°/s</span>
            </div>
          </div>

          <button
            onClick={startCalib}
            disabled={calibrating}
            className="w-full py-2.5 rounded-xl bg-[#a3e635]/20 hover:bg-[#a3e635] text-[#ccff80] hover:text-[#121f00] border border-[#a3e635]/50 font-bold text-xs flex items-center justify-center gap-2 transition-all cursor-pointer"
          >
            {calibrating ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Zero-Calibrating IMU Sensors...</span>
              </>
            ) : calibrated ? (
              <>
                <CheckCircle className="w-4 h-4 text-[#a3e635]" />
                <span>Zero Baseline Applied Successfully</span>
              </>
            ) : (
              <span>Start Gyroscope Zero Calibration</span>
            )}
          </button>
        </div>

        {/* NDIR CO2 & Toxic Gas Calibration Card */}
        <div className="glass-panel rounded-2xl p-6 border border-white/10 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h3 className="font-['Poppins'] text-base font-bold text-white flex items-center gap-2">
              <Wind className="w-5 h-5 text-[#5de6ff]" />
              NDIR CO2 & O2 Gas Multi-Sensor
            </h3>
            <span className="text-[10px] text-[#5de6ff] px-2 py-0.5 rounded bg-[#5de6ff]/15 border border-[#5de6ff]/30">
              CALIBRATED
            </span>
          </div>

          <p className="text-xs text-white/60">
            Dual-channel Non-Dispersive Infrared optical sensor with automated baseline correction (ABC).
          </p>

          <div className="p-3 bg-black/40 rounded-xl text-xs flex flex-col gap-1 border border-white/5">
            <div className="flex justify-between">
              <span>Fresh Air Baseline:</span>
              <span className="text-[#5de6ff]">400 PPM Reference</span>
            </div>
            <div className="flex justify-between">
              <span>Response Time (t90):</span>
              <span className="text-white">1.8 Seconds</span>
            </div>
          </div>

          <button
            onClick={() => {
              sounds.playClick('tactile');
              alert('CO2 Baseline Verified at 412 PPM against ambient atmosphere.');
            }}
            className="w-full py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-white border border-white/15 font-bold text-xs transition-colors"
          >
            Verify Atmospheric Baseline
          </button>
        </div>
      </div>
    </div>
  );
};
