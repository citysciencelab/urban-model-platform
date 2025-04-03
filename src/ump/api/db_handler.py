import logging

import psycopg2 as db
import psycopg2.pool
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine

from ump.config import app_settings as config

logger = logging.getLogger(__name__)
# Note: differnt part of the code use differnt Database handling strategies,
# should be unified sometime!

# Initialize the connection pool
connection_pool = psycopg2.pool.SimpleConnectionPool(
    minconn=1,  # Minimum number of connections
    maxconn=49,  # Maximum number of connections, lower than postgres default
    database = config.UMP_DATABASE_NAME,
    host     = config.UMP_DATABASE_HOST,
    user     = config.UMP_DATABASE_USER,
    password = config.UMP_DATABASE_PASSWORD,
    port     = config.UMP_DATABASE_PORT
)

db_engine = engine = create_engine(
    (
        "postgresql+psycopg2://"
        f"{config.UMP_DATABASE_USER}:{config.UMP_DATABASE_PASSWORD}"
        f"@{config.UMP_DATABASE_HOST}:{config.UMP_DATABASE_PORT}"
        f"/{config.UMP_DATABASE_NAME}"
    ),
    pool_size=49,  # Maximum number of connections in the pool
    max_overflow=1,  # Additional connections allowed beyond pool_size
    pool_timeout=30,  # Timeout for getting a connection from the pool
    pool_recycle=3600,  # Recycle connections after 1 hour
)

def close_pool():
    """Close the connection pool."""
    global connection_pool

    if connection_pool:
        try:
            connection_pool.closeall()
            connection_pool = None  # Mark the pool as closed
            logger.info("Connection pool closed.")
        except psycopg2.pool.PoolError as e:
            logger.warning("Connection pool is already closed: %s", e)

class DBHandler():
    def __init__(self):
        self.connection = connection_pool.getconn()

    def set_sortable_columns(self, sortable_columns):
        self.sortable_columns = sortable_columns

    def run_query(
            self,
            query,
            conditions=None,
            query_params=None,
            order=None,
            limit=None,
            page=None
        ):
        if query_params is None:
            query_params = {}
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        if order and set(order).issubset(set(self.sortable_columns)):
            query += f" ORDER BY {', '.join(order)} DESC"
        elif order:
            logging.debug(
                " --> Could not order by %s since sortable_columns hasn't been set!" +
                " Please call set_sortable_columns!",
                order
              )

        if limit:
            offset = 0
            if page:
                offset = (page - 1) * limit

            query += " LIMIT %(limit)s OFFSET %(offset)s"
            query_params['limit'] = limit
            query_params['offset'] = offset

        with self.connection:
            with self.connection.cursor(cursor_factory = RealDictCursor) as cursor:
                cursor.execute(query, query_params)
                try:
                    results = cursor.fetchall()
                except db.ProgrammingError as e:
                    if str(e) == "no results to fetch":
                        return
                    else:
                        raise e

        return results

    # needed so that this class can be used as a context manager
    def __enter__(self):
        return self

    def __exit__(self, exc_type, value, traceback):
        if self.connection:
            connection_pool.putconn(self.connection)

        if exc_type is None and value is None and traceback is None:
            return True

        logger.error("%s: %s - %s", exc_type, value, traceback)
        return False
