import React, { useEffect, useState } from 'react';
import type { GasSensorData } from '../types';

interface CO2SensorPanelProps {
  gasData: GasSensorData;
}

export const CO2SensorPanel: React.FC<CO2SensorPanelProps> = ({ gasData }) => {
  // 7 historical bar heights matching screenshot
  const [barHeights, setBarHeights] = useState<number[]>([28, 36, 22, 58, 86, 68, 54]);

  useEffect(() => {
    const interval = setInterval(() => {
      setBarHeights((prev) => {
        const nextVal = Math.floor(30 + Math.random() * 55);
        return [...prev.slice(1), nextVal];
      });
    }, 1800);

    return () => clearInterval(interval);
  }, []);

  return (
    <div
      id="co2-sensor-panel"
      className="bg-[#141619] rounded-xl p-4 sm:p-5 flex flex-col gap-3 border border-white/10 shadow-lg"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="font-['Space_Mono'] text-xs font-bold text-[#c2cab0] tracking-widest uppercase">
          CO2 SENSOR
        </span>
        <div className="w-2 h-2 rounded-full bg-[#a3e635] shadow-[0_0_8px_#a3e635]" />
      </div>

      {/* Main Measurement Readout: 412 PPM */}
      <div className="flex items-baseline gap-2">
        <span className="font-['Space_Mono'] text-3xl sm:text-4xl font-bold text-[#5de6ff] tracking-tight">
          {gasData.co2Ppm}
        </span>
        <span className="font-['Space_Mono'] text-xs text-[#5de6ff]/80 font-bold uppercase tracking-wider">
          PPM
        </span>
      </div>

      {/* Exactly 7 Cyan Histogram Bars */}
      <div className="w-full h-8 flex items-end gap-1.5 pt-1">
        {barHeights.map((val, idx) => (
          <div
            key={idx}
            className="flex-1 bg-[#5de6ff]/80 hover:bg-[#5de6ff] rounded-t-sm transition-all duration-500"
            style={{
              height: `${val}%`,
              boxShadow: idx === barHeights.length - 1 ? '0 0 8px rgba(93, 230, 255, 0.6)' : 'none'
            }}
          />
        ))}
      </div>
    </div>
  );
};
