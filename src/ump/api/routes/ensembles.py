"""The ensemble related routes"""
import builtins
import copy
import json
import logging

from apiflask import APIBlueprint
from ema_workbench import CategoricalParameter, RealParameter
from ema_workbench.em_framework.samplers import (
    FullFactorialSampler,
    LHSSampler,
    MonteCarloSampler,
    UniformLHSSampler,
    sample_parameters,
)
from flask import Response, g, request
from names_generator import generate_name
from sqlalchemy import create_engine, delete, or_, select
from sqlalchemy.orm import Session

from ump.api.ensemble import Comment, Ensemble, EnsemblesUsers, JobsEnsembles
from ump.api.job import Job
from ump.api.keycloak_utils import find_user_id_by_email
from ump.api.process import Process

ensembles = APIBlueprint("ensembles", __name__)

engine = create_engine("postgresql+psycopg2://postgres:postgres@postgis/cut_dev")


def add_job_fields(ensemble: Ensemble):
    """Adds the synthetic jobs_metadata field"""
    with engine.begin() as conn:
        result = conn.exec_driver_sql(
            """select count(*), j.status from jobs j
            right join jobs_ensembles je on j.job_id = je.job_id
            where je.ensemble_id = %(id)s group by j.status""",
            {"id": ensemble.id},
        )
        ensemble.jobs_metadata = {}
        for row in result:
            ensemble.jobs_metadata[row.status] = row.count


@ensembles.route("/", methods=["GET"])
def index():
    """Gets all ensembles the current user has access to"""
    auth = g.get("auth_token")
    if auth is None:
        return Response("[]", mimetype="application/json")
    with Session(engine) as session:
        stmt = (
            select(Ensemble)
            .join(
                EnsemblesUsers, EnsemblesUsers.ensemble_id == Ensemble.id, isouter=True
            )
            .where(
                or_(
                    Ensemble.user_id == auth["sub"],
                    EnsemblesUsers.user_id == auth["sub"],
                )
            )
        )
        result = session.scalars(stmt).fetchall()
        response = []
        for ensemble in result:
            add_job_fields(ensemble)
            response.append(ensemble.to_dict(rules=["jobs_metadata"]))
        return response


@ensembles.route("/", methods=["POST"])
def create():
    """Create an ensemble"""
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
        add_job_fields(ensemble)
        return Response(
            json.dumps(ensemble.to_dict(rules=["jobs_metadata"])),
            status=201,
            mimetype="application/json",
        )


@ensembles.route("/<path:ensemble_id>/comments", methods=["GET"])
def get_comments(ensemble_id):
    """Get the comments for an ensemble"""
    auth = g.get("auth_token")
    if auth is None:
        return Response("[]", mimetype="application/json")
    with Session(engine) as session:
        stmt = (
            select(Ensemble)
            .join(
                EnsemblesUsers, EnsemblesUsers.ensemble_id == Ensemble.id, isouter=True
            )
            .where(
                or_(
                    Ensemble.user_id == auth["sub"],
                    EnsemblesUsers.user_id == auth["sub"],
                )
            )
            .where(Ensemble.id == ensemble_id)
        )
        ensemble = session.scalar(stmt)
        if ensemble is None:
            return Response(status=404)
        stmt = (
            select(Comment)
            .join(
                EnsemblesUsers, EnsemblesUsers.ensemble_id == ensemble_id, isouter=True
            )
            .where(
                or_(
                    Comment.user_id == auth["sub"],
                    EnsemblesUsers.user_id == auth["sub"],
                )
            )
            .where(Comment.ensemble_id == ensemble_id)
        )
        results = []
        for comment in session.scalars(stmt).fetchall():
            results.append(comment.to_dict())
        return results


@ensembles.route("/<path:ensemble_id>/share/<path:email>", methods=["GET"])
def share(ensemble_id=None, email=None):
    """Share an ensemble with another user"""
    auth = g.get('auth_token')
    user_id = find_user_id_by_email(email)
    if user_id is None:
        logging.error("Unable to find user by email %s.", email)
        return Response(status = 404)
    with Session(engine) as session:
        stmt = (
            select(Ensemble)
            .join(
                EnsemblesUsers, EnsemblesUsers.ensemble_id == Ensemble.id, isouter=True
            )
            .where(
                or_(
                    Ensemble.user_id == auth["sub"],
                    EnsemblesUsers.user_id == auth["sub"],
                )
            )
            .where(Ensemble.id == ensemble_id)
        )
        ensemble = session.scalar(stmt)
        if ensemble is None:
            return Response(status=404)

        row = EnsemblesUsers(ensemble_id = ensemble_id, user_id = user_id)
        session.add(row)
        session.commit()
        return Response(status=201)


