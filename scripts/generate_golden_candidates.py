#!/usr/bin/env python3
"""
Generate golden dataset candidates from existing database using stratified sampling.

This script queries the existing BB-PAXDATA database to find 150 candidate sentences
that match the stratification criteria described in Faz 5.
"""

import csv
import sqlite3
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class GoldenCandidateGenerator:
    """Generates golden dataset candidates with stratified sampling."""

    def __init__(self, db_path: str = "bb-paxdata.db"):
        self.db_path = db_path
        self.logger = structlog.get_logger(__name__)

    def connect_db(self) -> sqlite3.Connection:
        """Connect to SQLite database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        return conn

    def get_topic_candidates(
        self, conn: sqlite3.Connection, target_per_topic: int = 20
    ) -> list[dict[str, Any]]:
        """Get candidates stratified by topic."""
        topics = [
            "BM Reformu",
            "Gazze",
            "Ukrayna",
            "Güvenlik",
            "Ekonomi",
            "Çok-kutupluluk",
            "İnsani Yardım",
            "Diğer",
        ]

        candidates = []
        for topic in topics:
            # Try different topic field names
            query = """
            SELECT DISTINCT s.sent_id, s.text, s.sent_order,
                   COALESCE(ai.AI_Birincil_Konu, ai.AI_Topic, 'Diğer') as topic,
                   ai.AI_Duygu_Skoru, ai.AI_Risk_Skoru, ai.AI_Potansiyel_Risk,
                   ai.AI_Diplomatik_Ton, ai.AI_Talep_Var,
                   seg.seg_id, p.panel_id, sp.speaker_name, sp.country
            FROM sentences s
            LEFT JOIN ai_sentence_analysis ai ON s.sent_id = ai.sent_id
            LEFT JOIN segments seg ON s.seg_id = seg.seg_id
            LEFT JOIN panels p ON seg.panel_id = p.panel_id
            LEFT JOIN speakers sp ON s.speaker_id = sp.speaker_id
            WHERE (ai.AI_Birincil_Konu LIKE ? OR ai.AI_Topic LIKE ? OR ? = 'Diğer')
            AND s.text IS NOT NULL AND LENGTH(s.text) > 20
            ORDER BY RANDOM()
            LIMIT ?
            """

            try:
                cursor = conn.execute(
                    query, (f"%{topic}%", f"%{topic}%", topic, target_per_topic)
                )
                topic_candidates = [dict(row) for row in cursor.fetchall()]
                candidates.extend(topic_candidates)
                self.logger.info(
                    f"Found {len(topic_candidates)} candidates for topic: {topic}"
                )
            except sqlite3.Error as e:
                self.logger.error(f"Error querying topic {topic}: {e}")

        return candidates

    def get_sentiment_candidates(
        self, conn: sqlite3.Connection
    ) -> list[dict[str, Any]]:
        """Get candidates stratified by sentiment."""
        sentiment_targets = [
            ("positive", 20, "ai.AI_Duygu_Skoru > 0.3"),
            ("negative", 30, "ai.AI_Duygu_Skoru < -0.3"),
            ("neutral", 30, "ai.AI_Duygu_Skoru BETWEEN -0.3 AND 0.3"),
            ("confrontational", 20, "ai.AI_Diplomatik_Ton = 'confrontational'"),
        ]

        candidates = []
        for sentiment, target, condition in sentiment_targets:
            query = f"""
            SELECT DISTINCT s.sent_id, s.text, s.sent_order,
                   ai.AI_Duygu_Skoru, ai.AI_Risk_Skoru, ai.AI_Potansiyel_Risk,
                   ai.AI_Diplomatik_Ton, ai.AI_Talep_Var, ai.AI_Birincil_Konu,
                   seg.seg_id, p.panel_id, sp.speaker_name, sp.country
            FROM sentences s
            LEFT JOIN ai_sentence_analysis ai ON s.sent_id = ai.sent_id
            LEFT JOIN segments seg ON s.seg_id = seg.seg_id
            LEFT JOIN panels p ON seg.panel_id = p.panel_id
            LEFT JOIN speakers sp ON s.speaker_id = sp.speaker_id
            WHERE {condition}
            AND s.text IS NOT NULL AND LENGTH(s.text) > 20
            ORDER BY RANDOM()
            LIMIT ?
            """

            try:
                cursor = conn.execute(query, (target,))
                sentiment_candidates = [dict(row) for row in cursor.fetchall()]
                candidates.extend(sentiment_candidates)
                self.logger.info(
                    f"Found {len(sentiment_candidates)} candidates for "
                    f"sentiment: {sentiment}"
                )
            except sqlite3.Error as e:
                self.logger.error(f"Error querying sentiment {sentiment}: {e}")

        return candidates

    def get_risk_candidates(self, conn: sqlite3.Connection) -> list[dict[str, Any]]:
        """Get candidates stratified by risk level."""
        risk_targets = [
            ("low", 40, "ai.AI_Risk_Skoru BETWEEN 0 AND 3"),
            ("medium", 35, "ai.AI_Risk_Skoru BETWEEN 4 AND 6"),
            ("high", 25, "ai.AI_Risk_Skoru BETWEEN 7 AND 10"),
        ]

        candidates = []
        for risk_level, target, condition in risk_targets:
            query = f"""
            SELECT DISTINCT s.sent_id, s.text, s.sent_order,
                   ai.AI_Duygu_Skoru, ai.AI_Risk_Skoru, ai.AI_Potansiyel_Risk,
                   ai.AI_Diplomatik_Ton, ai.AI_Talep_Var, ai.AI_Birincil_Konu,
                   seg.seg_id, p.panel_id, sp.speaker_name, sp.country
            FROM sentences s
            LEFT JOIN ai_sentence_analysis ai ON s.sent_id = ai.sent_id
            LEFT JOIN segments seg ON s.seg_id = seg.seg_id
            LEFT JOIN panels p ON seg.panel_id = p.panel_id
            LEFT JOIN speakers sp ON s.speaker_id = sp.speaker_id
            WHERE {condition}
            AND s.text IS NOT NULL AND LENGTH(s.text) > 20
            ORDER BY RANDOM()
            LIMIT ?
            """

            try:
                cursor = conn.execute(query, (target,))
                risk_candidates = [dict(row) for row in cursor.fetchall()]
                candidates.extend(risk_candidates)
                self.logger.info(
                    f"Found {len(risk_candidates)} candidates for risk: {risk_level}"
                )
            except sqlite3.Error as e:
                self.logger.error(f"Error querying risk {risk_level}: {e}")

        return candidates

    def get_demand_candidates(
        self, conn: sqlite3.Connection, target: int = 30
    ) -> list[dict[str, Any]]:
        """Get candidates that contain demands."""
        query = """
        SELECT DISTINCT s.sent_id, s.text, s.sent_order,
               ai.AI_Duygu_Skoru, ai.AI_Risk_Skoru, ai.AI_Potansiyel_Risk,
               ai.AI_Diplomatik_Ton, ai.AI_Talep_Var, ai.AI_Birincil_Konu,
               seg.seg_id, p.panel_id, sp.speaker_name, sp.country
        FROM sentences s
        LEFT JOIN ai_sentence_analysis ai ON s.sent_id = ai.sent_id
        LEFT JOIN segments seg ON s.seg_id = seg.seg_id
        LEFT JOIN panels p ON seg.panel_id = p.panel_id
        LEFT JOIN speakers sp ON s.speaker_id = sp.speaker_id
        WHERE ai.AI_Talep_Var = 1
        AND s.text IS NOT NULL AND LENGTH(s.text) > 20
        ORDER BY RANDOM()
        LIMIT ?
        """

        try:
            cursor = conn.execute(query, (target,))
            candidates = [dict(row) for row in cursor.fetchall()]
            self.logger.info(f"Found {len(candidates)} demand candidates")
            return candidates
        except sqlite3.Error as e:
            self.logger.error(f"Error querying demand candidates: {e}")
            return []

    def get_negation_trap_candidates(
        self, conn: sqlite3.Connection, target: int = 15
    ) -> list[dict[str, Any]]:
        """Get candidates with negation traps."""
        negation_patterns = [
            "% do not %",
            "% don't %",
            "% will not %",
            "% won't %",
            "% cannot %",
            "% can't %",
            "% should not %",
            "% shouldn't %",
            "% must not %",
            "% mustn't %",
            "% never %",
            "% no %",
        ]

        candidates = []
        for pattern in negation_patterns:
            query = """
            SELECT DISTINCT s.sent_id, s.text, s.sent_order,
                   ai.AI_Duygu_Skoru, ai.AI_Risk_Skoru, ai.AI_Potansiyel_Risk,
                   ai.AI_Diplomatik_Ton, ai.AI_Talep_Var, ai.AI_Birincil_Konu,
                   seg.seg_id, p.panel_id, sp.speaker_name, sp.country
            FROM sentences s
            LEFT JOIN ai_sentence_analysis ai ON s.sent_id = ai.sent_id
            LEFT JOIN segments seg ON s.seg_id = seg.seg_id
            LEFT JOIN panels p ON seg.panel_id = p.panel_id
            LEFT JOIN speakers sp ON s.speaker_id = sp.speaker_id
            WHERE s.text LIKE ?
            AND s.text IS NOT NULL AND LENGTH(s.text) > 20
            ORDER BY RANDOM()
            LIMIT 3
            """

            try:
                cursor = conn.execute(query, (pattern,))
                pattern_candidates = [dict(row) for row in cursor.fetchall()]
                candidates.extend(pattern_candidates)
            except sqlite3.Error as e:
                self.logger.error(f"Error querying negation pattern {pattern}: {e}")

        # Limit to target
        candidates = candidates[:target]
        self.logger.info(f"Found {len(candidates)} negation trap candidates")
        return candidates

    def get_position_candidates(self, conn: sqlite3.Connection) -> list[dict[str, Any]]:
        """Get candidates stratified by position in segment."""
        position_targets = [
            ("beginning", 30, "s.sent_order <= 3"),
            ("middle", 40, "s.sent_order BETWEEN 4 AND 10"),
            ("end", 30, "s.sent_order > 10"),
        ]

        candidates = []
        for position, target, condition in position_targets:
            query = f"""
            SELECT DISTINCT s.sent_id, s.text, s.sent_order,
                   ai.AI_Duygu_Skoru, ai.AI_Risk_Skoru, ai.AI_Potansiyel_Risk,
                   ai.AI_Diplomatik_Ton, ai.AI_Talep_Var, ai.AI_Birincil_Konu,
                   seg.seg_id, p.panel_id, sp.speaker_name, sp.country
            FROM sentences s
            LEFT JOIN ai_sentence_analysis ai ON s.sent_id = ai.sent_id
            LEFT JOIN segments seg ON s.seg_id = seg.seg_id
            LEFT JOIN panels p ON seg.panel_id = p.panel_id
            LEFT JOIN speakers sp ON s.speaker_id = sp.speaker_id
            WHERE {condition}
            AND s.text IS NOT NULL AND LENGTH(s.text) > 20
            ORDER BY RANDOM()
            LIMIT ?
            """

            try:
                cursor = conn.execute(query, (target,))
                position_candidates = [dict(row) for row in cursor.fetchall()]
                candidates.extend(position_candidates)
                self.logger.info(
                    f"Found {len(position_candidates)} candidates for "
                    f"position: {position}"
                )
            except sqlite3.Error as e:
                self.logger.error(f"Error querying position {position}: {e}")

        return candidates

    def remove_duplicates(
        self, candidates: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Remove duplicate candidates based on sent_id."""
        seen = set()
        unique_candidates = []

        for candidate in candidates:
            sent_id = candidate.get("sent_id")
            if sent_id and sent_id not in seen:
                seen.add(sent_id)
                unique_candidates.append(candidate)

        self.logger.info(
            f"Removed {len(candidates) - len(unique_candidates)} duplicates"
        )
        return unique_candidates

    def generate_candidates(self, output_path: str = "golden_candidates.csv") -> None:
        """Generate all candidates and save to CSV."""
        try:
            with self.connect_db() as conn:
                self.logger.info("Starting golden candidate generation...")

                # Collect candidates from all strategies
                all_candidates = []

                # Topic stratification
                topic_candidates = self.get_topic_candidates(conn, target_per_topic=15)
                all_candidates.extend(topic_candidates)

                # Sentiment stratification
                sentiment_candidates = self.get_sentiment_candidates(conn)
                all_candidates.extend(sentiment_candidates)

                # Risk stratification
                risk_candidates = self.get_risk_candidates(conn)
                all_candidates.extend(risk_candidates)

                # Demand candidates
                demand_candidates = self.get_demand_candidates(conn, target=25)
                all_candidates.extend(demand_candidates)

                # Negation trap candidates
                negation_candidates = self.get_negation_trap_candidates(conn, target=12)
                all_candidates.extend(negation_candidates)

                # Position stratification
                position_candidates = self.get_position_candidates(conn)
                all_candidates.extend(position_candidates)

                # Remove duplicates
                unique_candidates = self.remove_duplicates(all_candidates)

                # Limit to 150 candidates
                if len(unique_candidates) > 150:
                    unique_candidates = unique_candidates[:150]

                self.logger.info(
                    f"Generated {len(unique_candidates)} unique candidates"
                )

                # Save to CSV
                if unique_candidates:
                    fieldnames = unique_candidates[0].keys()
                    with open(
                        output_path, "w", newline="", encoding="utf-8"
                    ) as csvfile:
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(unique_candidates)

                    self.logger.info(f"Saved candidates to {output_path}")
                else:
                    self.logger.warning("No candidates generated")

        except Exception as e:
            self.logger.error(f"Error generating candidates: {e}")
            raise


def main() -> None:
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate golden dataset candidates")
    parser.add_argument("--db", default="bb-paxdata.db", help="Database path")
    parser.add_argument(
        "--output", default="golden_candidates.csv", help="Output CSV path"
    )

    args = parser.parse_args()

    generator = GoldenCandidateGenerator(args.db)
    generator.generate_candidates(args.output)


if __name__ == "__main__":
    main()
