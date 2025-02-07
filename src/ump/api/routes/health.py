from flask import Blueprint
from ump.api.db_handler import DBHandler

health_bp = Blueprint('health', __name__)

@health_bp.route('/ready')
def readiness():
    query = "SELECT 1"
    with DBHandler() as db:
        try:
            db.run_query(query)
            return {'status': 'ok'}, 200
        except Exception:
            return {'status': 'error'}, 503