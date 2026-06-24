from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from bb_paxdata.infrastructure.db.models import Speaker

if TYPE_CHECKING:
    from bb_paxdata.infrastructure.db.repositories.unit_of_work import (
        AbstractUnitOfWork,
    )

logger = logging.getLogger(__name__)


def normalize_speaker_name(raw_name: str) -> tuple[str, str]:
    """
    Normalizes a raw speaker name.
    Returns (canonical_name, display_name).

    Examples:
    - "LAVROV, Sergei" -> ("LAVROV, Sergei", "Sergei Lavrov")
    - "Sergei Lavrov" -> ("LAVROV, Sergei", "Sergei Lavrov")
    - "Erdoğan" -> ("ERDOĞAN", "Erdoğan")
    """
    from bb_paxdata.infrastructure.text.normalizer import normalize_person_name

    name = normalize_person_name(raw_name)
    if not name:
        return "UNKNOWN", "Unknown"

    if "," in name:
        parts = name.split(",", 1)
        last = parts[0].strip().upper()
        first = parts[1].strip()
        canonical = f"{last}, {first}"
        display = f"{first} {last.title()}"
        return canonical, display

    parts = name.split()
    if len(parts) == 1:
        canonical = name.upper()
        display = name
        return canonical, display

    # Assume last word is surname
    first = " ".join(parts[:-1])
    last = parts[-1].upper()
    canonical = f"{last}, {first}"
    display = f"{first} {last.title()}"
    return canonical, display


