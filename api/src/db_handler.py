import configs.config as config
import psycopg2 as db
from psycopg2.extras import RealDictCursor

import logging

logger = logging.getLogger(__name__)

class DBHandler():
  def __init__(self):
    self.connection = db.connect(
      database = config.postgres_db,
      host     = config.postgres_host,
      user     = config.postgres_user,
      password = config.postgres_password,
      port     = config.postgres_port
    )
    self.sortable_columns = []

  def set_sortable_columns(self, sortable_columns):
    self.sortable_columns = sortable_columns

  def run_query(self, query, conditions=[], query_params={}, order=[], limit=None, page=None):
    if conditions:
      query += " WHERE " + " AND ".join(conditions)

    if order and set(order).issubset(set(self.sortable_columns)):
      query += f" ORDER BY {', '.join(order)} DESC"
    elif order:
      logging.debug(f" --> Could not order by {order} since sortable_columns hasn't been set! Please call set_sortable_columns!")

    if limit:
      offset = 0
      if page:
        offset = (page - 1) * limit

      query += " LIMIT %(limit)s OFFSET %(offset)s"
      query_params['limit'] = limit
      query_params['offset'] = offset

    #logging.debug(f" --> SQL query = {query}")
    #logging.debug(f" --> query_params = {query_params}")

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

  def __exit__(self, type, value, traceback):
    if (self.connection):
      self.connection.close()

    if type is None and value is None and traceback is None:
      return True

    logger.error(f"{type}: {value} - {traceback}")
    return False
