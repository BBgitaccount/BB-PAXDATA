"""Audit demand_records table."""

from bb_paxdata.infrastructure.db.models import DemandRecord
from bb_paxdata.infrastructure.db.session import get_db_session

with get_db_session() as session:
    print("Total rows:", session.query(DemandRecord).count())

    # Check column fill rates
    total = session.query(DemandRecord).count()
    print(f"\nColumn fill rates (total: {total}):")
    print(f"  sent_id: {session.query(DemandRecord.sent_id).count()}")
    print(f"  seg_id: {session.query(DemandRecord.seg_id).count()}")
    print(f"  demand_type: {session.query(DemandRecord.demand_type).count()}")
    print(f"  demand_verb: {session.query(DemandRecord.demand_verb).count()}")
    print(f"  demand_category: {session.query(DemandRecord.demand_category).count()}")
    print(f"  target_entity: {session.query(DemandRecord.target_entity).count()}")

    # Sample rows
    print("\nSample rows:")
    rows = session.query(DemandRecord).limit(5).all()
    for r in rows:
        print(
            f"ID: {r.demand_id}, sent_id: {r.sent_id}, demand_type: {r.demand_type}, demand_verb: {r.demand_verb}"
        )
