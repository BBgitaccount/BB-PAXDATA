export type RelationshipType = 'ALLY' | 'PARTNER' | 'NEUTRAL' | 'CAUTIOUS' | 'ADVERSARY';
export type ReferenceContext = 'PRAISE' | 'NEUTRAL_MENTION' | 'ACCUSATION';
export type DominantEmotion =
  | 'cooperative'
  | 'constructive'
  | 'neutral_cautious'
  | 'concerned'
  | '';

export interface CountryNode {
  country: string;
  isoAlpha3: string | null;
  totalInteractions: number;
  avgSentiment: number;
  dominantEmotion: DominantEmotion | null;
  relationshipCategories: Record<RelationshipType, number>;
  praiseCount: number;
  accusationCount: number;
  neutralCount: number;
  powerLevel: number;
  sessions: string[];
}

export interface BilateralFlow {
  fromCountry: string;
  toCountry: string;
  fromIso3: string | null;
  toIso3: string | null;
  interactionCount: number;
  avgSentiment: number;
  affinityScore: number;
  powerWeightedScore: number;
  relationshipType: RelationshipType;
  praiseRatio: number;
  accusationRatio: number;
  sessions: string[];
}

export interface SentimentMatrix {
  countries: string[];
  matrix: (number | null)[][];
  interactionMatrix: number[][];
  relationshipMatrix: (RelationshipType | null)[][];
}

export interface SessionTimeline {
  sessionId: string;
  sessionLabel: string;
  countries: string[];
  avgSentiment: number;
  dominantEmotion: string;
  topRelationships: Array<{
    from: string;
    to: string;
    type: RelationshipType;
    score: number;
  }>;
  praiseCount: number;
  accusationCount: number;
  createdAt: string | null;
}

export interface ReferenceFlow {
  speakerCountry: string;
  referencedCountry: string;
  context: ReferenceContext;
  count: number;
  avgSentiment: number;
  sessions: string[];
}

export interface CountryRiskProfile {
  country: string;
  totalMentions: number;
  avgSentiment: number;
  sentimentAsSpeaker: number;
  sentimentAsTarget: number;
  allyCount: number;
  adversaryCount: number;
  accusationRatio: number;
  dominantEmotion: string;
  sessionsActive: string[];
  topAccusers: Array<{ country: string; count: number }>;
  topPraiseGivers: Array<{ country: string; count: number }>;
  relationshipBreakdown: Record<RelationshipType, number>;
}
