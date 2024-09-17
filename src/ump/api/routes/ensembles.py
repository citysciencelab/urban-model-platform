import json
import builtins
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, select
from apiflask import APIBlueprint
from flask import Response, g, request, jsonify
from ump.api.ensemble import Ensemble, Comment
import logging
import copy
from ump.api.process import Process

ensembles = APIBlueprint("ensembles", __name__)

engine = create_engine('postgresql+psycopg2://postgres:postgres@postgis/cut_dev')

@ensembles.route("/", methods = ['GET'])
def index():
    auth = g.get('auth_token')
    if auth is None:
        return Response('[]', mimetype = 'application/json')
    with Session(engine) as session:
        stmt = select(Ensemble).where(Ensemble.user_id == auth['sub'])
        return jsonify(session.scalars(stmt).fetchall())

@ensembles.route("/", methods=["POST"])
def create():
    auth = g.get('auth_token')
    if auth is None:
        logging.error('Not creating ensemble, no authentication found.')
        return Response('', mimetype = 'application/json')
    data = request.get_json()
    ensemble = Ensemble(
        name = data['name'],
        description = data['description'],
        user_id = auth['sub'],
        scenario_configs = json.dumps(data['scenario_configs'])
    )
    with Session(engine) as session:
        session.add(ensemble)
        session.commit()
        return Response(mimetype="application/json", status = 201)

@ensembles.route('/<path:ensemble_id>/comments', methods = ['GET'])
def get_comments(ensemble_id):
    auth = g.get('auth_token')
    if auth is None:
        return Response('[]', mimetype = 'application/json')
    with Session(engine) as session:
        stmt = select(Comment).where(Comment.user_id == auth['sub']).where(Comment.ensemble_id == ensemble_id)
        return jsonify(session.scalars(stmt).fetchall())

@ensembles.route("/<path:ensemble_id>/comments", methods=["POST"])
def create_comment(ensemble_id):
    auth = g.get('auth_token')
    if auth is None:
        logging.error('Not creating comment, no authentication found.')
        return Response('', mimetype = 'application/json')
    comment = Comment(
        user_id = auth['sub'],
        ensemble_id = ensemble_id,
        comment = request.get_json()['comment']
    )
    with Session(engine) as session:
        session.add(comment)
        session.commit()
        return Response(mimetype="application/json", status = 201)

@ensembles.route("/<path:ensemble_id>", methods=["GET"])
def get(ensemble_id):
    auth = g.get('auth_token')
    if auth is None:
        return Response('[]', mimetype = 'application/json')
    with Session(engine) as session:
        stmt = select(Ensemble).where(Ensemble.user_id == auth['sub']).where(Ensemble.id == ensemble_id)
        return jsonify(session.scalars(stmt).fetchall())
    return Response(json.dumps(''), mimetype="application/json")

@ensembles.route("/<path:ensemble_id>/execute", methods=["GET"])
def execute(ensemble_id):
    auth = g.get('auth_token')
    if auth is None:
        return Response('[]', mimetype = 'application/json')
    with Session(engine) as session:
        stmt = select(Ensemble).where(Ensemble.user_id == auth['sub']).where(Ensemble.id == ensemble_id)
        ensembles = session.scalars(stmt).fetchall()
        if len(ensembles) == 0:
            return Response('No such scenario', status = 400)
        return create_jobs(ensembles[0], auth)

def create_jobs_for_config(config):
    list = [{
        'process_id': config['process_id'],
        'inputs': {}
    }]
    for param in config['parameters'].keys():
        val = config['parameters'][param]
        match val:
            case builtins.list():
                old_list = list
                list = []
                for v in val:
                    for item in old_list:
                        x = copy.deepcopy(item)
                        x['inputs'][param] = v
                        list.append(x)
            case dict():
                old_list = list
                list = []
                for v in range(val['from'], val['to'], val['step']):
                    for item in old_list:
                        x = copy.deepcopy(item)
                        x['inputs'][param] = v
                        list.append(x)
            case _:
                for cfg in list:
                    cfg['inputs'][param] = val
    return list

def create_jobs(ensemble: Ensemble, auth):
    configs = ensemble.scenario_configs
    list = []
    for config in configs:
        list = list + create_jobs_for_config(config)
    result_list = []
    for config in list:
        process = Process(config['process_id'])
        result_list.append(process.execute({'job_name': ensemble.name, 'inputs': config['inputs']}, auth['sub'], ensemble_id = ensemble.id))
    return Response(json.dumps(result_list), mimetype="application/json")
