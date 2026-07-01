import { AnimatePresence, motion } from 'framer-motion';
import { Maximize2, Minimize2, PanelLeftClose, PanelLeftOpen, X } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { useVizStore } from '../../store/vizStore';

interface WorldMapLayoutProps {
  header: React.ReactNode;
  kpiRow: React.ReactNode;
  tabBar: React.ReactNode;
  sidePanelContent: React.ReactNode;
  children: React.ReactNode;
  countryDrawer: React.ReactNode;
}

export const WorldMapLayout: React.FC<WorldMapLayoutProps> = ({
  header,
  kpiRow,
  tabBar,
  sidePanelContent,
  children,
  countryDrawer,
}) => {
  const selectedCountry = useVizStore((state) => state.filters.selectedCountry);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [sidePanelVisible, setSidePanelVisible] = useState(true);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // F: fullscreen toggle for main content
      if (e.key === 'f' || e.key === 'F') {
        setIsFullscreen((prev) => !prev);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <div
      className="h-screen w-screen flex overflow-hidden animate-[fade-in-up_300ms_ease-out_both]"
      style={{ fontSize: 'clamp(10px, 1.1vw, 14px)' }}
    >
      {/* Main Map Area */}
      <motion.div
        initial={{ x: 0 }}
        animate={{ x: selectedCountry ? '-30vw' : 0 }}
        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
        className="flex-1 relative flex flex-col min-w-0"
      >
        {/* Header */}
        <div className="flex-shrink-0">{header}</div>

        {/* KPI Row */}
        <div className="flex-shrink-0">{kpiRow}</div>

        {/* Map Container */}
        <div
          className="flex-1 bg-[var(--bg-secondary)] relative overflow-hidden h-full w-full"
          style={{ paddingTop: 'clamp(8px, 2vh, 16px)', paddingBottom: 'clamp(44px, 9vh, 72px)' }}
        >
          {children}
        </div>

        {/* Floating Command Bar - Bottom */}
        <div className="absolute bottom-1.5 sm:bottom-2 md:bottom-3 left-1.5 sm:left-2 md:left-3 right-1.5 sm:right-2 md:right-3 z-30">
          <div
            className="rounded p-2 sm:p-3 flex items-center justify-between gap-2"
            style={{
              backgroundColor: 'var(--geoint-deep)',
              border: 'var(--border-subtle)',
            }}
          >
            <div className="flex-1">{tabBar}</div>
            <div className="flex items-center gap-1 sm:gap-2">
              {/* Side Panel Toggle */}
              <button
                onClick={() => setSidePanelVisible(!sidePanelVisible)}
                className="p-1.5 sm:p-2 rounded transition-colors"
                style={{
                  backgroundColor: 'var(--geoint-deep)',
                  border: 'var(--border-subtle)',
                  color: 'var(--text-tertiary)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--geoint-elevated)';
                  e.currentTarget.style.color = 'var(--text-primary)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--geoint-deep)';
                  e.currentTarget.style.color = 'var(--text-tertiary)';
                }}
                title={sidePanelVisible ? 'Paneli Gizle' : 'Paneli Göster'}
              >
                {sidePanelVisible ? (
                  <PanelLeftClose className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                ) : (
                  <PanelLeftOpen className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                )}
              </button>

              {/* Fullscreen Toggle */}
              <button
                onClick={() => setIsFullscreen(!isFullscreen)}
                className="p-1.5 sm:p-2 rounded transition-colors"
                style={{
                  backgroundColor: 'var(--geoint-deep)',
                  border: 'var(--border-subtle)',
                  color: 'var(--text-tertiary)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--geoint-elevated)';
                  e.currentTarget.style.color = 'var(--text-primary)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--geoint-deep)';
                  e.currentTarget.style.color = 'var(--text-tertiary)';
                }}
                title={isFullscreen ? 'Çıkış (F)' : 'Tam Ekran (F)'}
              >
                {isFullscreen ? (
                  <Minimize2 className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                ) : (
                  <Maximize2 className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                )}
              </button>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Side Panel */}
      <AnimatePresence>
        {sidePanelVisible && (
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className="w-[18vw] sm:w-[22vw] md:w-[26vw] lg:w-[300px] max-w-[360px] flex-shrink-0 flex flex-col overflow-hidden"
            style={{
              backgroundColor: 'var(--bg-secondary)',
              borderLeft: 'var(--border-subtle)',
            }}
          >
            {/* Panel Header */}
            <div
              className="px-3 sm:px-4 py-2 sm:py-3 flex-shrink-0"
              style={{ borderBottom: 'var(--border-subtle)' }}
            >
              <h3
                className="text-xs sm:text-sm font-semibold"
                style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}
              >
                Kontrol Paneli
              </h3>
            </div>

            {/* Panel Content */}
            <div className="flex-1 overflow-y-auto geoint-scroll px-3 sm:px-4 py-2 sm:py-3">
              {sidePanelContent}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Country Intelligence Drawer */}
      <AnimatePresence>
        {selectedCountry && (
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className="w-64 sm:w-[22rem] md:w-[26rem] lg:w-[30rem] flex-shrink-0 flex flex-col overflow-hidden"
            style={{
              backgroundColor: 'var(--bg-secondary)',
              borderLeft: 'var(--border-subtle)',
            }}
          >
            {/* Panel Header */}
            <div
              className="px-3 sm:px-4 py-2 sm:py-3 flex items-center justify-between flex-shrink-0"
              style={{ borderBottom: 'var(--border-subtle)' }}
            >
              <div className="flex items-center gap-2">
                <div
                  className="w-2 h-2 rounded-full"
                  style={{
                    backgroundColor: 'var(--signal-info)',
                  }}
                />
                <h3
                  className="text-xs sm:text-sm font-semibold"
                  style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}
                >
                  {selectedCountry}
                </h3>
              </div>
              <button
                onClick={() => {
                  const event = new CustomEvent('close-country-drawer');
                  window.dispatchEvent(event);
                }}
                className="p-1 rounded transition-colors"
                style={{ color: 'var(--text-tertiary)' }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = 'var(--text-primary)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = 'var(--text-tertiary)';
                }}
              >
                <X className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              </button>
            </div>

            {/* Panel Content */}
            <div className="flex-1 overflow-y-auto geoint-scroll px-3 sm:px-4 py-2 sm:py-3">
              {countryDrawer}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
