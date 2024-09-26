import asyncio
import json

from apiflask import APIBlueprint
from flask import Response, g, request, jsonify
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ump.api.job import Job
from ump.api.jobs import get_jobs
from ump.api.entities import JobConfig

jobs = APIBlueprint("jobs", __name__)

engine = create_engine('postgresql+psycopg2://postgres:postgres@postgis/cut_dev')

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

@jobs.route("/config", methods = ['POST'])
def create_config():
    auth = g.get('auth_token')
    if auth is None:
        return Response(status = 401)
    data = request.get_json()
    config = JobConfig(**data)
    config.user_id = auth['sub']
    with Session(engine) as session:
        session.add(config)
        session.commit()
        return Response(status = 201)

@jobs.route("/config", methods = ['GET'])
def get_configs():
    auth = g.get('auth_token')
    if auth is None:
        return Response(status = 401)
    with Session(engine) as session:
        stmt = select(JobConfig).where(JobConfig.user_id == auth['sub'])
        list = []
        for row in session.scalars(stmt).fetchall():
            list.append(row.to_dict(rules = ['-ensembles.job_configs']))
        return jsonify(list)
