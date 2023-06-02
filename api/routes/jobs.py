from flask import Response, Blueprint, request
from src.job import Job
from src.jobs import get_jobs
import json

jobs = Blueprint('jobs', __name__)

@jobs.route('/', defaults={'page': 'index'})
def index(page):
  args = request.args.to_dict(flat=False) if request.args else {}
  result = get_jobs(args)
  return Response(json.dumps(result), mimetype='application/json')

@jobs.route('/<path:job_id>', methods = ['GET'])
def show(job_id=None):
  job = Job(job_id)
  return Response(json.dumps(job.display()), mimetype='application/json')

@jobs.route('/<path:job_id>/results', methods = ['GET'])
def results(job_id=None):
  job = Job(job_id)
  return Response(json.dumps(job.results()), mimetype='application/json')
