import builtins
import copy
import json
import logging

from apiflask import APIBlueprint
from flask import Response, g, request
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ump.api.ensemble import Comment, Ensemble, JobsEnsembles
from ump.api.process import Process
from ump.api.job import Job

ensembles = APIBlueprint("ensembles", __name__)

engine = create_engine("postgresql+psycopg2://postgres:postgres@postgis/cut_dev")

@ensembles.route("/", methods=["GET"])
def index():
    auth = g.get("auth_token")
    if auth is None:
        return Response("[]", mimetype="application/json")
    with Session(engine) as session:
        stmt = select(Ensemble).where(Ensemble.user_id == auth["sub"])
        result = session.scalars(stmt).fetchall()
        list = []
        for ensemble in result:
            list.append(ensemble.to_dict())
        return list

@ensembles.route("/", methods=["POST"])
def create():
    auth = g.get("auth_token")
    if auth is None:
        logging.error("Not creating ensemble, no authentication found.")
        return Response("Unauthorized. No ensemble created", status=401)
    data = request.get_json()
    ensemble = Ensemble(
        name=data.get("name"),
        description=data.get("description"),
        user_id=auth.get("sub"),
        scenario_configs=json.dumps(data.get("scenario_configs")),
    )
    with Session(engine) as session:
        session.add(ensemble)
        session.commit()
        return Response(
            json.dumps(ensemble._to_dict()), status=201, mimetype="application/json"
        )


@ensembles.route("/<path:ensemble_id>/comments", methods=["GET"])
def get_comments(ensemble_id):
    auth = g.get("auth_token")
    if auth is None:
        return Response("[]", mimetype="application/json")
    with Session(engine) as session:
        stmt = (
            select(Comment)
            .where(Comment.user_id == auth["sub"])
            .where(Comment.ensemble_id == ensemble_id)
        )
        list = []
        for comment in session.scalars(stmt).fetchall():
            list.append(comment.to_dict())
        return list


@ensembles.route("/<path:ensemble_id>/comments", methods=["POST"])
def create_comment(ensemble_id):
    auth = g.get("auth_token")
    if auth is None:
        logging.error("Not creating comment, no authentication found.")
        return Response("", mimetype="application/json")
    comment = Comment(
        user_id=auth["sub"],
        ensemble_id=ensemble_id,
        comment=request.get_json()["comment"],
    )
    with Session(engine) as session:
        session.add(comment)
        session.commit()
        return Response(mimetype="application/json", status=201)


@ensembles.route("/<path:ensemble_id>", methods=["GET"])
def get(ensemble_id):
    auth = g.get("auth_token")
    if auth is None:
        return Response("[]", mimetype="application/json")
    with Session(engine) as session:
        stmt = (
            select(Ensemble)
            .where(Ensemble.user_id == auth["sub"])
            .where(Ensemble.id == ensemble_id)
        )
        return session.scalar(stmt).to_dict()
    return Response(json.dumps(""), mimetype="application/json")

@ensembles.route("/<path:ensemble_id>/jobs", methods=["GET"])
def jobs(ensemble_id):
    auth = g.get("auth_token")
    if auth is None:
        return Response("[]", mimetype="application/json")
    with Session(engine) as session:
        stmt = select(JobsEnsembles).where(JobsEnsembles.ensemble_id == ensemble_id)
        ids = session.scalars(stmt).fetchall()
        list = []
        for row in ids:
            list.append(Job(row.job_id, auth['sub']).display())
        return Response(json.dumps(list), mimetype="application/json")

@ensembles.route("/<path:ensemble_id>/execute", methods=["GET"])
def execute(ensemble_id):
    auth = g.get("auth_token")
    if auth is None:
        return Response("[]", mimetype="application/json")
    with Session(engine) as session:
        stmt = (
            select(Ensemble)
            .where(Ensemble.user_id == auth["sub"])
            .where(Ensemble.id == ensemble_id)
        )
        ensemble = session.scalar(stmt)
        if ensemble is None:
            return Response("No such scenario", status=400)
        jobs = create_jobs(ensemble, auth)
        for job in jobs:
            session.add(JobsEnsembles(ensemble_id = ensemble_id, job_id = job['jobID']))
        session.commit()
        return Response(json.dumps(jobs), mimetype="application/json")

def create_jobs_for_config(config):
    list = [{"process_id": config["process_id"], "inputs": {}}]
    for param in config["parameters"].keys():
        val = config["parameters"][param]
        match val:
            case builtins.list():
                old_list = list
                list = []
                for v in val:
                    for item in old_list:
                        x = copy.deepcopy(item)
                        x["inputs"][param] = v
                        list.append(x)
            case dict():
                old_list = list
                list = []
                for v in range(val["from"], val["to"], val["step"]):
                    for item in old_list:
                        x = copy.deepcopy(item)
                        x["inputs"][param] = v
                        list.append(x)
            case _:
                for cfg in list:
                    cfg["inputs"][param] = val
    return list


def create_jobs(ensemble: Ensemble, auth):
    configs = ensemble.scenario_configs
    list = []
    for config in configs:
        list = list + create_jobs_for_config(config)
    result_list = []
    for config in list:
        process = Process(config["process_id"])
        result_list.append(
            process.execute(
                {"job_name": ensemble.name, "inputs": config["inputs"]},
                auth["sub"],
                ensemble_id=ensemble.id,
            )
        )
    return result_list
