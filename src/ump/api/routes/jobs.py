import asyncio
import json

from apiflask import APIBlueprint
from flask import Response, g, request

from ump.api.job import Job
from ump.api.jobs import get_jobs

jobs = APIBlueprint("jobs", __name__)

@jobs.route("/", defaults={"page": "index"})
def index(page):
    args = request.args.to_dict(flat=False) if request.args else {}
    result = get_jobs(args, g.get('auth_token'))
    return Response(json.dumps(result), mimetype="application/json")

@jobs.route("/<path:job_id>", methods=["GET"])
def show(job_id=None):
    auth = g.get('auth_token')
    job = Job(job_id, None if auth is None else auth['sub'])
    return Response(json.dumps(job.display()), mimetype="application/json")

@jobs.route("/<path:job_id>/results", methods=["GET"])
def results(job_id=None):
    auth = g.get('auth_token')
    job = Job(job_id, None if auth is None else auth['sub'])
    return Response(json.dumps(asyncio.run(job.results())), mimetype="application/json")
