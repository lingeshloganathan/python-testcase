# db_connection.py
import psycopg2

# PostgreSQL connection configuration
DB_CONFIG = {
    "host": "localhost",
    "database": "TestCases_priority",
    "user": "postgres",
    "password": "12345"
}

def create_tables():
    commands = (
        """ 
            CREATE TABLE IF NOT EXISTS regression_matrix (
            id SERIAL PRIMARY KEY,
            user_story_id VARCHAR(50) NOT NULL,
            commit_SHA text,
            author VARCHAR(100),
            file_changed varchar(255),
            changed_function text unique,
            dependent_function text,
            test_case_id VARCHAR(50) NOT NULL,
            test_name VARCHAR(255),
            total_no_of_Passed INT,
            total_no_of_Failed INT,
            last_status VARCHAR(20),
            last_execution_date TIMESTAMP
        )
        """
    )
    # conn = get_connection()
    conn = psycopg2.connect(**DB_CONFIG)
    if conn is not None:
        try:
            cur = conn.cursor()
            cur.execute(commands)
            conn.commit()
            cur.close()
            print("✅ Tables created successfully")
        except Exception as e:
            print("❌ Failed to create tables:", e)
        finally:
            conn.close()

if __name__ == "__main__":
    create_tables()