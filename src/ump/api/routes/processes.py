import asyncio
import copy
import json

from apiflask import APIBlueprint
from flask import Response, g, request

import ump.api.providers as providers
from ump.api.models.process import Process
from ump.api.processes import all_processes

processes = APIBlueprint("processes", __name__)

@processes.route("/", defaults={"page": "index"})
def index(page):
    result = asyncio.run(all_processes())
    return Response(json.dumps(result), mimetype="application/json")


@processes.route("/<path:process_id_with_prefix>", methods=["GET"])
def show(process_id_with_prefix=None):
    process = Process(process_id_with_prefix)
    return Response(process.to_json(), mimetype="application/json")


@processes.route("/<path:process_id_with_prefix>/execution", methods=["POST"])
def execute(process_id_with_prefix=None):
    auth = g.get('auth_token')
    process = Process(process_id_with_prefix)
    result = process.execute(request.json, None if auth is None else auth['sub'])
    return Response(json.dumps(result), status=201, mimetype="application/json")

# TODO: this lists ALL providers in providers.yaml, ignoring "exclude: True"
@processes.route("/providers", methods=["GET"])
def get_providers():
    """Returns the providers config"""
    response = copy.deepcopy(providers.PROVIDERS)
    for key in response:
        if 'authentication' in response[key]:
            del response[key]['authentication']
        del response[key]['url']
        if 'timeout' in response[key]:
            del response[key]['timeout']
        for process in response[key]['processes']:
            if 'deterministic' in response[key]['processes'][process]:
                del response[key]['processes'][process]['deterministic']
            if 'anonymous-access' in response[key]['processes'][process]:
                del response[key]['processes'][process]['anonymous-access']
    return response
