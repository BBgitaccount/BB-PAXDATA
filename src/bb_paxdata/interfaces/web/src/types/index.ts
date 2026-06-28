export type HumanVerdict = 'CONFIRMED_FAIL' | 'CONFIRMED_PASS' | 'CORRECTED';
export type AuditActionType =
  | 'REVIEW_STARTED'
  | 'VERDICT_SUBMITTED'
  | 'CORRECTED'
  | 'ROLLED_BACK'
  | 'ESCALATED';
export type PermissionLevel = 'view' | 'verdict' | 'correct' | 'escalate' | 'admin';
export type ReviewerScopeType = 'formula' | 'speaker' | 'panel' | 'country' | 'global';
export type ConfidenceLevel = 'LOW' | 'MEDIUM' | 'HIGH';
export type TriagePriority = 'NORMAL' | 'HIGH_PRIORITY' | 'SOVEREIGN_PRIORITY' | 'CRITICAL';
export type TriggerType =
  | 'HIGH_RISK'
  | 'CRITICAL_ANOMALY'
  | 'LOW_UNCERTAINTY'
  | 'MANUAL_FLAG'
  | 'CONSENSUS_ANOMALY'
  | 'CRITICAL_CONSENSUS'
  | 'FORMULA_FAILURE'
  | 'LOGIC_CHECK_FAILURE';
export type QueueStatus =
  | 'PENDING'
  | 'ASSIGNED'
  | 'IN_REVIEW'
  | 'APPROVED'
  | 'REJECTED'
  | 'MODIFIED'
  | 'ESCALATED';
export type AgreementStatus = 'AGREED' | 'PARTIAL' | 'DISAGREED' | 'ESCALATED';
export type RiskLevel = 'LOW' | 'MED' | 'HIGH' | 'CRITICAL';
export type ConsensusLevel = 'CLEAN' | 'SOFT_ANOMALY' | 'HARD_ANOMALY' | 'CRITICAL_ANOMALY';
export type FormulaName =
  | 'vader_compound'
  | 'negation_aware_diplo'
  | 'emotion_category_alignment'
  | 'hedging_score'
  | 'politeness_ratio'
  | 'sbi_score'
  | 'dki_score'
  | 'risk_score';
export type FrameType =
  | 'problem_definition'
  | 'cause_interpretation'
  | 'moral_evaluation'
  | 'remedy_suggestion'
  | 'episodic'
  | 'thematic'
  | 'conflict_frame'
  | 'security_frame'
  | 'humanitarian_frame'
  | 'legal_frame'
  | 'negotiation_frame'
  | 'occupation_frame'
  | 'two_state_frame'
  | 'effectiveness_frame'
  | 'sovereignty_frame'
  | 'multilateral_frame'
  | 'threat_frame'
  | 'deterrence_frame'
  | 'peace_frame'
  | 'neutral';

export interface KpiStats {
  total_logs: number;
  total_pass: number;
  total_fail: number;
  pending_review: number;
  confirmed_fail: number;
  confirmed_pass: number;
  corrected: number;
  accuracy_percentage: number;
}

export interface FormulaHealth {
  formula_name: string;
  total_fail: number;
  false_positive_rate: number;
  correction_rate: number;
  confirmed_fail_count: number;
  false_positive_count: number;
  correction_count: number;
}

export interface DailyTrend {
  date: string;
  pass_count: number;
  fail_count: number;
}

export interface PriorityDistribution {
  priority: TriagePriority;
  count: number;
}

export interface TriggerDistribution {
  trigger: TriggerType;
  count: number;
}

export interface ConsensusDistribution {
  consensus: ConsensusLevel;
  count: number;
}

export interface FailQueueItem {
  log_id: number;
  run_id: string;
  formula_name: FormulaName;
  status: string;
  actual_value: number;
  expected_constraint: string;
  details: Record<string, unknown>;
  human_verdict: HumanVerdict | null;
  human_note: string | null;
  log_version: number;
  reviewer_id: string | null;
  sentence_text: string;
  sent_id: string;
  seg_id: string;
  file_id: string;
  speaker_name: string;
  country: string;
  power_level: number;
  ai_risk_score: number;
  ai_emotion_category: string;
  ai_diplomatic_tone: string;
  review_id: number | null;
  review_status: QueueStatus | null;
  trigger_type: TriggerType | null;
  priority_score: number;
  created_at: string;
}

export interface TripletContext {
  prev: string | null;
  current: string;
  next: string | null;
  speaker: {
    name: string;
    country: string;
    role: string;
    power_level: number;
    influence_tier: string;
    bloc: string;
  };
  panel: {
    file_id: string;
    panel_number: number;
    date: string;
    theme: string;
  };
}

export interface ComparisonRow {
  metric: string;
  formula_value: string | number;
  ai_value: string | number;
  delta: string;
  aligned: boolean;
}

export interface VerdictPayload {
  log_id: number;
  verdict: HumanVerdict;
  corrected_value: number | null;
  note: string | null;
  confidence: ConfidenceLevel;
  justification: string;
  reviewer_id: string;
}