@ensembles.route("/<path:ensemble_id>/comments", methods=["POST"])
def create_comment(ensemble_id):
    """Create a comment for an ensemble"""
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
        return Response(
            json.dumps(comment.to_dict()), mimetype="application/json", status=201
        )


@ensembles.route("/<path:ensemble_id>", methods=["GET"])
def get(ensemble_id):
    """Get an ensemble by id"""
    auth = g.get("auth_token")
    if auth is None:
        return Response("[]", mimetype="application/json")
    with Session(engine) as session:
        stmt = (
            select(Ensemble)
            .join(
                EnsemblesUsers, EnsemblesUsers.ensemble_id == Ensemble.id, isouter=True
            )
            .where(
                or_(
                    Ensemble.user_id == auth["sub"],
                    EnsemblesUsers.user_id == auth["sub"],
                )
            )
            .where(Ensemble.id == ensemble_id)
        )
        ensemble = session.scalar(stmt)
        add_job_fields(ensemble)
        return ensemble.to_dict(rules=["jobs_metadata"])
    return Response(json.dumps(""), mimetype="application/json")


@ensembles.route("/<path:ensemble_id>/jobs", methods=["GET"])
def jobs(ensemble_id):
    """Get all jobs included in an ensemble"""
    auth = g.get("auth_token")
    if auth is None:
        return Response("[]", mimetype="application/json")
    with Session(engine) as session:
        stmt = select(JobsEnsembles).where(JobsEnsembles.ensemble_id == ensemble_id)
        ids = session.scalars(stmt).fetchall()
        results = []
        for row in ids:
            results.append(Job(row.job_id, auth["sub"]).display())
        return Response(json.dumps(results), mimetype="application/json")


@ensembles.route("/<path:ensemble_id>/jobs/<path:job_id>", methods=["DELETE"])
def delete_job_from_ensemble(ensemble_id, job_id):
    """Delete a job from an ensemble"""
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
            return Response(status=404)
        stmt = (
            delete(JobsEnsembles)
            .where(JobsEnsembles.ensemble_id == ensemble_id)
            .where(JobsEnsembles.job_id == job_id)
        )
        session.execute(stmt)
        session.commit()
        return Response(status=204, mimetype="application/json")


@ensembles.route("/<path:ensemble_id>/execute", methods=["GET"])
def execute(ensemble_id):
    """Create and execute the jobs in this ensemble"""
    auth = g.get("auth_token")
    if auth is None:
        return Response("[]", mimetype="application/json")
    with Session(engine) as session:
        stmt = (
            select(Ensemble)
            .join(
                EnsemblesUsers, EnsemblesUsers.ensemble_id == Ensemble.id, isouter=True
            )
            .where(
                or_(
                    Ensemble.user_id == auth["sub"],
                    EnsemblesUsers.user_id == auth["sub"],
                )
            )
            .where(Ensemble.id == ensemble_id)
        )
        ensemble = session.scalar(stmt)
        if ensemble is None:
            return Response("No such ensemble", status=400)
        job_list = create_jobs(ensemble, auth)
        for job in job_list:
            session.add(JobsEnsembles(ensemble_id=ensemble_id, job_id=job["jobID"]))
        session.commit()
        return Response(json.dumps(job_list), mimetype="application/json")


def create_jobs_for_config(config):
    """Creates the job configurations for an ensemble using
    the configured parameters and sampling method"""
    params = []
    process_config = {"process_id": config["process_id"], "inputs": {}}
    sampler = None
    match config["sampling_method"]:
        case "lhs":
            sampler = LHSSampler()
        case "uniformlhs":
            sampler = UniformLHSSampler()
        case "factorial":
            sampler = FullFactorialSampler()
        case "montecarlo":
            sampler = MonteCarloSampler()
    for param in config["parameters"].keys():
        val = config["parameters"][param]
        match val:
            case builtins.list():
                if len(val) > 1:
                    params.append(CategoricalParameter(param, val))
                else:
                    process_config["inputs"][param] = val[0]
            case dict():
                params.append(RealParameter(param, val["from"], val["to"]))
            case _:
                process_config["inputs"][param] = val
    samples = sample_parameters(params, config["sample_size"], sampler=sampler)
    results = []
    for sample in samples:
        x = copy.deepcopy(process_config)
        x["inputs"] = x["inputs"] | dict(sample)
        results.append(x)
    return results


def create_jobs(ensemble: Ensemble, auth):
    """Create the jobs for an ensemble"""
    configs = ensemble.scenario_configs
    results = []
    for config in configs:
        results = results + create_jobs_for_config(config)
    result_list = []
    for config in results:
        process = Process(config["process_id"])
        job_name = ensemble.name + " - " + generate_name(style="plain")
        result_list.append(
            process.execute(
                {"job_name": f"{job_name}", "inputs": config["inputs"]},
                auth["sub"],
                ensemble_id=ensemble.id,
            )
        )
    return result_list
