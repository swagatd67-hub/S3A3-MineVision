import React, { useEffect, useState } from 'react';
import { Activity } from 'lucide-react';
import type { TelemetryIMU } from '../types/telemetry';

interface MPU6050PanelProps { imuData: TelemetryIMU | null; dataIsSimulated?: boolean; }
type GraphTab = 'ACCELEROMETER' | 'GYROSCOPE' | 'COMBINED';
type Sample = { x: number; y: number; z: number };

const fmt = (value: number, decimals = 2) => `${value >= 0 ? '+' : ''}${value.toFixed(decimals)}`;

function pathFor(samples: Sample[], axis: keyof Sample, min: number, max: number) {
  if (samples.length < 2) return '';
  const span = Math.max(max - min, 0.001);
  return samples.map((sample, index) => {
    const x = (index / (samples.length - 1)) * 100;
    const y = 94 - ((sample[axis] - min) / span) * 88;
    return `${index === 0 ? 'M' : 'L'}${x.toFixed(1)} ${Math.max(4, Math.min(96, y)).toFixed(1)}`;
  }).join(' ');
}

export const MPU6050Panel: React.FC<MPU6050PanelProps> = ({ imuData, dataIsSimulated = false }) => {
  const [activeTab, setActiveTab] = useState<GraphTab>('ACCELEROMETER');
  const [accelHistory, setAccelHistory] = useState<Sample[]>([]);
  const [gyroHistory, setGyroHistory] = useState<Sample[]>([]);

  useEffect(() => {
    if (!imuData) return;
    // Telemetry is an external stream; retain a bounded history for the real-data graph.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setAccelHistory((history) => [...history, { x: imuData.ax, y: imuData.ay, z: imuData.az }].slice(-40));
    setGyroHistory((history) => [...history, { x: imuData.gx, y: imuData.gy, z: imuData.gz }].slice(-40));
  }, [imuData]);

  const row = (axis: string, value: number, color: string) => (
    <div className="flex justify-between items-center bg-black/40 px-2.5 py-1 rounded border border-white/5">
      <span className={`${color} font-bold`}>{axis}</span><span className="text-white font-semibold">{fmt(value)}</span>
    </div>
  );
  const samples = activeTab === 'GYROSCOPE' ? gyroHistory : accelHistory;
  const min = samples.length ? Math.min(...samples.flatMap((sample) => Object.values(sample))) : 0;
  const max = samples.length ? Math.max(...samples.flatMap((sample) => Object.values(sample))) : 1;

  return (
    <div id="mpu6050-imu-panel" className="glass-panel rounded-xl p-5 flex flex-col gap-4 border border-[#a3e635]/20 shadow-[0_4px_30px_rgba(0,0,0,0.3)] bg-[#0e1013]/90 backdrop-blur-md">
      <div className="flex items-center justify-between border-b border-white/10 pb-3">
        <div className="flex items-center gap-2"><Activity className="w-4 h-4 text-[#a3e635]" /><span className="font-['Space_Mono'] text-xs font-bold text-white tracking-widest">MPU6050 - 6-AXIS IMU</span></div>
        <div className="flex items-center gap-2"><span className={`w-2 h-2 rounded-full ${imuData && !dataIsSimulated ? 'bg-[#a3e635] animate-pulse' : 'bg-amber-300'}`} /><span className={`font-['Space_Mono'] text-[10px] font-bold tracking-wider ${imuData && !dataIsSimulated ? 'text-[#a3e635]' : 'text-amber-300'}`}>{!imuData ? 'NO LIVE DATA' : dataIsSimulated ? 'SIMULATED DATA' : 'RAW LIVE DATA'}</span></div>
      </div>

      {!imuData ? <div className="rounded-lg border border-amber-300/20 bg-amber-300/5 p-4 text-center"><p className="font-['Space_Mono'] text-xs font-bold text-amber-200">IMU DATA UNAVAILABLE</p><p className="font-['Inter'] text-xs text-white/50 mt-2">Waiting for a live MPU6050 telemetry reading. No sensor values are being estimated.</p></div> : <>
        <div className="grid grid-cols-2 gap-4">
          <div className="flex flex-col gap-1.5"><div className="text-[10px] font-['Space_Mono'] font-bold text-[#c2cab0] opacity-80 border-b border-white/10 pb-1 flex justify-between"><span>ACCELEROMETER</span><span className="font-normal text-white/50">(m/s²)</span></div><div className="font-['Space_Mono'] text-xs flex flex-col gap-1">{row('X', imuData.ax, 'text-[#a3e635]')}{row('Y', imuData.ay, 'text-[#a3e635]')}{row('Z', imuData.az, 'text-[#a3e635]')}</div></div>
          <div className="flex flex-col gap-1.5"><div className="text-[10px] font-['Space_Mono'] font-bold text-[#c2cab0] opacity-80 border-b border-white/10 pb-1 flex justify-between"><span>GYROSCOPE</span><span className="font-normal text-white/50">(rad/s)</span></div><div className="font-['Space_Mono'] text-xs flex flex-col gap-1">{row('X', imuData.gx, 'text-[#5de6ff]')}{row('Y', imuData.gy, 'text-[#5de6ff]')}{row('Z', imuData.gz, 'text-[#5de6ff]')}</div></div>
        </div>
        {typeof imuData.temperature_c === 'number' && <div className="font-['Space_Mono'] text-xs text-white/70">SENSOR TEMPERATURE: <span className="text-white font-bold">{imuData.temperature_c.toFixed(1)} °C</span></div>}

        <div className="flex flex-col gap-2.5"><div className="flex gap-1.5">{(['ACCELEROMETER', 'GYROSCOPE', 'COMBINED'] as GraphTab[]).map((tab) => <button key={tab} onClick={() => setActiveTab(tab)} className={`flex-1 text-[10px] font-['Space_Mono'] font-bold py-1.5 px-2 rounded ${activeTab === tab ? 'bg-[#a3e635]/20 text-[#ccff80] border border-[#a3e635]/60' : 'bg-black/40 text-white/60 border border-white/10'}`}>{tab}</button>)}</div>
          <div className="relative w-full h-32 bg-black/60 rounded-lg border border-white/15 overflow-hidden graph-grid"><svg className="absolute inset-0 w-full h-full" preserveAspectRatio="none" viewBox="0 0 100 100"><line x1="0" y1="50" x2="100" y2="50" stroke="rgba(255,255,255,0.1)" strokeDasharray="2,2" />{(activeTab === 'ACCELEROMETER' || activeTab === 'COMBINED') && <path d={pathFor(accelHistory, 'x', min, max)} fill="none" stroke="#a3e635" strokeWidth="1.6" />}{(activeTab === 'ACCELEROMETER' || activeTab === 'GYROSCOPE' || activeTab === 'COMBINED') && <path d={pathFor(activeTab === 'GYROSCOPE' ? gyroHistory : accelHistory, 'y', min, max)} fill="none" stroke="#5de6ff" strokeWidth="1.6" />}{(activeTab === 'GYROSCOPE' || activeTab === 'COMBINED') && <path d={pathFor(activeTab === 'GYROSCOPE' ? gyroHistory : accelHistory, 'z', min, max)} fill="none" stroke="#ffb4ab" strokeWidth="1.6" />}</svg><span className="absolute bottom-2 left-2 font-['Space_Mono'] text-[9px] text-white/40">LIVE SAMPLE HISTORY</span></div>
        </div>
        <div className="flex items-center justify-between p-3.5 bg-black/30 rounded-xl border border-white/10"><div><span className="text-[10px] font-['Space_Mono'] font-bold text-[#c2cab0] tracking-wider">ORIENTATION</span><p className="font-['Space_Mono'] text-xs text-white/50 mt-1">Unavailable: calibration and sensor fusion are not implemented.</p></div><div className="relative w-20 h-20 mr-2 flex items-center justify-center border border-white/10 rounded-full"><span className="font-['Space_Mono'] text-[9px] text-white/40">RAW ONLY</span></div></div>
      </>}
    </div>
  );
};
