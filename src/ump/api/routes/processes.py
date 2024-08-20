import asyncio
import json

from apiflask import APIBlueprint
from flask import Response, request

from ump.api.process import Process
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
    process = Process(process_id_with_prefix)
    result = process.execute(request.json)
    return Response(json.dumps(result), status=201, mimetype="application/json")
