// src/bb_paxdata/interfaces/web/src/pages/WorldMap/components/MapLegend.tsx

import type React from 'react';

export const MapLegend: React.FC = () => {
  return (
    <div
      className="absolute bottom-4 left-4 bg-carbon-900/95 border border-carbon-700/80 p-4 w-72 shadow-2xl backdrop-blur-md z-10 pointer-events-auto"
      style={{
        fontFamily: "'JetBrains Mono', 'Space Mono', monospace",
        fontSize: '10px',
      }}
    >
      <div className="space-y-4">
        {/* Sentiment Scale */}
        <div>
          <div className="text-carbon-400 font-semibold mb-2 uppercase tracking-wider">
            SENTIMENT SKALASI
          </div>
          <div className="w-full h-3.5 bg-gradient-to-r from-[#7f1d1d] via-[#1e293b] to-[#064e3b] border border-carbon-800" />
          <div className="flex justify-between text-[9px] text-carbon-400 mt-1 font-mono">
            <span>-1.0</span>
            <span>0.0</span>
            <span>+1.0</span>
          </div>
        </div>

        {/* Relationship Types */}
        <div>
          <div className="text-carbon-400 font-semibold mb-2 uppercase tracking-wider">
            İLİŞKİ TİPLERİ
          </div>
          <div className="grid grid-cols-2 gap-y-1.5 gap-x-2 text-[10px] text-carbon-300 font-mono">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-[#10b981] inline-block" />
              <span>ALLY</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-[#3b82f6] inline-block" />
              <span>PARTNER</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-[#6b7280] inline-block" />
              <span>NEUTRAL</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-[#f59e0b] inline-block" />
              <span>CAUTIOUS</span>
            </div>
            <div className="flex items-center gap-1.5 col-span-2">
              <span className="w-2 h-2 rounded-full bg-[#ef4444] inline-block animate-pulse" />
              <span>ADVERSARY</span>
            </div>
          </div>
        </div>

        {/* Bubble size indicator */}
        <div>
          <div className="text-carbon-400 font-semibold mb-2 uppercase tracking-wider">
            BUBBLE BOYUTU = ETKİLEŞİM
          </div>
          <div className="flex items-center justify-between text-[9px] text-carbon-400 mt-1 font-mono pr-4">
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full border border-carbon-500 bg-carbon-700 inline-block" />
              <span>az</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full border border-carbon-500 bg-carbon-700 inline-block" />
              <span>orta</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-5 h-5 rounded-full border border-carbon-500 bg-carbon-700 inline-block" />
              <span>çok</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
