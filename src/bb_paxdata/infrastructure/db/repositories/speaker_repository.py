from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import func, or_, select

from bb_paxdata.infrastructure.db.models import Speaker, SpeakerProfile
from bb_paxdata.infrastructure.db.repositories.base import BaseRepository

if TYPE_CHECKING:
    from bb_paxdata.infrastructure.db.models import Speaker


class SpeakerRepository(BaseRepository[Speaker]):
    """Async repository for Speaker Master Database."""

    model_class = Speaker

    async def get_by_canonical_name(self, name: str) -> Speaker | None:
        """Get a speaker by canonical name."""
        stmt = select(Speaker).where(Speaker.canonical_name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_country(self, country_code: str) -> list[Speaker]:
        """Get speakers by country code (ISO 3166-1 alpha-3)."""
        stmt = select(Speaker).where(Speaker.country_code == country_code)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_bloc(self, bloc: str) -> list[Speaker]:
        """Get speakers by diplomatic bloc."""
        stmt = select(Speaker).where(Speaker.bloc == bloc)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def search(self, query: str) -> list[Speaker]:
        """Search speakers by canonical_name, display_name or aliases."""
        if not query:
            return []
        like_query = f"%{query}%"

        # In SQLite/PostgreSQL, we can check JSON array search or cast to string.
        # CAST(aliases AS TEXT) LIKE query is simple and works across SQLite and PG.
        from sqlalchemy import String

        stmt = select(Speaker).where(
            or_(
                Speaker.canonical_name.ilike(like_query),
                Speaker.display_name.ilike(like_query),
                func.cast(Speaker.aliases, String).ilike(like_query),
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def upsert(self, speaker: Speaker) -> Speaker:
        """Upsert speaker based on canonical_name."""
        existing = await self.get_by_canonical_name(speaker.canonical_name)
        if existing:
            # Update fields
            existing.display_name = speaker.display_name or existing.display_name
            existing.country_code = speaker.country_code or existing.country_code
            existing.country_name = speaker.country_name or existing.country_name
            existing.bloc = speaker.bloc or existing.bloc
            if speaker.power_level is not None:
                existing.power_level = speaker.power_level
            existing.role = speaker.role or existing.role
            existing.title = speaker.title or existing.title
            existing.organization = speaker.organization or existing.organization
            existing.is_active = speaker.is_active
            existing.first_seen_at = speaker.first_seen_at or existing.first_seen_at
            existing.last_seen_at = speaker.last_seen_at or existing.last_seen_at
            existing.appearance_count = max(
                existing.appearance_count, speaker.appearance_count
            )
            existing.data_source = speaker.data_source or existing.data_source

            # Merge aliases
            existing_aliases = set(existing.aliases or [])
            new_aliases = set(speaker.aliases or [])
            existing.aliases = list(existing_aliases.union(new_aliases))

            # Merge metadata
            existing_meta = dict(existing.additional_metadata or {})
            new_meta = dict(speaker.additional_metadata or {})
            existing.additional_metadata = {**existing_meta, **new_meta}

            await self._session.flush()
            return existing
        else:
            self._session.add(speaker)
            await self._session.flush()
            return speaker

    async def get_all_with_stats(self) -> list[dict[str, Any]]:
        """Get all speakers joined with SpeakerProfile analytics stats."""
        # Query joining Speaker and SpeakerProfile (outer join since profile might be absent)
        stmt = select(Speaker, SpeakerProfile).outerjoin(
            SpeakerProfile, Speaker.speaker_id == SpeakerProfile.speaker_id
        )
        result = await self._session.execute(stmt)

        speakers_with_stats = []
        for speaker, profile in result.all():
            stats = {
                "speaker_id": speaker.speaker_id,
                "canonical_name": speaker.canonical_name,
                "display_name": speaker.display_name or speaker.canonical_name,
                "country_code": speaker.country_code,
                "country_name": speaker.country_name,
                "bloc": speaker.bloc,
                "power_level": speaker.power_level,
                "role": speaker.role,
                "title": speaker.title,
                "organization": speaker.organization,
                "is_active": speaker.is_active,
                "first_seen_at": (
                    speaker.first_seen_at.isoformat() if speaker.first_seen_at else None
                ),
                "last_seen_at": (
                    speaker.last_seen_at.isoformat() if speaker.last_seen_at else None
                ),
                "appearance_count": speaker.appearance_count,
                "data_source": speaker.data_source,
                "aliases": speaker.aliases or [],
                "metadata": speaker.additional_metadata or {},
                "created_at": speaker.created_at.isoformat(),
                "updated_at": speaker.updated_at.isoformat(),
                # Stats from profile
                "n_panels": profile.n_panels if profile else 0,
                "n_segments": profile.n_segments if profile else 0,
                "n_sentences": profile.n_sentences if profile else 0,
                "total_words": profile.total_words if profile else 0,
                "total_duration_sec": profile.total_duration_sec if profile else 0,
                "avg_sentiment": profile.avg_sentiment if profile else 0.0,
                "dominant_emotion": profile.dominant_emotion if profile else None,
                "dominant_topic": profile.dominant_topic if profile else None,
                "cooperative_pct": profile.cooperative_pct if profile else 0.0,
                "constructive_pct": profile.constructive_pct if profile else 0.0,
                "neutral_pct": profile.neutral_pct if profile else 0.0,
                "concerned_pct": profile.concerned_pct if profile else 0.0,
                "confrontational_pct": profile.confrontational_pct if profile else 0.0,
                "risk_event_count": profile.risk_event_count if profile else 0,
                "top_topics": profile.top_topics if profile else None,
                "avg_sentence_length": profile.avg_sentence_length if profile else 0.0,
                "lexical_diversity": profile.lexical_diversity if profile else 0.0,
                "diplo_vocab_score": profile.diplo_vocab_score if profile else 0.0,
                "demand_count": profile.demand_count if profile else 0,
                "pattern_diversity": profile.pattern_diversity if profile else 0.0,
                "avg_hedging_score": profile.avg_hedging_score if profile else 0.0,
                "avg_politeness_ratio": (
                    profile.avg_politeness_ratio if profile else 0.0
                ),
                "avg_dki_score": profile.avg_dki_score if profile else 0.0,
                "dominant_frame": profile.dominant_frame if profile else None,
                "dominant_audience": profile.dominant_audience if profile else None,
                "top_countries_mentioned": (
                    profile.top_countries_mentioned if profile else {}
                ),
                "ally_countries": profile.ally_countries if profile else {},
                "adversary_countries": profile.adversary_countries if profile else {},
            }
            speakers_with_stats.append(stats)

        return speakers_with_stats

    async def get_stats_summary(self) -> dict[str, Any]:
        """Get summary stats for dashboard cards."""
        # Total speaker count
        total_stmt = select(func.count(Speaker.speaker_id))
        total_res = await self._session.execute(total_stmt)
        total_count = total_res.scalar() or 0

        # Active speaker count
        active_stmt = select(func.count(Speaker.speaker_id)).where(Speaker.is_active)
        active_res = await self._session.execute(active_stmt)
        active_count = active_res.scalar() or 0

        # Represented countries count
        countries_stmt = select(func.count(func.distinct(Speaker.country_code))).where(
            Speaker.country_code is not None
        )
        countries_res = await self._session.execute(countries_stmt)
        countries_count = countries_res.scalar() or 0

        # Average power level
        power_stmt = select(func.avg(Speaker.power_level)).where(
            Speaker.power_level is not None
        )
        power_res = await self._session.execute(power_stmt)
        avg_power_level = float(power_res.scalar() or 0.0)

        return {
            "total_speakers": total_count,
            "active_speakers": active_count,
            "represented_countries": countries_count,
            "average_power_level": avg_power_level,
        }
