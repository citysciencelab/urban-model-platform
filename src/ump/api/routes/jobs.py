import asyncio
import json
import logging
from datetime import datetime, timezone

from apiflask import APIBlueprint
from flask import Response, g, request
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ump.api.job import Job
from ump.api.job_comments import JobComment
from ump.api.jobs import append_ensemble_list, get_jobs

jobs = APIBlueprint("jobs", __name__)

engine = create_engine("postgresql+psycopg2://postgres:postgres@postgis/cut_dev")


@jobs.route("/", defaults={"page": "index"})
def index(page):
    args = request.args.to_dict(flat=False) if request.args else {}
    result = get_jobs(args, g.get("auth_token"))
    if "include_ensembles" in args and args["include_ensembles"]:
        for job in result["jobs"]:
            append_ensemble_list(job)
    return Response(json.dumps(result), mimetype="application/json")


@jobs.route("/<path:job_id>/results", methods=["GET"])
def results(job_id=None):
    auth = g.get("auth_token")
    job = Job(job_id, None if auth is None else auth["sub"])
    return Response(json.dumps(asyncio.run(job.results())), mimetype="application/json")


@jobs.route("/<path:job_id>/comments", methods=["GET"])
def get_comments(job_id):
    auth = g.get("auth_token")
    if auth is None:
        return Response("[]", mimetype="application/json")
    with Session(engine) as session:
        stmt = select(JobComment).where(JobComment.job_id == job_id)
        list = []
        for comment in session.scalars(stmt).fetchall():
            list.append(comment.to_dict())
        return list


@jobs.route("/<path:job_id>/comments", methods=["POST"])
def create_comment(job_id):
    auth = g.get("auth_token")
    if auth is None:
        logging.error("Not creating comment, no authentication found.")
        return Response(
            '{"error_message": "not authenticated"}',
            mimetype="application/json",
            status=401,
        )
    comment = JobComment(
        user_id=auth["sub"],
        job_id=job_id,
        comment=request.get_json()["comment"],
        created=datetime.now(timezone.utc),
        modified=datetime.now(timezone.utc),
    )
    with Session(engine) as session:
        session.add(comment)
        session.commit()
        return Response(
            json.dumps(comment.to_dict()), mimetype="application/json", status=201
        )


@jobs.route("/<path:job_id>", methods=["GET"])
def show(job_id=None):
    auth = g.get("auth_token")
    job = Job(job_id, None if auth is None else auth["sub"]).display()
    append_ensemble_list(job)
    return Response(json.dumps(job), mimetype="application/json")
