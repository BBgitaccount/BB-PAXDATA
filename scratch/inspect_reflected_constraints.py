import shutil

from sqlalchemy import MetaData, create_engine

engine = create_engine("sqlite:///bb-paxdata.db")
metadata = MetaData()

# Let's restore the db first so we can reflect

try:
    shutil.copy("bb-paxdata.db.bak", "bb-paxdata.db")
except Exception as e:
    print(e)

metadata.reflect(bind=engine)
for name, table in metadata.tables.items():
    if name == "ai_panel_synthesis":
        print(f"Table: {name}")
        print("Foreign Keys:")
        for fk in table.foreign_keys:
            print(f"  FK: {fk} | name: {fk.name} | constraint: {fk.constraint.name}")
        print("Constraints:")
        for const in table.constraints:
            print(f"  Const: {const} | name: {const.name}")