export interface VerdictResponse {
  new_log_id: number;
  audit_id: number;
  log_version: number;
}

export interface SimilarCase {
  sentence_text: string;
  country: string;
  speaker_name: string;
  actual_value: number;
  previous_verdict: HumanVerdict;
  previous_note: string;
}

export interface AuditEntry {
  audit_id: number;
  log_id: number;
  action_type: AuditActionType;
  previous_verdict: HumanVerdict | null;
  new_verdict: HumanVerdict | null;
  previous_value: number | null;
  new_value: number | null;
  performed_by: string;
  performed_at: string;
  justification: string;
  review_status: QueueStatus;
}

export interface CalibrationReport {
  cohens_kappa_frame: number;
  cohens_kappa_risk: number;
  ai_human_f1_frame: number;
  ai_human_f1_risk: number;
  sbi_mae: number;
  total_reviews: number;
  total_disagreements: number;
  disagreement_rate: number;
  is_reliable: boolean;
  requires_prompt_update: boolean;
  requires_weight_update: boolean;
  alert_message: string | null;
  top_disagreement_patterns: string[];
}

export interface ReviewerPerformance {
  reviewer_id: string;
  total_actions: number;
  verdict_count: number;
  correction_count: number;
  correction_rate: number;
}

export interface Reviewer {
  reviewer_id: string;
  scope_type: ReviewerScopeType;
  scope_value: string;
  permission_level: PermissionLevel;
  max_daily_reviews: number;
  current_daily_count: number;
  is_active: boolean;
  created_at: string;
}

export interface SystemSettings {
  anomaly_soft_log_only: boolean;
  anomaly_controller_enabled: boolean;
  anomaly_context_window: number;
  risk_ai_weight: number;
  risk_anomaly_weight: number;
  formula_tolerance: number;
  risk_threshold: number;
}

export interface HumanReviewEntry {
  id: number;
  sentence_text: string;
  ai_sbi_score: number;
  ai_dominant_frame: FrameType;
  ai_risk_level: RiskLevel;
  ai_sentiment_score: number;
  human_sbi_score: number | null;
  human_dominant_frame: FrameType | null;
  human_risk_level: RiskLevel | null;
  human_sentiment_score: number | null;
  agreement_status: AgreementStatus | null;
  disagreement_reason: string | null;
}

export interface GoldStandardExample {
  frame_type: FrameType;
  sentence_text: string;
  explanation: string;
}

export interface User {
  reviewer_id: string;
  roles: PermissionLevel[];
  token: string;
  scope_type: ReviewerScopeType;
  scope_value: string;
}

export interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
}

export interface PromptVersion {
  version_id: string;
  content: string;
  content_hash: string;
  academic_ref: string | null;
  created_at: string;
}

export interface PromptListResponse {
  prompts: Record<string, PromptVersion[]>;
}

export interface BilateralSentimentData {
  from_country: string;
  to_country: string;
  affinity_score: number;
  avg_sentiment: number;
  interaction_count: number;
  relationship_type: string;
}

export interface PanelTimelineEntry {
  file_id: string;
  panel_number: number | null;
  date_str: string;
  title: string;
  speaker_count?: number;
}

export interface DiscourseNode {
  id: string;
  label: string;
  type: 'actor' | 'concept';
}

export interface DiscourseEdge {
  source: string;
  target: string;
  weight: number;
  tf: number;
  idf: number;
}

export interface DiscourseNetworkResponse {
  nodes: DiscourseNode[];
  edges: DiscourseEdge[];
}

export interface AnomalyTimelineItem {
  fail_id: number;
  sent_id: string;
  file_id: string | null;
  speaker_name: string | null;
  country: string | null;
  check_type: string;
  formula_value: string | null;
  ai_value: string | null;
  discrepancy_score: number | null;
  original_sentence: string | null;
  fail_reason: string | null;
  fail_category: string | null;
  anomaly_types: string | null;
  processed_at: string | null;
  negation_type: string | null;
  negation_scope: string | null;
  linguistic_marker: string | null;
  contextual_factor: string | null;
  temporal_factor: string | null;
}

export interface GarchResult {
  sentiment_volatility: number;
  volatility_regime: 'LOW_VOLATILITY' | 'ARCH_EFFECTS' | 'HIGH_VOLATILITY';
  volatilities_series: number[];
  sentiment_series: number[];
}

export interface HalfLifeResult {
  salience_half_life: number;
  decay_rate: number;
  agenda_permanence: 'FLASH' | 'TACTICAL' | 'STRATEGIC' | 'STRUCTURAL';
  counts_series: number[];
}

export interface DkiHistoryItem {
  id: number;
  analysis_id: string;
  speaker_id: string;
  session_id: string;
  dki_score: number;
  velocity: number;
  semantic_shift: number;
  debate_loading: number;
  created_at: string;
}

