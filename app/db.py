from contextlib import contextmanager
import app.extensions as ext


@contextmanager
def get_db():
    conn = ext.db_pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        ext.db_pool.putconn(conn)
