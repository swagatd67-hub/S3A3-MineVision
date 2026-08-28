import React from 'react';
import { 
  BarChart2, 
  Map, 
  HelpCircle 
} from 'lucide-react';
import { sounds } from '../utils/audio';

export type ActiveNavTab = 'telemetry' | 'network-mapping' | 'help';

interface SideNavBarProps {
  activeTab: ActiveNavTab;
  onSelectTab: (tab: ActiveNavTab) => void;
  robotMode: string;
}

export const SideNavBar: React.FC<SideNavBarProps> = ({
  activeTab,
  onSelectTab,
  robotMode,
}) => {
  return (
    <aside 
      id="side-nav-bar"
      className="fixed left-0 top-16 h-[calc(100vh-64px)] z-40 flex flex-col justify-between w-16 lg:w-64 bg-[#141619] border-r border-white/10 shadow-2xl transition-all duration-300"
    >
      {/* Top Section: Navigation Header & Tabs */}
      <div className="flex flex-col">
        {/* Profile / System Info Header without robo icon */}
        <div className="p-4 lg:p-5 flex items-center border-b border-white/5">
          <div className="hidden lg:block overflow-hidden">
            <h2 className="font-['Poppins'] text-base font-bold text-white tracking-wide">
              ROV-01
            </h2>
            <p className="font-['Space_Mono'] text-xs text-white/50 truncate">
              {robotMode === 'DEEPSCAN' ? 'DeepScan Mode' : robotMode}
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="py-4 flex flex-col gap-2 px-3">
          {/* Tab 1: Telemetry */}
          <button
            id="nav-tab-telemetry"
            onClick={() => {
              sounds.playClick('tactile');
              onSelectTab('telemetry');
            }}
            className={`w-full flex items-center gap-3.5 px-3.5 py-2.5 rounded-lg text-left transition-all cursor-pointer ${
              activeTab === 'telemetry'
                ? 'bg-[#a3e635] text-[#121f00] font-bold shadow-[0_0_12px_rgba(163,230,53,0.3)]'
                : 'text-white/70 hover:bg-white/5 hover:text-white'
            }`}
            title="Telemetry Dashboard"
          >
            <BarChart2 className={`w-4 h-4 flex-shrink-0 ${activeTab === 'telemetry' ? 'text-[#121f00]' : 'text-white/70'}`} />
            <span className="font-['Space_Mono'] text-xs tracking-wide hidden lg:block">
              Telemetry
            </span>
          </button>

          {/* Tab 2: Network Mapping */}
          <button
            id="nav-tab-network-mapping"
            onClick={() => {
              sounds.playClick('tactile');
              onSelectTab('network-mapping');
            }}
            className={`w-full flex items-center gap-3.5 px-3.5 py-2.5 rounded-lg text-left transition-all cursor-pointer ${
              activeTab === 'network-mapping'
                ? 'bg-[#a3e635] text-[#121f00] font-bold shadow-[0_0_12px_rgba(163,230,53,0.3)]'
                : 'text-white/70 hover:bg-white/5 hover:text-white'
            }`}
            title="Network Mapping"
          >
            <Map className={`w-4 h-4 flex-shrink-0 ${activeTab === 'network-mapping' ? 'text-[#121f00]' : 'text-white/70'}`} />
            <span className="font-['Space_Mono'] text-xs tracking-wide hidden lg:block">
              Network Mapping
            </span>
          </button>
        </div>
      </div>

      {/* Bottom Section: Help */}
      <div className="p-3 border-t border-white/5">
        <button
          id="nav-tab-help"
          onClick={() => {
            sounds.playClick('tactile');
            onSelectTab('help');
          }}
          className={`w-full flex items-center gap-3.5 px-3.5 py-2.5 rounded-lg text-left transition-all cursor-pointer ${
            activeTab === 'help'
              ? 'bg-[#a3e635] text-[#121f00] font-bold'
              : 'text-white/50 hover:bg-white/5 hover:text-white'
          }`}
          title="Help & Info"
        >
          <HelpCircle className="w-4 h-4 flex-shrink-0" />
          <span className="font-['Space_Mono'] text-xs tracking-wide hidden lg:block">
            Help
          </span>
        </button>
      </div>
    </aside>
  );
};
