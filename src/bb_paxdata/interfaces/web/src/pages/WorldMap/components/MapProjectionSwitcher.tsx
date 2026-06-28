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
      className="absolute top-4 right-4 bg-carbon-900/90 border border-carbon-700/80 p-1 flex gap-1 shadow-xl backdrop-blur-md z-10 pointer-events-auto"
      style={{
        fontFamily: "'JetBrains Mono', 'Space Mono', monospace",
        fontSize: '10px',
      }}
    >
      {buttons.map((btn) => {
        const isActive = currentProjection === btn.value;
        return (
          <button
            key={btn.value}
            type="button"
            onClick={() => onChangeProjection(btn.value)}
            className={`px-3 py-1 text-2xs font-semibold tracking-wider transition-all duration-200 ${
              isActive
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'text-carbon-400 hover:text-carbon-100 hover:bg-carbon-800'
            }`}
          >
            {btn.label.toUpperCase()}
          </button>
        );
      })}
    </div>
  );
};