export interface DriftEventItem {
  id: number;
  speaker_id: string;
  panel_id: string;
  drift_type: 'SENTIMENT' | 'TOPIC' | 'LEXICAL' | 'TONE' | 'RISK';
  start_position: number;
  end_position: number;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  before_state: string | null;
  after_state: string | null;
  confidence: number;
  algorithm: string;
}

export interface TemporalDriftData {
  selected_speaker: string | null;
  garch: GarchResult;
  half_life: HalfLifeResult;
  dki: DkiHistoryItem[];
  drift_events: DriftEventItem[];
  speakers: string[];
}

export interface Speaker {
  speaker_id: string;
  canonical_name: string;
  display_name: string | null;
  country_code: string | null;
  country_name: string | null;
  bloc: string | null;
  power_level: number | null;
  role: string | null;
  title: string | null;
  organization: string | null;
  is_active: boolean;
  first_seen_at: string | null;
  last_seen_at: string | null;
  appearance_count: number;
  data_source: string;
  aliases: string[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;

  // Stats joined from SpeakerProfile
  n_panels: number;
  n_segments: number;
  n_sentences: number;
  total_words: number;
  total_duration_sec: number;
  avg_sentiment: number;
  dominant_emotion: string | null;
  dominant_topic: string | null;
  cooperative_pct: number;
  constructive_pct: number;
  neutral_pct: number;
  concerned_pct: number;
  confrontational_pct: number;
  risk_event_count: number;
  top_topics: string | null;
  avg_sentence_length: number;
  lexical_diversity: number;
  diplo_vocab_score: number;
  demand_count: number;
  pattern_diversity: number;
  avg_hedging_score: number;
  avg_politeness_ratio: number;
  avg_dki_score: number;
  dominant_frame: string | null;
  dominant_audience: string | null;
}

export interface PaginatedSpeakers {
  items: Speaker[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface SpeakerStatsSummary {
  total_speakers: number;
  active_speakers: number;
  represented_countries: number;
  average_power_level: number;
}

export interface SpeakerCountryDistribution {
  country_code: string | null;
  country_name: string | null;
  count: number;
}

export interface SpeakerBlocDistribution {
  bloc: string | null;
  count: number;
}

export interface SpeakerAppearance {
  file_id: string;
  title: string;
  date_str: string | null;
  sentence_count: number;
}

export interface SpeakerSentimentHistory {
  file_id: string;
  file_title: string;
  date_str: string | null;
  avg_sentiment: number;
  sentence_count: number;
}

export interface EventCorrelation {
  event_id: string;
  event_type: 'MILITARY' | 'ECONOMIC' | 'TREATY' | 'CRISIS';
  affected_countries: string[];
  sentiment_impact_score: number;
}

export interface AsymmetricRelation {
  source_country: string;
  target_country: string;
  rhetoric_sentiment: number;
  action_sentiment: number;
}

export interface EconomicIndicators {
  country_a: string;
  country_b: string;
  bilateral_trade_volume: number;
  sanctions_active: boolean;
}

export interface SpeechActDelta {
  speaker_id: string;
  distribution_a: Record<string, number>;
  distribution_b: Record<string, number>;
  delta_distribution: Record<string, number>;
  most_changed_type: string | null;
  change_magnitude: number;
}

export interface NarrativeLayerDelta {
  speaker_id: string;
  layer_weights_a: Record<string, number>;
  layer_weights_b: Record<string, number>;
  delta_weights: Record<string, number>;
  dominant_layer_change: [string, number] | null;
}

export interface SignificantChange {
  speaker_id: string;
  metric: string;
  change_type: string;
  value_a: number | string;
  value_b: number | string;
  delta: number;
  is_significant: boolean;
}

export interface AnalysisDelta {
  session_a_id: string;
  session_b_id: string;
  comparison_timestamp: string;

  delta_sbi?: Record<string, number>;
  delta_sbi_normalized?: Record<string, number>;
  delta_sbi_significant?: Record<string, boolean>;

  delta_dki?: Record<string, number>;
  delta_dki_normalized?: Record<string, number>;
  delta_dki_significant?: Record<string, boolean>;

  delta_risk: number | null;
  delta_risk_normalized?: number | null;
  delta_risk_significant: boolean;

  delta_hedging?: Record<string, number>;
  delta_hedging_normalized?: Record<string, number>;
  delta_hedging_significant?: Record<string, boolean>;

  delta_speech_act?: Record<string, SpeechActDelta>;
  delta_narrative?: Record<string, NarrativeLayerDelta>;

  significant_changes?: SignificantChange[];

  speakers_in_a?: string[];
  speakers_in_b?: string[];
  common_speakers?: string[];
  speakers_only_in_a?: string[];
  speakers_only_in_b?: string[];

  most_drifted_speaker?: string | null;
  most_drifted_dimension?: string;
  total_significant_changes?: number;
}

export interface CompareSessionsResponse {
  success: boolean;
  contrast_report: unknown | null;
  analysis_delta: AnalysisDelta | null;
  errors: string[];
}