class SpeakerRegistryUseCase:
    def __init__(self, unit_of_work: AbstractUnitOfWork) -> None:
        self._uow = unit_of_work

    async def detect_or_create_speaker(
        self, raw_name: str, context: dict[str, Any] | None = None
    ) -> Speaker:
        """
        Detects an existing speaker matching raw_name (canonical name or alias)
        or creates a new one in the Speaker Master database.
        """
        ctx = context or {}
        canonical_name, display_name = normalize_speaker_name(raw_name)

        # 1. Check canonical name match
        speaker = await self._uow.speakers.get_by_canonical_name(canonical_name)

        # 2. Check alias matches if not found
        if not speaker:
            speakers_list = await self._uow.speakers.search(raw_name)
            for s in speakers_list:
                aliases = s.aliases or []
                if (
                    raw_name in aliases
                    or canonical_name in aliases
                    or display_name in aliases
                ):
                    speaker = s
                    break

        # 3. If not found, create a new speaker
        if not speaker:
            aliases = list(set([raw_name, canonical_name, display_name]))

            # Map role from string to standard roles
            role = ctx.get("role")
            if role:
                role = str(role).upper()

            # Normalize country and bloc assignments
            norm_code = ctx.get("country_code")
            norm_name = ctx.get("country_name") or ctx.get("country")
            norm_bloc = ctx.get("bloc")

            raw_country = norm_name or norm_code
            if raw_country:
                from bb_paxdata.application.domain.lexicon.country_bloc_mapping import (
                    normalize_country,
                )

                iso3, std_name, std_bloc = normalize_country(raw_country)
                if iso3 != "UNK":
                    norm_code = iso3
                    norm_name = std_name
                    if not norm_bloc or norm_bloc.lower() == "unknown":
                        norm_bloc = std_bloc

            speaker = Speaker(
                canonical_name=canonical_name,
                display_name=display_name,
                country_code=norm_code,
                country_name=norm_name,
                bloc=norm_bloc,
                power_level=ctx.get("power_level", 0.5),
                role=role,
                title=ctx.get("title"),
                organization=ctx.get("organization"),
                is_active=ctx.get("is_active", True),
                first_seen_at=datetime.now(UTC).replace(tzinfo=None),
                last_seen_at=datetime.now(UTC).replace(tzinfo=None),
                appearance_count=0,
                data_source=ctx.get("data_source", "pipeline_auto"),
                aliases=aliases,
                additional_metadata=ctx.get("metadata", {}),
            )
            speaker = await self._uow.speakers.add(speaker)
            logger.info(
                "Created new speaker in Master Registry: %s (%s)",
                canonical_name,
                speaker.speaker_id,
            )
        else:
            # If exists, update aliases list to include raw_name if not already present
            curr_aliases = list(speaker.aliases or [])
            if raw_name not in curr_aliases:
                curr_aliases.append(raw_name)
                speaker.aliases = curr_aliases
                await self._uow.flush()

        # Sync names to entries table
        await self._sync_to_entries([canonical_name, display_name])
        return speaker

    async def _sync_to_entries(self, names: list[str]) -> None:
        """Syncs normalized speaker names to the entries table."""
        session = getattr(self._uow, "_session", None)
        if session is None:
            session = getattr(self._uow, "session", None)
        if session is None:
            return

        from sqlalchemy import select

        from bb_paxdata.infrastructure.db.models import Entry

        for name in names:
            if not name or name.upper() in ("UNKNOWN",):
                continue
            try:
                stmt = select(Entry).where(Entry.person == name)
                res = await session.execute(stmt)
                existing = res.scalar_one_or_none()
                if not existing:
                    entry = Entry(person=name)
                    session.add(entry)
                    await session.flush()
            except Exception as e:
                logger.warning(
                    "Failed to sync name %s to entries table: %s", name, str(e)
                )

    async def enrich_speaker_from_pipeline(
        self, speaker_id: str, analysis_result: dict[str, Any]
    ) -> None:
        """
        Enriches speaker metadata with information detected during downstream pipeline analysis.
        """
        speaker = await self._uow.speakers.get_by_id(speaker_id)
        if not speaker:
            return

        # Extract potential enrichment data
        title = analysis_result.get("title")
        org = analysis_result.get("organization")
        wiki_id = analysis_result.get("wikipedia_id")
        un_url = analysis_result.get("un_profile_url")

        if title and not speaker.title:
            speaker.title = title
        if org and not speaker.organization:
            speaker.organization = org

        # Update metadata
        meta = dict(speaker.additional_metadata or {})
        if wiki_id:
            meta["wikipedia_id"] = wiki_id
        if un_url:
            meta["un_profile_url"] = un_url
        speaker.additional_metadata = meta

        await self._uow.flush()

    async def bulk_import_speakers(self, data: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Bulk import speakers into the Master Registry.
        """
        created = 0
        updated = 0
        errors = []

        for idx, item in enumerate(data):
            try:
                name = (
                    item.get("canonical_name")
                    or item.get("display_name")
                    or item.get("name")
                )
                if not name:
                    errors.append(f"Row {idx}: Missing name identifier.")
                    continue

                canonical_name, display_name = normalize_speaker_name(name)

                norm_code = item.get("country_code")
                norm_name = item.get("country_name") or item.get("country")
                norm_bloc = item.get("bloc")

                raw_country = norm_name or norm_code
                if raw_country:
                    from bb_paxdata.application.domain.lexicon.country_bloc_mapping import (
                        normalize_country,
                    )

                    iso3, std_name, std_bloc = normalize_country(raw_country)
                    if iso3 != "UNK":
                        norm_code = iso3
                        norm_name = std_name
                        if not norm_bloc or norm_bloc.lower() == "unknown":
                            norm_bloc = std_bloc

                speaker = Speaker(
                    canonical_name=canonical_name,
                    display_name=item.get("display_name") or display_name,
                    country_code=norm_code,
                    country_name=norm_name,
                    bloc=norm_bloc,
                    power_level=item.get("power_level", 0.5),
                    role=item.get("role"),
                    title=item.get("title"),
                    organization=item.get("organization"),
                    is_active=item.get("is_active", True),
                    appearance_count=item.get("appearance_count", 0),
                    data_source=item.get("data_source", "imported"),
                    aliases=item.get("aliases", [name, canonical_name, display_name]),
                    additional_metadata=item.get("metadata", {}),
                )

                res = await self._uow.speakers.upsert(speaker)
                if res.created_at == res.updated_at:
                    created += 1
                else:
                    updated += 1
                await self._sync_to_entries([canonical_name, display_name])
            except Exception as e:
                errors.append(f"Row {idx} import error: {e!s}")

        return {
            "succeeded": len(errors) == 0,
            "created": created,
            "updated": updated,
            "errors": errors,
        }
