import React from 'react';

interface GeoPanelProps {
  title: string;
  badge?: string;
  className?: string;
  children: React.ReactNode;
}

export const GeoPanel: React.FC<GeoPanelProps> = ({ title, badge, className = '', children }) => {
  return (
    <div className={`geoint-panel ${className}`}>
      <div className="geoint-panel-content">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--geoint-border)]">
          <div className="flex items-center gap-3">
            <h3 className="geoint-section-label !mb-0 !border-l-0 !pl-0">{title}</h3>
          </div>
          {badge && (
            <span
              className={`px-2 py-0.5 text-[9px] font-mono uppercase tracking-wider ${
                badge === 'LIVE' ? 'geoint-badge-live' : ''
              }`}
              style={{
                backgroundColor:
                  badge === 'LIVE'
                    ? 'var(--sentiment-ally)'
                    : badge === 'WARNING'
                      ? 'var(--signal-warning)'
                      : 'var(--geoint-muted)',
                color: badge === 'LIVE' || badge === 'WARNING' ? '#000' : 'var(--text-primary)',
              }}
            >
              {badge}
            </span>
          )}
        </div>
        {/* Content */}
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
};
