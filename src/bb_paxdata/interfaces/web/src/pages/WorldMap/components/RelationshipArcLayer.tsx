// src/bb_paxdata/interfaces/web/src/pages/WorldMap/components/RelationshipArcLayer.tsx

import type React from 'react';
import { Line } from 'react-simple-maps';
import { sentimentToColor } from '../../../utils/visualizationHelpers';

interface CountryConnection {
  from_country: string;
  to_country: string;
  from_lat: number;
  from_lon: number;
  to_lat: number;
  to_lon: number;
  avg_sentiment: number;
  interaction_count: number;
  relationship_type: string;
  affinity_score: number;
}

interface RelationshipArcLayerProps {
  connections: CountryConnection[];
  highlightedCountry: string | null;
  selectedConnection: CountryConnection | null;
  setSelectedConnection: (conn: CountryConnection | null) => void;
}

export const RelationshipArcLayer: React.FC<RelationshipArcLayerProps> = ({
  connections,
  highlightedCountry,
  selectedConnection,
  setSelectedConnection,
}) => {
  // Filters out adversaries since they are handled separately by Conflict Hotspots layer
  const activeConnections = connections.filter((conn) => conn.relationship_type !== 'ADVERSARY');

  return (
    <g>
      {activeConnections.map((conn, idx) => {
        const isSelected = selectedConnection === conn;
        // Apply isolation/highlighting logic
        let opacity = isSelected ? 1.0 : 0.6;
        if (highlightedCountry) {
          const isRelated =
            conn.from_country === highlightedCountry || conn.to_country === highlightedCountry;
          opacity = isRelated ? 0.9 : 0.15;
        }

        const color = sentimentToColor(conn.avg_sentiment);
        // Map interaction count to stroke width
        const strokeWidth = Math.min(Math.max(conn.interaction_count / 5, 1.5), 5);

        return (
          <Line
            key={`arc-${idx}`}
            from={[conn.from_lon, conn.from_lat]}
            to={[conn.to_lon, conn.to_lat]}
            stroke={color}
            strokeWidth={isSelected ? strokeWidth + 1.5 : strokeWidth}
            strokeOpacity={opacity}
            style={{ outline: 'none' }}
            className="cursor-pointer transition-all duration-200"
            onClick={() => setSelectedConnection(conn)}
          />
        );
      })}
    </g>
  );
};
