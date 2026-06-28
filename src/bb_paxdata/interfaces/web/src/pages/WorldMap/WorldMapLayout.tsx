import { AnimatePresence, motion } from 'framer-motion';
import { ChevronLeft, Maximize2, Minimize2, PanelLeft, X } from 'lucide-react';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useVizStore } from '../../store/vizStore';

interface WorldMapLayoutProps {
  header: React.ReactNode;
  kpiRow: React.ReactNode;
  tabBar: React.ReactNode;
  children: React.ReactNode;
  sidePanelContent: React.ReactNode;
}

export const WorldMapLayout: React.FC<WorldMapLayoutProps> = ({
  header,
  kpiRow,
  tabBar: _tabBar,
  children,
  sidePanelContent,
}) => {
  const { panelWidth, isSidePanelOpen, setPanelWidth, toggleSidePanel, activeTab, setActiveTab } =
    useVizStore();

  const [isResizing, setIsResizing] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [screenSize, setScreenSize] = useState<'desktop' | 'tablet' | 'mobile'>('desktop');
  const resizeHandleRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Detect screen size
  useEffect(() => {
    const handleResize = () => {
      const width = window.innerWidth;
      if (width < 768) {
        setScreenSize('mobile');
      } else if (width < 1280) {
        setScreenSize('tablet');
      } else {
        setScreenSize('desktop');
      }
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Handle resize via drag
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing || !containerRef.current) return;

      const containerRect = containerRef.current.getBoundingClientRect();
      const newWidth = containerRect.right - e.clientX;

      setPanelWidth(newWidth);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing, setPanelWidth]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Tab shortcuts: 1-6
      if (e.key >= '1' && e.key <= '6') {
        const tabs: Array<'choropleth' | 'network' | 'chord' | 'sankey' | 'heatmap' | 'timeline'> =
          ['choropleth', 'network', 'chord', 'sankey', 'heatmap', 'timeline'];
        const tabIndex = parseInt(e.key) - 1;
        setActiveTab(tabs[tabIndex]);
      }

      // Escape: close drawer, clear highlight
      if (e.key === 'Escape') {
        toggleSidePanel(false);
      }

      // F: fullscreen toggle for main content
      if (e.key === 'f' || e.key === 'F') {
        setIsFullscreen((prev) => !prev);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [setActiveTab, toggleSidePanel]);

  const tabs = [
    { id: 'choropleth', label: '🌍 Harita', key: '1' },
    { id: 'network', label: '🔗 Ağ Grafiği', key: '2' },
    { id: 'chord', label: '🎯 Chord', key: '3' },
    { id: 'sankey', label: '⟶ Sankey', key: '4' },
    { id: 'heatmap', label: '🔥 Isı Haritası', key: '5' },
    { id: 'timeline', label: '⏱ Timeline', key: '6' },
  ] as const;

  return (
    <div
      ref={containerRef}
      className="flex flex-col h-screen overflow-hidden"
      style={{ backgroundColor: 'var(--geoint-void)' }}
    >
      {/* Header Section */}
      <div className="flex-shrink-0">
        {header}
        {kpiRow}
      </div>

      {/* Tab Bar */}
      <div
        className="flex-shrink-0 overflow-x-auto"
        style={{ borderBottom: 'var(--border-subtle)' }}
      >
        <div className="flex gap-1 px-4 py-2">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 text-sm font-medium rounded transition-colors whitespace-nowrap ${
                activeTab === tab.id ? '' : ''
              }`}
              style={{
                fontFamily: 'var(--font-label)',
                backgroundColor: activeTab === tab.id ? 'var(--geoint-elevated)' : 'transparent',
                color: activeTab === tab.id ? 'var(--text-primary)' : 'var(--text-tertiary)',
                border: activeTab === tab.id ? 'var(--border-subtle)' : '1px solid transparent',
              }}
              onMouseEnter={(e) => {
                if (activeTab !== tab.id) {
                  e.currentTarget.style.color = 'var(--text-secondary)';
                }
              }}
              onMouseLeave={(e) => {
                if (activeTab !== tab.id) {
                  e.currentTarget.style.color = 'var(--text-tertiary)';
                }
              }}
            >
              <span className="mr-2 opacity-50 text-xs">{tab.key}</span>
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* Main Visualization Area */}
        <motion.div
          className="flex-1 overflow-hidden relative"
          initial={false}
          animate={{
            width: isFullscreen
              ? '100%'
              : isSidePanelOpen
                ? `calc(100% - ${panelWidth}px)`
                : '100%',
          }}
          transition={{ duration: 0.2, ease: 'easeInOut' }}
        >
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18 }}
              className="h-full p-4"
            >
              {children}
            </motion.div>
          </AnimatePresence>

          {/* Fullscreen Toggle Button */}
          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="absolute top-4 right-4 p-2 rounded transition-colors z-10"
            style={{
              backgroundColor: 'var(--geoint-base)',
              border: 'var(--border-subtle)',
              color: 'var(--text-tertiary)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'var(--geoint-elevated)';
              e.currentTarget.style.color = 'var(--text-primary)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'var(--geoint-base)';
              e.currentTarget.style.color = 'var(--text-tertiary)';
            }}
            title={isFullscreen ? 'Çıkış (F)' : 'Tam Ekran (F)'}
          >
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </motion.div>

        {/* Resize Handle (Desktop only) */}
        <AnimatePresence>
          {isSidePanelOpen && !isFullscreen && screenSize === 'desktop' && (
            <motion.div
              ref={resizeHandleRef}
              initial={{ width: 0 }}
              animate={{ width: 4 }}
              exit={{ width: 0 }}
              className="flex-shrink-0 cursor-col-resize hover:bg-blue-500/20 transition-colors z-20"
              style={{ backgroundColor: isResizing ? 'var(--signal-info)' : 'transparent' }}
              onMouseDown={handleMouseDown}
            />
          )}
        </AnimatePresence>

        {/* Side Panel - Desktop/Tablet (right side) */}
        <AnimatePresence>
          {isSidePanelOpen && !isFullscreen && screenSize !== 'mobile' && (
            <motion.div
              initial={{ width: 0, opacity: 0 }}
              animate={{
                width: screenSize === 'desktop' ? panelWidth : 400,
                opacity: 1,
                x: screenSize === 'tablet' ? 0 : 0,
              }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.2, ease: 'easeInOut' }}
              className={`flex-shrink-0 overflow-hidden ${screenSize === 'tablet' ? 'absolute right-0 top-0 h-full z-30 shadow-2xl' : ''}`}
              style={{
                backgroundColor: 'var(--geoint-base)',
                borderLeft: screenSize === 'desktop' ? 'var(--border-subtle)' : 'none',
                minWidth: screenSize === 'desktop' ? '320px' : '320px',
                maxWidth: screenSize === 'desktop' ? '600px' : '500px',
              }}
            >
              <div className="h-full flex flex-col">
                {/* Side Panel Header */}
                <div
                  className="flex items-center justify-between px-4 py-3"
                  style={{ borderBottom: 'var(--border-subtle)' }}
                >
                  <h3
                    className="text-sm font-semibold"
                    style={{ fontFamily: 'var(--font-label)', color: 'var(--text-primary)' }}
                  >
                    Analiz Paneli
                  </h3>
                  <button
                    onClick={() => toggleSidePanel(false)}
                    className="p-1 rounded transition-colors"
                    style={{ color: 'var(--text-tertiary)' }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-primary)')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-tertiary)')}
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                {/* Side Panel Content */}
                <div className="flex-1 overflow-y-auto geoint-scroll">{sidePanelContent}</div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Side Panel - Mobile (Bottom Sheet) */}
        <AnimatePresence>
          {isSidePanelOpen && !isFullscreen && screenSize === 'mobile' && (
            <>
              {/* Backdrop */}
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="absolute inset-0 bg-black/50 z-30"
                onClick={() => toggleSidePanel(false)}
              />

              {/* Bottom Sheet */}
              <motion.div
                initial={{ y: '100%' }}
                animate={{ y: 0 }}
                exit={{ y: '100%' }}
                transition={{ type: 'spring', damping: 25, stiffness: 300 }}
                className="absolute bottom-0 left-0 right-0 z-40 rounded-t-2xl shadow-2xl"
                style={{
                  backgroundColor: 'var(--geoint-base)',
                  height: '56%',
                  borderTop: 'var(--border-subtle)',
                }}
              >
                <div className="h-full flex flex-col">
                  {/* Drag Handle */}
                  <div className="flex justify-center pt-2 pb-1">
                    <div
                      className="w-12 h-1.5 rounded-full"
                      style={{ backgroundColor: 'var(--geoint-border)' }}
                    />
                  </div>

                  {/* Side Panel Header */}
                  <div
                    className="flex items-center justify-between px-4 py-3"
                    style={{ borderBottom: 'var(--border-subtle)' }}
                  >
                    <h3
                      className="text-sm font-semibold"
                      style={{ fontFamily: 'var(--font-label)', color: 'var(--text-primary)' }}
                    >
                      Analiz Paneli
                    </h3>
                    <button
                      onClick={() => toggleSidePanel(false)}
                      className="p-1 rounded transition-colors"
                      style={{ color: 'var(--text-tertiary)' }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-primary)')}
                      onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-tertiary)')}
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>

                  {/* Side Panel Content */}
                  <div className="flex-1 overflow-y-auto geoint-scroll">{sidePanelContent}</div>
                </div>
              </motion.div>
            </>
          )}
        </AnimatePresence>

        {/* Side Panel Toggle Button (when closed - desktop/tablet) */}
        {(!isSidePanelOpen || screenSize === 'mobile') && !isFullscreen && (
          <button
            onClick={() => toggleSidePanel(true)}
            className={`p-2 rounded transition-colors z-10 ${screenSize === 'mobile' ? 'absolute bottom-4 right-4' : 'absolute right-4 top-1/2 -translate-y-1/2'}`}
            style={{
              backgroundColor: 'var(--geoint-base)',
              border: 'var(--border-subtle)',
              color: 'var(--text-tertiary)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'var(--geoint-elevated)';
              e.currentTarget.style.color = 'var(--text-primary)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'var(--geoint-base)';
              e.currentTarget.style.color = 'var(--text-tertiary)';
            }}
          >
            {screenSize === 'mobile' ? (
              <PanelLeft className="w-5 h-5" />
            ) : (
              <ChevronLeft className="w-4 h-4" />
            )}
          </button>
        )}
      </div>
    </div>
  );
};
