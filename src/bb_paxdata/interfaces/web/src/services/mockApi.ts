import type {
  HumanReviewEntry,
  FailQueueItem,
  FrameType,
  RiskLevel,
  AgreementStatus,
} from '@/types';
import { apiClient } from './apiClient';

/**
 * mockApi — retained only for the complex HumanReviewEntry mapping that
 * adapts FailQueueItem API responses to the AIComparison page data model.
 *
 * All other methods have been migrated to direct `apiClient` calls.
 */
export const mockApi = {
  async getHumanReviews(): Promise<HumanReviewEntry[]> {
    const data = await apiClient.get<FailQueueItem[]>(
      '/api/v1/queue?status_filter=reviewed&limit=50',
    );
    return data.map((item) => {
      const details = (item.details || {}) as Record<string, any>;
      return {
        id: item.log_id,
        sentence_text: item.sentence_text || '',
        ai_sbi_score:
          item.ai_risk_score !== null && item.ai_risk_score !== undefined
            ? item.ai_risk_score
            : details.ai_sbi_score || null,
        ai_dominant_frame:
          (item.ai_emotion_category as FrameType) ||
          (details.ai_dominant_frame as FrameType) ||
          ('neutral' as FrameType),
        ai_risk_level:
          (details.ai_risk_level as RiskLevel) ||
          (item.ai_risk_score
            ? item.ai_risk_score > 70
              ? ('HIGH' as RiskLevel)
              : ('LOW' as RiskLevel)
            : ('LOW' as RiskLevel)),
        ai_sentiment_score:
          item.ai_diplomatic_tone !== null && item.ai_diplomatic_tone !== undefined
            ? Number(item.ai_diplomatic_tone)
            : details.ai_sentiment_score || 0.0,
        human_sbi_score:
          item.actual_value !== null ? item.actual_value : details.human_sbi_score || null,
        human_dominant_frame: (details.human_dominant_frame as FrameType) || null,
        human_risk_level: (details.human_risk_level as RiskLevel) || null,
        human_sentiment_score: (details.human_sentiment_score as number) || null,
        agreement_status: (item.human_verdict as AgreementStatus) || null,
        disagreement_reason: item.human_note || null,
      };
    });
  },
};
