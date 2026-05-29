import sqlite3


def print_table_schema(db_path, table_name):
    print("\n==========================================")
    print(f"DB: {db_path} | Table: {table_name}")
    print("==========================================")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # 1. Print sqlite_master SQL schema
    c.execute(f"SELECT sql FROM sqlite_master WHERE name='{table_name}'")
    schema = c.fetchone()
    if schema:
        print("Schema:")
        print(schema[0])
    else:
        print(f"Table '{table_name}' not found!")
        conn.close()
        return

    # 2. Print indexes
    c.execute(f"PRAGMA index_list({table_name})")
    indexes = c.fetchall()
    print("\nIndexes:")
    for idx in indexes:
        print(idx)
        # Print index columns
        c.execute(f"PRAGMA index_info({idx[1]})")
        cols = c.fetchall()
        print("  Columns:", cols)

    # 3. Print table info
    c.execute(f"PRAGMA table_info({table_name})")
    tbl_info = c.fetchall()
    print("\nTable Info:")
    for col in tbl_info:
        print(col)

    conn.close()


for db in ["bb-paxdata.db", "bb-paxdata-temp.db"]:
    for table in ["country_stats", "topic_matrix"]:
        print_table_schema(db, table)
