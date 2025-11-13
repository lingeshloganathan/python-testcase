# db_connection.py
import psycopg2
import logging

# Try to get DB config from central config_loader if available
try:
    import config_loader as cfg
    cfg.setup_logging()
    _conf = cfg.load_config()
except Exception:
    _conf = {}

logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host": _conf.get('host', 'localhost'),
    "database": _conf.get('database', 'postgres'),
    "user": _conf.get('user', 'postgres'),
    # psycopg2 accepts port as int or string
    "port": str(_conf.get('port', 5432)),
    "password": _conf.get('password', '1976')
}


def get_connection():
    """Return a new PostgreSQL connection using DB_CONFIG.

    Falls back to DB_CONFIG defaults if central config is absent.
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logger.info("✅ Database connection established to %s:%s/%s", DB_CONFIG.get('host'), DB_CONFIG.get('port'), DB_CONFIG.get('database'))
        return conn
    except Exception as e:
        logger.exception("❌ Database connection failed: %s", e)
        return None


def create_tables():
    command = """
        CREATE TABLE IF NOT EXISTS regression_matrix (
            id SERIAL PRIMARY KEY,
            user_story_id VARCHAR(50) NOT NULL,
            commit_SHA TEXT,
            author VARCHAR(100),
            file_changed VARCHAR(255),
            changed_function TEXT UNIQUE,
            dependent_function TEXT,
            test_case_id VARCHAR(50),
            test_name VARCHAR(255),
            total_no_of_Passed INT,
            total_no_of_Failed INT,
            last_status VARCHAR(20),
            last_execution_date TIMESTAMP
        );
    """
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(command)
            conn.commit()
            cur.close()
            logger.info("✅ Table created successfully")
        except Exception as e:
            logger.exception("❌ Failed to create table: %s", e)
        finally:
            conn.close()


if __name__ == "__main__":
    create_tables()
