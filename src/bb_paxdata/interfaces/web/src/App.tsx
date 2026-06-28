import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { Layout } from '@/components/Layout';
import { AIComparison } from '@/pages/AIComparison';
import { AnomalyTimeline } from '@/pages/AnomalyTimeline';
import { AuditTrail } from '@/pages/AuditTrail';
import { BilateralRelations } from '@/pages/BilateralRelations';
import { Calibration } from '@/pages/Calibration';
import { Dashboard } from '@/pages/Dashboard';
import { DiscourseNetwork } from '@/pages/DiscourseNetwork';
import { PipelineMonitor } from '@/pages/PipelineMonitor';
import { PromptRegistry } from '@/pages/PromptRegistry';
import { ProvenanceGraph } from '@/pages/ProvenanceGraph';
import { ReviewDetail } from '@/pages/ReviewDetail';
import { ReviewQueue } from '@/pages/ReviewQueue';
import { Settings } from '@/pages/Settings';
import { SpeakersPage } from '@/pages/SpeakersPage';
import { SystemHealth } from '@/pages/SystemHealth';
import { TemporalDrift } from '@/pages/TemporalDrift';
import { WorldMap } from '@/pages/WorldMap';

export const App = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/speakers" element={<SpeakersPage />} />
          <Route path="/bilateral" element={<BilateralRelations />} />
          <Route path="/worldmap" element={<WorldMap />} />
          <Route path="/discourse" element={<DiscourseNetwork />} />
          <Route path="/anomalies" element={<AnomalyTimeline />} />
          <Route path="/drift" element={<TemporalDrift />} />
          <Route path="/queue" element={<Navigate to="/hitl-logic/queue" replace />} />
          <Route
            path="/hitl-logic/queue"
            element={
              <ErrorBoundary>
                <ReviewQueue mode="logic" />
              </ErrorBoundary>
            }
          />
          <Route
            path="/hitl-logic/queue/:logId"
            element={
              <ErrorBoundary>
                <ReviewDetail />
              </ErrorBoundary>
            }
          />
          <Route
            path="/hitl-ai/queue"
            element={
              <ErrorBoundary>
                <ReviewQueue mode="ai" />
              </ErrorBoundary>
            }
          />
          <Route
            path="/hitl-ai/queue/:logId"
            element={
              <ErrorBoundary>
                <ReviewDetail />
              </ErrorBoundary>
            }
          />
          <Route path="/review/:logId" element={<Navigate to="/hitl-logic/queue" replace />} />
          <Route path="/hitl-logic/audit" element={<AuditTrail />} />
          <Route path="/hitl-logic/calibration" element={<Calibration />} />
          <Route path="/hitl-logic/prompts" element={<PromptRegistry />} />
          <Route path="/hitl-ai/comparison" element={<AIComparison />} />
          <Route path="/audit" element={<Navigate to="/hitl-logic/audit" replace />} />
          <Route path="/calibration" element={<Navigate to="/hitl-logic/calibration" replace />} />
          <Route path="/prompts" element={<Navigate to="/hitl-logic/prompts" replace />} />
          <Route path="/comparison" element={<Navigate to="/hitl-ai/comparison" replace />} />
          <Route path="/health" element={<SystemHealth />} />
          <Route path="/monitor" element={<PipelineMonitor />} />
          <Route path="/provenance" element={<ProvenanceGraph />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};
