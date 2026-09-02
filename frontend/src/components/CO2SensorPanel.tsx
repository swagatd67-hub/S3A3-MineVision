import React, { useEffect, useState } from 'react';
import type { GasSensorData } from '../types';

interface CO2SensorPanelProps {
  gasData: GasSensorData;
}

export const CO2SensorPanel: React.FC<CO2SensorPanelProps> = ({ gasData }) => {
  // Historical bar heights (0-100)
  const [barHeights, setBarHeights] = useState<number[]>([28, 36, 22, 58, 86, 68, 54]);

  useEffect(() => {
    if (gasData.history && gasData.history.length > 0) {
      setBarHeights(gasData.history.slice(-7));
      return;
    }
    if (gasData.historyPpm && gasData.historyPpm.length > 0) {
      setBarHeights(gasData.historyPpm.slice(-7).map((v) => Math.min(100, Math.max(0, Math.round(v / 10)))));
      return;
    }
  }, [gasData.history, gasData.historyPpm]);

  const displayVal = typeof gasData.value === 'number'
    ? Math.round(gasData.value)
    : Math.round((gasData.co2Ppm ?? 250) / 10);

  const status = gasData.status || 'NORMAL';

  let statusBadgeStyle = 'bg-[#a3e635]/10 border-[#a3e635]/30 text-[#a3e635]';
  let dotStyle = 'bg-[#a3e635] shadow-[0_0_8px_#a3e635]';

  if (status === 'ELEVATED') {
    statusBadgeStyle = 'bg-amber-400/10 border-amber-400/30 text-amber-400';
    dotStyle = 'bg-amber-400 shadow-[0_0_8px_#facc15]';
  } else if (status === 'HIGH') {
    statusBadgeStyle = 'bg-orange-400/10 border-orange-400/30 text-orange-400';
    dotStyle = 'bg-orange-400 shadow-[0_0_8px_#fb923c]';
  } else if (status === 'CRITICAL' || status === ('WARNING' as string)) {
    statusBadgeStyle = 'bg-[#ff5449]/10 border-[#ff5449]/30 text-[#ff5449]';
    dotStyle = 'bg-[#ff5449] shadow-[0_0_8px_#ff5449]';
  }

  return (
    <div
      id="co2-sensor-panel"
      className="bg-[#141619] rounded-xl p-4 sm:p-5 flex flex-col gap-3 border border-white/10 shadow-lg"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="font-['Space_Mono'] text-xs font-bold text-[#c2cab0] tracking-widest uppercase">
          GAS LEVEL
        </span>
        <div className={`w-2 h-2 rounded-full ${dotStyle}`} />
      </div>

      {/* Main Measurement Readout: 0-100 Index & Status */}
      <div className="flex items-baseline justify-between gap-2">
        <div className="flex items-baseline gap-2">
          <span className="font-['Space_Mono'] text-3xl sm:text-4xl font-bold text-[#5de6ff] tracking-tight">
            {displayVal}
          </span>
          <span className="font-['Space_Mono'] text-xs text-[#5de6ff]/80 font-bold uppercase tracking-wider">
            INDEX
          </span>
        </div>
        <span className={`font-['Space_Mono'] text-xs font-bold px-2 py-0.5 rounded border uppercase ${statusBadgeStyle}`}>
          {status}
        </span>
      </div>

      {/* Histogram Bars */}
      <div className="w-full h-8 flex items-end gap-1.5 pt-1">
        {barHeights.map((val, idx) => (
          <div
            key={idx}
            className="flex-1 bg-[#5de6ff]/80 hover:bg-[#5de6ff] rounded-t-sm transition-all duration-500"
            style={{
              height: `${Math.min(100, Math.max(10, val))}%`,
              boxShadow: idx === barHeights.length - 1 ? '0 0 8px rgba(93, 230, 255, 0.6)' : 'none'
            }}
          />
        ))}
      </div>
    </div>
  );
};

export const GasSensorPanel = CO2SensorPanel;

