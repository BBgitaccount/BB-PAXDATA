// src/bb_paxdata/interfaces/web/src/pages/WorldMap/components/MapProjectionSwitcher.tsx

import type React from 'react';

type ProjectionType = 'naturalEarth' | 'mercator' | 'orthographic';

interface MapProjectionSwitcherProps {
  currentProjection: ProjectionType;
  onChangeProjection: (projection: ProjectionType) => void;
}

export const MapProjectionSwitcher: React.FC<MapProjectionSwitcherProps> = ({
  currentProjection,
  onChangeProjection,
}) => {
  const buttons: { label: string; value: ProjectionType }[] = [
    { label: 'Globe', value: 'orthographic' },
    { label: 'Flat', value: 'naturalEarth' },
    { label: 'Regional', value: 'mercator' },
  ];

  return (
    <div
      className="absolute top-2 right-2 bg-carbon-900/90 border border-carbon-700/80 flex gap-0.5 shadow-xl backdrop-blur-md z-10 pointer-events-auto"
      style={{
        padding: 'clamp(3px, 0.4vw, 6px)',
        fontFamily: "'JetBrains Mono', 'Space Mono', monospace",
        fontSize: 'clamp(8px, 0.7vw, 10px)',
      }}
    >
      {buttons.map((btn) => {
        const isActive = currentProjection === btn.value;
        return (
          <button
            key={btn.value}
            type="button"
            onClick={() => onChangeProjection(btn.value)}
            className={`font-semibold tracking-wider transition-all duration-200 ${
              isActive
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'text-carbon-400 hover:text-carbon-100 hover:bg-carbon-800'
            }`}
            style={{
              padding: 'clamp(2px, 0.3vw, 4px) clamp(6px, 0.8vw, 12px)',
            }}
          >
            {btn.label.toUpperCase()}
          </button>
        );
      })}
    </div>
  );
};
