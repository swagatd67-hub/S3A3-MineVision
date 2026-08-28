import { useState, useEffect } from 'react';
import { Activity } from 'lucide-react';
import type { IMUData } from '../types';
import { sounds } from '../utils/audio';

interface MPU6050PanelProps {
  imuData: IMUData;
}

type GraphTab = 'ACCELEROMETER' | 'GYROSCOPE' | 'COMBINED';

export const MPU6050Panel: React.FC<MPU6050PanelProps> = ({ imuData }) => {
  const [activeTab, setActiveTab] = useState<GraphTab>('ACCELEROMETER');
  const [timeTick, setTimeTick] = useState<number>(0);

  // Animate waveform phase over time
  useEffect(() => {
    const anim = setInterval(() => {
      setTimeTick((t) => (t + 1) % 1000);
    }, 50);
    return () => clearInterval(anim);
  }, []);

  // Format sign and decimals
  const fmt = (val: number, decimals = 2) => {
    const sign = val >= 0 ? '+' : '';
    return `${sign}${val.toFixed(decimals)}`;
  };

  // Generate dynamic wave path based on current IMU values
  const t = timeTick * 0.1;
  const accelXFactor = imuData.accel.x * 4;
  const accelYFactor = imuData.accel.y * 4;
  const accelZFactor = (imuData.accel.z - 9.8) * 4;

  const pathX = `M0 ${50 + Math.sin(t) * 4 + accelXFactor} Q 15 ${44 + Math.cos(t * 1.2) * 8 + accelXFactor}, 30 ${52 + Math.sin(t * 0.9) * 6} T 60 ${48 + Math.cos(t) * 7} T 85 ${54 + Math.sin(t * 1.1) * 6} T 100 ${50 + Math.sin(t) * 4 + accelXFactor}`;
  const pathY = `M0 ${70 + Math.cos(t * 0.8) * 5 + accelYFactor} Q 20 ${62 + Math.sin(t * 1.1) * 9 + accelYFactor}, 45 ${76 + Math.cos(t * 0.7) * 7} T 75 ${66 + Math.sin(t) * 8} T 100 ${70 + Math.cos(t * 0.8) * 5 + accelYFactor}`;
  const pathZ = `M0 ${22 + Math.sin(t * 0.7) * 6 + accelZFactor} Q 30 ${14 + Math.cos(t * 1.3) * 8 + accelZFactor}, 60 ${26 + Math.sin(t * 0.8) * 6} T 100 ${22 + Math.sin(t * 0.7) * 6 + accelZFactor}`;

  return (
    <div
      id="mpu6050-imu-panel"
      className="glass-panel rounded-xl p-5 flex flex-col gap-4 border border-[#a3e635]/20 shadow-[0_4px_30px_rgba(0,0,0,0.3)] bg-[#0e1013]/90 backdrop-blur-md"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-3">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-[#a3e635]" />
          <span className="font-['Space_Mono'] text-xs font-bold text-white tracking-widest">
            MPU6050 – 6-AXIS IMU
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#a3e635] animate-pulse shadow-[0_0_8px_#a3e635]" />
          <span className="font-['Space_Mono'] text-[10px] text-[#a3e635] font-bold tracking-wider">
            LIVE DATA
          </span>
        </div>
      </div>

      {/* Live Numeric Readout Columns */}
      <div className="grid grid-cols-2 gap-4">
        {/* Accelerometer Column */}
        <div className="flex flex-col gap-1.5">
          <div className="text-[10px] font-['Space_Mono'] font-bold text-[#c2cab0] opacity-80 border-b border-white/10 pb-1 flex justify-between">
            <span>ACCELEROMETER</span>
            <span className="lowercase font-normal text-white/50">(m/s²)</span>
          </div>
          <div className="font-['Space_Mono'] text-xs flex flex-col gap-1">
            <div className="flex justify-between items-center bg-black/40 px-2.5 py-1 rounded border border-white/5">
              <span className="text-[#a3e635] font-bold">X</span>
              <span className="text-white font-semibold">{fmt(imuData.accel.x)}</span>
            </div>
            <div className="flex justify-between items-center bg-black/40 px-2.5 py-1 rounded border border-white/5">
              <span className="text-[#a3e635] font-bold">Y</span>
              <span className="text-white font-semibold">{fmt(imuData.accel.y)}</span>
            </div>
            <div className="flex justify-between items-center bg-black/40 px-2.5 py-1 rounded border border-white/5">
              <span className="text-[#a3e635] font-bold">Z</span>
              <span className="text-white font-semibold">{fmt(imuData.accel.z)}</span>
            </div>
          </div>
        </div>

        {/* Gyroscope Column */}
        <div className="flex flex-col gap-1.5">
          <div className="text-[10px] font-['Space_Mono'] font-bold text-[#c2cab0] opacity-80 border-b border-white/10 pb-1 flex justify-between">
            <span>GYROSCOPE</span>
            <span className="lowercase font-normal text-white/50">(°/s)</span>
          </div>
          <div className="font-['Space_Mono'] text-xs flex flex-col gap-1">
            <div className="flex justify-between items-center bg-black/40 px-2.5 py-1 rounded border border-white/5">
              <span className="text-[#5de6ff] font-bold">X</span>
              <span className="text-white font-semibold">{fmt(imuData.gyro.x)}</span>
            </div>
            <div className="flex justify-between items-center bg-black/40 px-2.5 py-1 rounded border border-white/5">
              <span className="text-[#5de6ff] font-bold">Y</span>
              <span className="text-white font-semibold">{fmt(imuData.gyro.y)}</span>
            </div>
            <div className="flex justify-between items-center bg-black/40 px-2.5 py-1 rounded border border-white/5">
              <span className="text-[#5de6ff] font-bold">Z</span>
              <span className="text-white font-semibold">{fmt(imuData.gyro.z)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Graph Section */}
      <div className="flex flex-col gap-2.5">
        {/* Graph Tabs */}
        <div className="flex gap-1.5">
          {(['ACCELEROMETER', 'GYROSCOPE', 'COMBINED'] as GraphTab[]).map((tab) => (
            <button
              key={tab}
              id={`tab-${tab.toLowerCase()}`}
              onClick={() => {
                sounds.playClick('tactile');
                setActiveTab(tab);
              }}
              className={`flex-1 text-[10px] font-['Space_Mono'] font-bold py-1.5 px-2 rounded transition-all ${
                activeTab === tab
                  ? 'bg-[#a3e635]/20 text-[#ccff80] border border-[#a3e635]/60 shadow-[0_0_10px_rgba(163,230,53,0.15)]'
                  : 'bg-black/40 hover:bg-white/10 text-white/60 border border-white/10'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Large Scrolling Graph Viewport */}
        <div className="relative w-full h-32 bg-black/60 rounded-lg border border-white/15 overflow-hidden graph-grid shadow-inner select-none">
          {/* Graph Axis Legend */}
          <div className="absolute top-2 right-2 flex flex-col gap-1 bg-black/70 backdrop-blur px-2 py-1 rounded border border-white/10 z-10 font-['Space_Mono'] text-[9px]">
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-0.5 bg-[#a3e635] shadow-[0_0_4px_#a3e635]" />
              <span className="text-white">X-AXIS</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-0.5 bg-[#5de6ff] shadow-[0_0_4px_#5de6ff]" />
              <span className="text-white">Y-AXIS</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-0.5 bg-[#ffb4ab] shadow-[0_0_4px_#ffb4ab]" />
              <span className="text-white">Z-AXIS</span>
            </div>
          </div>

          {/* Real-time Dynamic Waveform Curves (SVG) */}
          <svg className="absolute inset-0 w-full h-full" preserveAspectRatio="none" viewBox="0 0 100 100">
            {/* Horizontal Zero/Neutral Reference Line */}
            <line x1="0" y1="50" x2="100" y2="50" stroke="rgba(255,255,255,0.1)" strokeDasharray="2,2" strokeWidth="0.8" />

            {/* X Wave Curve */}
            {(activeTab === 'ACCELEROMETER' || activeTab === 'COMBINED') && (
              <path
                d={pathX}
                fill="none"
                stroke="#a3e635"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ filter: 'drop-shadow(0 0 4px rgba(163,230,53,0.8))' }}
              />
            )}

            {/* Y Wave Curve */}
            {(activeTab === 'ACCELEROMETER' || activeTab === 'GYROSCOPE' || activeTab === 'COMBINED') && (
              <path
                d={pathY}
                fill="none"
                stroke="#5de6ff"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ filter: 'drop-shadow(0 0 4px rgba(93,230,255,0.8))' }}
              />
            )}

            {/* Z Wave Curve */}
            {(activeTab === 'GYROSCOPE' || activeTab === 'COMBINED') && (
              <path
                d={pathZ}
                fill="none"
                stroke="#ffb4ab"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ filter: 'drop-shadow(0 0 4px rgba(255,180,171,0.8))' }}
              />
            )}
          </svg>

          {/* Scanner Light Sweep */}
          <div
            className="absolute top-0 bottom-0 w-12 bg-gradient-to-r from-transparent via-white/20 to-transparent pointer-events-none"
            style={{
              animation: 'scan-line 3.5s linear infinite',
            }}
          />
        </div>
      </div>

      {/* 3D Orientation Widget */}
      <div className="flex items-center justify-between p-3.5 bg-black/30 rounded-xl border border-white/10">
        <div className="flex flex-col gap-1.5">
          <span className="text-[10px] font-['Space_Mono'] font-bold text-[#c2cab0] tracking-wider">
            ORIENTATION
          </span>
          <div className="font-['Space_Mono'] text-xs text-white flex flex-col gap-0.5">
            <div>Roll: <span className="text-[#a3e635] font-bold">{fmt(imuData.orientation.roll, 1)}°</span></div>
            <div>Pitch: <span className="text-[#5de6ff] font-bold">{fmt(imuData.orientation.pitch, 1)}°</span></div>
            <div>Yaw: <span className="text-[#ffb4ab] font-bold">{fmt(imuData.orientation.yaw, 1)}°</span></div>
          </div>
        </div>

        {/* 3D Gyroscopic Coordinate Gimbal Box */}
        <div className="relative w-20 h-20 mr-2 flex items-center justify-center select-none">
          {/* Outer Gimbal Ring */}
          <div
            className="absolute inset-0 border border-[#a3e635]/30 rounded-full transition-transform duration-300"
            style={{
              transform: `rotate(${imuData.orientation.roll * 2}deg)`
            }}
          />
          {/* Inner 3D Cube / Gimbal Coordinate Planes */}
          <div
            className="absolute w-12 h-12 border border-[#a3e635]/60 rounded-sm transform transition-transform duration-300 shadow-[0_0_10px_rgba(163,230,53,0.2)]"
            style={{
              transform: `rotate(${imuData.orientation.roll + 45}deg) skewX(${imuData.orientation.pitch * 2}deg)`
            }}
          />
          <div
            className="absolute w-12 h-12 border border-[#5de6ff]/60 rounded-sm transform transition-transform duration-300 shadow-[0_0_10px_rgba(93,230,255,0.2)]"
            style={{
              transform: `rotate(${imuData.orientation.yaw + 60}deg) skewY(${imuData.orientation.pitch * 2}deg)`
            }}
          />
          {/* Center Anchor Point */}
          <div className="relative w-3.5 h-3.5 bg-white/10 backdrop-blur-md border border-white/40 rounded-full flex items-center justify-center z-10 shadow-[0_0_12px_rgba(255,255,255,0.4)]">
            <div className="w-1.5 h-1.5 bg-[#ccff80] rounded-full animate-ping" />
          </div>

          {/* Coordinate Axis Lines */}
          <div className="absolute top-1/2 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-[#a3e635] to-transparent pointer-events-none" />
          <div className="absolute left-1/2 top-0 w-[1px] h-full bg-gradient-to-b from-transparent via-[#5de6ff] to-transparent pointer-events-none" />

          {/* Axis Labels */}
          <span className="absolute -top-1.5 left-1/2 -translate-x-1/2 text-[9px] text-[#5de6ff] font-['Space_Mono'] font-bold">Y</span>
          <span className="absolute top-1/2 -right-2 -translate-y-1/2 text-[9px] text-[#a3e635] font-['Space_Mono'] font-bold">X</span>
          <span className="absolute -bottom-1.5 -left-1 text-[9px] text-[#ffb4ab] font-['Space_Mono'] font-bold">Z</span>
        </div>
      </div>
    </div>
  );
};
