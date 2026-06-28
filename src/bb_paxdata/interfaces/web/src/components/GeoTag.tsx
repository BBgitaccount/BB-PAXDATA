import React from 'react';

type RelationshipType = 'ALLY' | 'PARTNER' | 'NEUTRAL' | 'CAUTIOUS' | 'ADVERSARY';

interface GeoTagProps {
  type: RelationshipType;
  outlined?: boolean;
  className?: string;
}

const TAG_CONFIG: Record<RelationshipType, { color: string; label: string }> = {
  ALLY: { color: 'var(--sentiment-ally)', label: 'ALLY' },
  PARTNER: { color: 'var(--sentiment-partner)', label: 'PARTNER' },
  NEUTRAL: { color: 'var(--sentiment-neutral)', label: 'NEUTRAL' },
  CAUTIOUS: { color: 'var(--sentiment-cautious)', label: 'CAUTIOUS' },
  ADVERSARY: { color: 'var(--sentiment-adversary)', label: 'ADVERSARY' },
};

export const GeoTag: React.FC<GeoTagProps> = ({ type, outlined = false, className = '' }) => {
  const config = TAG_CONFIG[type];

  return (
    <span
      className={`
        inline-flex items-center gap-1.5 px-2 py-1 text-[10px] font-mono font-semibold
        uppercase tracking-wider transition-all duration-150
        ${className}
      `}
      style={{
        backgroundColor: outlined ? 'transparent' : config.color,
        color: outlined ? config.color : type === 'NEUTRAL' ? '#fff' : '#000',
        border: outlined ? `1px solid ${config.color}` : 'none',
        boxShadow:
          !outlined && type === 'ADVERSARY'
            ? 'var(--glow-adversary)'
            : !outlined && type === 'ALLY'
              ? 'var(--glow-ally)'
              : !outlined && type === 'PARTNER'
                ? 'var(--glow-partner)'
                : 'none',
      }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full"
        style={{ backgroundColor: outlined ? config.color : type === 'NEUTRAL' ? '#fff' : '#000' }}
      />
      {config.label}
    </span>
  );
};
