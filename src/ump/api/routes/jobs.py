import asyncio
import json
import logging
from datetime import datetime, timezone

from apiflask import APIBlueprint
from flask import Response, g, request
from sqlalchemy import create_engine, select, or_
from sqlalchemy.orm import Session

from ump.api.keycloak import find_user_id_by_email
from ump.api.ensemble import JobsUsers
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

@jobs.route("/<path:job_id>/share/<path:email>", methods=["GET"])
def share(job_id=None, email=None):
    auth = g.get('auth_token')
    id = find_user_id_by_email(email)
    if id is None:
        logging.error(f"Unable to find user by email {email}.")
        return Response(status = 404)
    job = Job(job_id, None if auth is None else auth['sub'])
    if job is None:
        logging.error(f"Unable to find job with id {job_id}.")
        return Response(status = 404)

    with Session(engine) as session:
        row = JobsUsers(job_id = job_id, user_id = id)
        session.add(row)
        session.commit()
        return Response(status = 201)

@jobs.route("/<path:job_id>/comments", methods=["GET"])
def get_comments(job_id):
    auth = g.get("auth_token")
    if auth is None:
        return Response("[]", mimetype="application/json")
    with Session(engine) as session:
        stmt = (
            select(JobComment)
            .join(JobsUsers, JobsUsers.job_id == JobComment.job_id, isouter = True)
            .where(or_(JobComment.user_id == auth["sub"], JobsUsers.user_id == auth['sub']))
            .where(JobComment.job_id == job_id)
        )
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
