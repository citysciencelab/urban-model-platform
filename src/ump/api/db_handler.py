import logging
import psycopg2.pool

import psycopg2 as db
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine

from ump import config

logger = logging.getLogger(__name__)
# Note: differnt part of the code use differnt Database handling strategies,
# should be unified sometime!

# Initialize the connection pool
connection_pool = psycopg2.pool.SimpleConnectionPool(
    minconn=1,  # Minimum number of connections
    maxconn=49,  # Maximum number of connections, lower than postgres default
    database = config.postgres_db,
    host     = config.postgres_host,
    user     = config.postgres_user,
    password = config.postgres_password,
    port     = config.postgres_port
)

db_engine = engine = create_engine(
    (
        "postgresql+psycopg2://"
        f"{config.postgres_user}:{config.postgres_password}"
        f"@{config.postgres_host}:{config.postgres_port}"
        f"/{config.postgres_db}"
    ),
    pool_size=49,  # Maximum number of connections in the pool
    max_overflow=1,  # Additional connections allowed beyond pool_size
    pool_timeout=30,  # Timeout for getting a connection from the pool
    pool_recycle=3600,  # Recycle connections after 1 hour
)

def close_pool():
    """Close the connection pool."""
    if connection_pool:
        connection_pool.closeall()

class DBHandler():
    def __init__(self):
        self.connection = None
        self.sortable_columns = []

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
        self.connection = connection_pool.getconn()
        return self

    def __exit__(self, exc_type, value, traceback):
        if self.connection:
            connection_pool.putconn(self.connection)
            self.connection = None

        if exc_type is None and value is None and traceback is None:
            return True

        logger.error("%s: %s - %s", exc_type, value, traceback)
        return False
