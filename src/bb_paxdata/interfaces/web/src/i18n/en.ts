import type { tr } from './tr';

export const en: typeof tr = {
  // Navigation & TopBar
  'nav.group.general': 'GENERAL',
  'nav.group.logic': 'HITL LOGIC',
  'nav.group.ai': 'HITL AI',
  'nav.dashboard': 'Summary',
  'nav.speakers': 'Speaker Database',
  'nav.chord': 'Chord Diagram',
  'nav.sankey': 'Sankey Flow',
  'nav.timeline': 'Timeline',
  'nav.discourse': 'Discourse Network',
  'nav.anomalies': 'Anomaly Timeline',
  'nav.drift': 'Temporal Drift',
  'nav.health': 'System Health',
  'nav.monitor': 'Pipeline Monitor',
  'nav.provenance': 'Provenance Graph',
  'nav.logic_queue': 'Formula Queue',
  'nav.logic_audit': 'Audit Trail',
  'nav.logic_calib': 'Calibration',
  'nav.logic_prompts': 'Prompt Registry',
  'nav.ai_queue': 'AI Queue',
  'nav.comparison': 'AI Comparison',
  'nav.settings': 'Settings',
  'topbar.logout': 'Log Out',
  'topbar.logout_toast': 'Session terminated.',
  'topbar.light_mode': 'Light Mode',
  'topbar.dark_mode': 'Dark Mode',

  // Common UI Elements
  'common.refresh': 'Refresh',
  'common.retry': 'Retry',
  'common.save': 'SAVE',
  'common.approve': 'APPROVE',
  'common.reject': 'REJECT',
  'common.review': 'REVIEW',
  'common.status': 'Status',
  'common.actions': 'Actions',
  'common.loading': 'Loading...',
  'common.error': 'Error',

  // Dashboard
  'dashboard.title': 'Summary',
  'dashboard.desc': 'HITL operational dashboard of the diplomatic analysis pipeline',
  'dashboard.kpi.total_logs': 'Total Logs',
  'dashboard.kpi.total_pass': 'Total PASS',
  'dashboard.kpi.total_fail': 'Total FAIL',
  'dashboard.kpi.pending_review': 'Pending Review',
  'dashboard.kpi.confirmed_fail': 'Confirmed FAIL',
  'dashboard.kpi.false_positive': 'False Positive',
  'dashboard.kpi.corrected': 'Corrected',
  'dashboard.kpi.accuracy': 'Accuracy',
  'dashboard.kpi.error_rate': 'Formula Error Rate',
  'dashboard.kpi.latency': 'Avg Latency',
  'dashboard.kpi.participation': 'Reviewer Participation',
  'dashboard.chart.consensus': 'Bilateral Discourse Consensus',
  'dashboard.chart.trends': 'Daily Anomaly and Formula Error Trends',
  'dashboard.chart.priorities': 'Priority Distribution (Fischer DNA)',
  'dashboard.chart.triggers': 'Trigger Distribution',
  'dashboard.chart.consensus_dist': 'Consensus Level Distribution',
  'dashboard.timeline': 'Review Timeline',
  'dashboard.chart.daily_trend': 'Daily PASS/FAIL Trend',
  'dashboard.chart.last_30_days': 'Last 30 days',
  'dashboard.chart.triage_dist': 'Triage Distribution',
  'dashboard.chart.priority_levels': 'Priority levels',
  'dashboard.chart.formula_health': 'Formula Health',
  'dashboard.chart.fp_correction_rates': 'False positive and correction rates',
  'dashboard.chart.trigger_dist': 'Trigger Distribution',
  'dashboard.chart.triage_reasons': 'Triage reasons',
  'dashboard.chart.consensus_level_dist': 'Consensus Level Distribution',
  'dashboard.chart.dualgate_outputs': 'DualGate outputs',

  // Settings
  'settings.title': 'System Settings',
  'settings.desc': 'Reviewer management, system parameters and token management',
  'settings.reviewers': 'Reviewer Management',
  'settings.params': 'System Parameters',
  'settings.token': 'Token Management',
  'settings.save_toast': 'Settings successfully saved.',
  'settings.token_toast': 'New token successfully generated.',
  'settings.no_permission': 'You do not have permission to access this page.',

  // Discourse Network
  'discourse.title': 'Discourse Network Explorer',
  'discourse.desc': 'Fischer DNA Bipartite Actor-Concept Discourse Network Analysis',
  'discourse.actors': 'Actors',
  'discourse.concepts': 'Discourse Concepts',
  'discourse.select_session':
    'Please select an Analysis Session (Session ID) to load the discourse network.',

  // Anomaly Timeline
  'anomalies.title': 'Anomaly Timeline',
  'anomalies.desc':
    'Chronological stream of contradictions and anomalies detected by Fischer DNA and CrossAnomalyService',

  // Audit Trail
  'audit.title': 'Audit Trail',
  'audit.desc': 'WORM audit logs and modification history',

  // System Health
  'health.title': 'System Health',
  'health.desc': 'Database status detection, table occupancy rates and live system metrics',

  // Temporal Drift
  'drift.title': 'Temporal Drift Analysis',
  'drift.desc': 'GARCH Volatility, Entity Speech Half-life and longitudinal DKI trend tracking',

  // Review Queue
  'queue.logic_title': 'HITL Logic — Formula Validation Queue',
  'queue.ai_title': 'HITL AI — Review Queue',
  'queue.logic_desc': 'Formula logs in FAIL state and records waiting for human review',
  'queue.ai_desc': 'AI analysis outputs and records waiting for human review',
  'queue.records_count': '{count} records',

  // Calibration
  'calibration.title': 'Calibration & Performance',
  'calibration.desc': 'AI-human alignment metrics and reviewer performance analysis',

  // Pipeline Monitor
  'monitor.title': 'Pipeline Monitor',
  'monitor.desc':
    'Asynchronous diplomatic transcript ingestion flow and process load monitoring panel',

  // Prompt Registry
  'prompts.title': 'Prompt Registry',
  'prompts.desc': 'Academic reference chain and prompt versions',

  // AI Comparison
  'comparison.title': 'AI Comparison Review',
  'comparison.desc': 'Comparison of AI outputs with human evaluations',
};
