import os
import sqlite3


def recreate_tables(db_path: str):
    if not os.path.exists(db_path):
        print(f"Database {db_path} does not exist. Skipping.")
        return

    print(f"Recreating stats tables in {db_path}...")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    try:
        # Enable foreign keys
        c.execute("PRAGMA foreign_keys = OFF;")

        # 1. Recreate country_stats
        c.execute("DROP TABLE IF EXISTS country_stats;")
        c.execute("""
            CREATE TABLE "country_stats" (
                country TEXT NOT NULL, 
                n_segments INTEGER NOT NULL, 
                n_sentences INTEGER NOT NULL, 
                total_words INTEGER NOT NULL, 
                total_duration_sec INTEGER NOT NULL, 
                words_per_minute FLOAT, 
                avg_sentiment FLOAT, 
                dominant_emotion TEXT, 
                dominant_topic TEXT, 
                topic_scores JSON, 
                file_id VARCHAR NOT NULL, 
                CONSTRAINT pk_country_stats PRIMARY KEY (country, file_id), 
                CONSTRAINT fk_country_stats_file_id_files FOREIGN KEY(file_id) REFERENCES files (file_id)
            );
        """)

        # 2. Recreate topic_matrix
        c.execute("DROP TABLE IF EXISTS topic_matrix;")
        c.execute("""
            CREATE TABLE "topic_matrix" (
                file_id VARCHAR NOT NULL, 
                country TEXT NOT NULL, 
                topic TEXT NOT NULL, 
                score FLOAT NOT NULL, 
                CONSTRAINT pk_topic_matrix PRIMARY KEY (file_id, country, topic), 
                CONSTRAINT fk_topic_matrix_file_id_files FOREIGN KEY(file_id) REFERENCES files (file_id)
            );
        """)

        c.execute("PRAGMA foreign_keys = ON;")
        conn.commit()
        print(f"Successfully recreated tables in {db_path}.")
    except Exception as e:
        print(f"Error recreating tables in {db_path}: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    recreate_tables("paxdata.db")
    recreate_tables("paxdata-temp.db")
