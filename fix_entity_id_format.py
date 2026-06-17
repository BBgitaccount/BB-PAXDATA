"""Script to fix entity_id format in formula_validation_logs to match sent_id format."""

import asyncio

from bb_paxdata.infrastructure.db.session import engine
from sqlalchemy import text


async def fix_entity_id_format():
    """Update entity_id in formula_validation_logs to match sent_id format in sentences."""

    async with engine.begin() as conn:
        # First, let's check the current formats
        result = await conn.execute(
            text("SELECT DISTINCT entity_id FROM formula_validation_logs LIMIT 10")
        )
        entity_ids = result.fetchall()
        print("Sample entity_ids from formula_validation_logs:")
        for row in entity_ids:
            print(f"  {row[0]}")

        result = await conn.execute(
            text("SELECT DISTINCT sent_id FROM sentences LIMIT 10")
        )
        sent_ids = result.fetchall()
        print("\nSample sent_ids from sentences:")
        for row in sent_ids:
            print(f"  {row[0]}")

        # Check if there's a pattern mismatch
        # Common issue: entity_id might be "sent-123" while sent_id is "SENT-123"
        # or entity_id might be "123" while sent_id is "SENT-123"

        # Try to fix by normalizing entity_id to match sent_id format
        # The actual data shows entity_ids like "sent_12_climate_214" and sent_ids like "sent_01_ahmed_al-sharaa_1"
        # These don't match, so we need a different approach

        # Check if there are any matching records
        result = await conn.execute(
            text(
                """
            SELECT COUNT(*) 
            FROM formula_validation_logs f
            JOIN sentences s ON f.entity_id = s.sent_id
        """
            )
        )
        match_count = result.fetchone()[0]
        print(f"\nCurrent matching records (entity_id = sent_id): {match_count}")

        # Try case-insensitive match
        result = await conn.execute(
            text(
                """
            SELECT COUNT(*) 
            FROM formula_validation_logs f
            JOIN sentences s ON LOWER(f.entity_id) = LOWER(s.sent_id)
        """
            )
        )
        case_match_count = result.fetchone()[0]
        print(f"Case-insensitive matching records: {case_match_count}")

        # If no matches, we need to create a mapping or fix the data
        if match_count == 0 and case_match_count == 0:
            print(
                "\nNo matching records found. The entity_id and sent_id formats are fundamentally different."
            )
            print("This requires a data migration or mapping strategy.")
            print(
                "For now, the queue will show formula validation data without sentence context."
            )
        else:
            print(
                f"\nFound {case_match_count} matching records with case-insensitive comparison."
            )

            # Update entity_id to match sent_id case
            await conn.execute(
                text(
                    """
                UPDATE formula_validation_logs f
                SET entity_id = s.sent_id
                FROM sentences s
                WHERE LOWER(f.entity_id) = LOWER(s.sent_id)
            """
                )
            )
            print("Updated entity_id to match sent_id case")

        # Check the result
        result = await conn.execute(
            text("SELECT COUNT(*) FROM formula_validation_logs")
        )
        count = result.fetchone()[0]
        print(f"Total formula_validation_logs records: {count}")

        result = await conn.execute(text("SELECT COUNT(*) FROM sentences"))
        count = result.fetchone()[0]
        print(f"Total sentences records: {count}")


if __name__ == "__main__":
    asyncio.run(fix_entity_id_format())
