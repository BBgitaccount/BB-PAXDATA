import React from 'react';
import { GeoPanel } from './GeoPanel';
import { GeoButton } from './GeoButton';
import { GeoTag } from './GeoTag';
import { SentimentBar } from './SentimentBar';

export const GeoComponentDemo: React.FC = () => {
  return (
    <div
      className="p-8 space-y-8"
      style={{ backgroundColor: 'var(--geoint-void)', minHeight: '100vh' }}
    >
      <div className="mb-8">
        <h1
          className="text-3xl font-bold mb-2"
          style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}
        >
          GEOINT Component Library Demo
        </h1>
        <p
          className="text-sm"
          style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}
        >
          Design System Components // NASA IRGC × Bloomberg Terminal × Palantir Gotham
        </p>
      </div>

      {/* GeoPanel Demo */}
      <div className="space-y-4">
        <h2
          className="text-xl font-semibold"
          style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}
        >
          GeoPanel
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <GeoPanel title="Basic Panel">
            <p style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
              This is a basic panel with scanline overlay effect.
            </p>
          </GeoPanel>
          <GeoPanel title="Panel with Badge" badge="LIVE">
            <p style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
              Panel with LIVE badge featuring pulse animation.
            </p>
          </GeoPanel>
          <GeoPanel title="Warning Panel" badge="WARNING">
            <p style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
              Panel with warning badge for alerts.
            </p>
          </GeoPanel>
        </div>
      </div>

      {/* GeoButton Demo */}
      <div className="space-y-4">
        <h2
          className="text-xl font-semibold"
          style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}
        >
          GeoButton
        </h2>
        <div
          className="flex flex-wrap gap-4 p-4"
          style={{ backgroundColor: 'var(--geoint-base)', border: 'var(--border-subtle)' }}
        >
          <GeoButton variant="primary">Primary</GeoButton>
          <GeoButton variant="secondary">Secondary</GeoButton>
          <GeoButton variant="danger">Danger</GeoButton>
          <GeoButton variant="ghost">Ghost</GeoButton>
          <GeoButton variant="primary" disabled>
            Disabled
          </GeoButton>
        </div>
      </div>

      {/* GeoTag Demo */}
      <div className="space-y-4">
        <h2
          className="text-xl font-semibold"
          style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}
        >
          GeoTag
        </h2>
        <div
          className="flex flex-wrap gap-4 p-4"
          style={{ backgroundColor: 'var(--geoint-base)', border: 'var(--border-subtle)' }}
        >
          <GeoTag type="ALLY" />
          <GeoTag type="PARTNER" />
          <GeoTag type="NEUTRAL" />
          <GeoTag type="CAUTIOUS" />
          <GeoTag type="ADVERSARY" />
          <div className="w-px" style={{ backgroundColor: 'var(--geoint-border)' }} />
          <GeoTag type="ALLY" outlined />
          <GeoTag type="PARTNER" outlined />
          <GeoTag type="NEUTRAL" outlined />
          <GeoTag type="CAUTIOUS" outlined />
          <GeoTag type="ADVERSARY" outlined />
        </div>
      </div>

      {/* SentimentBar Demo */}
      <div className="space-y-4">
        <h2
          className="text-xl font-semibold"
          style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}
        >
          SentimentBar
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <GeoPanel title="Strong Ally (+0.85)">
            <SentimentBar score={0.85} />
          </GeoPanel>
          <GeoPanel title="Moderate Partner (+0.45)">
            <SentimentBar score={0.45} />
          </GeoPanel>
          <GeoPanel title="Neutral (0.00)">
            <SentimentBar score={0.0} />
          </GeoPanel>
          <GeoPanel title="Cautious (-0.35)">
            <SentimentBar score={-0.35} />
          </GeoPanel>
          <GeoPanel title="Adversary (-0.75)">
            <SentimentBar score={-0.75} />
          </GeoPanel>
          <GeoPanel title="Extreme Adversary (-0.95)">
            <SentimentBar score={-0.95} />
          </GeoPanel>
        </div>
      </div>

      {/* Typography Demo */}
      <div className="space-y-4">
        <h2
          className="text-xl font-semibold"
          style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}
        >
          Typography
        </h2>
        <GeoPanel title="Font Families">
          <div className="space-y-4">
            <div>
              <div className="geoint-data-label">Display Font (Space Grotesk)</div>
              <div
                className="text-2xl font-bold"
                style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}
              >
                Dünya Haritası Analizi
              </div>
            </div>
            <div>
              <div className="geoint-data-label">Body Font (Inter)</div>
              <div
                className="text-base"
                style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}
              >
                Bu sistem diplomatik analistler için tasarlanmıştır.
              </div>
            </div>
            <div>
              <div className="geoint-data-label">Mono Font (JetBrains Mono)</div>
              <div
                className="text-base font-mono"
                style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-data)' }}
              >
                const affinityScore = 0.85;
              </div>
            </div>
            <div>
              <div className="geoint-data-label">Label Font (Space Mono)</div>
              <div
                className="text-xs font-mono uppercase tracking-wider"
                style={{ fontFamily: 'var(--font-label)', color: 'var(--text-tertiary)' }}
              >
                SENTIMENT ANALYSIS MODULE
              </div>
            </div>
          </div>
        </GeoPanel>
      </div>

      {/* Data Values Demo */}
      <div className="space-y-4">
        <h2
          className="text-xl font-semibold"
          style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}
        >
          Data Display
        </h2>
        <GeoPanel title="KPI Cards">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div
              className="text-center p-4"
              style={{ backgroundColor: 'var(--geoint-deep)', border: 'var(--border-subtle)' }}
            >
              <div className="geoint-data-label">Total Mentions</div>
              <div className="geoint-data-value">1,247</div>
            </div>
            <div
              className="text-center p-4"
              style={{ backgroundColor: 'var(--geoint-deep)', border: 'var(--border-subtle)' }}
            >
              <div className="geoint-data-label">Active Countries</div>
              <div className="geoint-data-value">42</div>
            </div>
            <div
              className="text-center p-4"
              style={{ backgroundColor: 'var(--geoint-deep)', border: 'var(--border-subtle)' }}
            >
              <div className="geoint-data-label">Avg Sentiment</div>
              <div className="geoint-data-value" style={{ color: 'var(--sentiment-ally)' }}>
                +0.23
              </div>
            </div>
            <div
              className="text-center p-4"
              style={{ backgroundColor: 'var(--geoint-deep)', border: 'var(--border-subtle)' }}
            >
              <div className="geoint-data-label">Risk Level</div>
              <div className="geoint-data-value" style={{ color: 'var(--sentiment-cautious)' }}>
                MED
              </div>
            </div>
          </div>
        </GeoPanel>
      </div>

      {/* Section Labels Demo */}
      <div className="space-y-4">
        <h2
          className="text-xl font-semibold"
          style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}
        >
          Section Labels
        </h2>
        <GeoPanel title="Label Styles">
          <div className="space-y-6">
            <div>
              <div className="geoint-section-label">Müttefikler & Partnerler</div>
              <p style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
                Content section with left border accent.
              </p>
            </div>
            <div>
              <div className="geoint-section-label">Çatışma & Risk Noktaları</div>
              <p style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
                Another section with consistent styling.
              </p>
            </div>
          </div>
        </GeoPanel>
      </div>
    </div>
  );
};
