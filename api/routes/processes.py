from flask import Response, Blueprint, request
from src.processes import all_processes
from src.process import Process
import json
import asyncio

processes = Blueprint('processes', __name__)

@processes.route('/', defaults={'page': 'index'})
def index(page):
  result = asyncio.run(all_processes())
  return Response(json.dumps(result), mimetype='application/json')

@processes.route('/<path:process_id_with_prefix>', methods = ['GET'])
def show(process_id_with_prefix=None):
  process = Process(process_id_with_prefix)
  return Response(process.to_json(), mimetype='application/json')

@processes.route('/<path:process_id_with_prefix>/execution', methods = ['POST'])
def execute(process_id_with_prefix=None):
  process = Process(process_id_with_prefix)
  result = process.execute(request.json)
  return Response(json.dumps(result), status=201, mimetype='application/json')
