import json
import time
from datetime import datetime
import re
from multiprocessing import dummy
import requests
import yaml

from src.job import Job, JobStatus
from src.geoserver import Geoserver
from src.errors import InvalidUsage, CustomException

PROVIDERS = yaml.safe_load(open('./configs/providers.yml'))

import logging

logging.basicConfig(level=logging.INFO)

class Process():
  def __init__(self, process_id_with_prefix=None):
    self.process_id_with_prefix = process_id_with_prefix

    match = re.search(r'(.*):(.*)', self.process_id_with_prefix)
    if not match:
      raise InvalidUsage(f"Process ID {self.process_id_with_prefix} is not known! Please check endpoint api/processes for a list of available processes.")

    self.provider_prefix = match.group(1)
    self.process_id = match.group(2)

    if not self.process_id or not self.provider_prefix in PROVIDERS.keys():
      raise InvalidUsage(f"Process ID {self.process_id_with_prefix} is not known! Please check endpoint api/processes for a list of available processes.")

    self.set_details()

  def set_details(self):
    p = PROVIDERS[self.provider_prefix]

    response = requests.get(
      f"{p['url']}/processes/{self.process_id}",
      auth    = (p['user'], p['password']),
      headers = {'Content-type': 'application/json', 'Accept': 'application/json'}
    )

    if response.ok:
      process_details = response.json()
      for key in process_details:
        setattr(self, key, process_details[key])
    else:
      raise InvalidUsage(f"Model/process not found! {response.status_code}: {response.reason}. Check /api/processes endpoint for available models/processes.")

  def validate_params(self, parameters):
    if not self.inputs:
      return

    for input in self.inputs:
      try:
        if not "schema" in self.inputs[input]:
          continue

        parameter_metadata = self.inputs[input]
        schema = parameter_metadata["schema"]

        if not input in parameters["inputs"]:
          if self.is_required(parameter_metadata):
            raise InvalidUsage(f"Parameter {input} is required", payload={"parameter_description": parameter_metadata})
          else:
            logging.warn(f"Model execution {self.process_id_with_prefix} started without parameter {input}.")
            continue

        param = parameters["inputs"][input]

        if "minimum" in schema:
          assert param >= schema["minimum"]

        if "maximum" in schema:
          assert param <= schema["maximum"]

        if "type" in schema:
          if schema["type"] == "number":
            assert type(param) == int or type(param) == float or type(param) == complex

          if schema["type"] == "string":
            assert type(param) == str

            if "maxLength" in schema:
              assert len(param) <= schema["maxLength"]

            if "minLength" in schema:
              assert len(param) >= schema["minLength"]

          if schema["type"] == "array":
            assert type(param) == list
            if "items" in schema and "type" in schema["items"] and schema["items"]["type"] == "string":
              for item in param:
                assert type(item) == str
            if schema["items"]["type"] == "number":
              for item in param:
                assert type(item) == int or type(item) == float or type(item) == complex
            if "uniqueItems" in schema and schema["uniqueItems"]:
              assert len(param) == len(set(param))
            if "minItems" in schema:
              assert len(param) >= schema["minItems"]

        if "pattern" in schema:
          assert re.search(schema["pattern"], param)

      except AssertionError:
        raise InvalidUsage(f"Invalid parameter {input} = {param}: does not match mandatory schema {schema}")

  def is_required(self, parameter_metadata):
    if "required" in parameter_metadata:
      return parameter_metadata["required"]

    if "required" in parameter_metadata["schema"]:
      return parameter_metadata["schema"]["required"]

    if "minOccurs" in parameter_metadata:
      return (parameter_metadata["minOccurs"] > 0)

    return False

  def execute(self, parameters):
    p = PROVIDERS[self.provider_prefix]

    self.validate_params(parameters)

    logging.info(f" --> Executing {self.process_id} on model server {p['url']} with params {parameters} as process {self.process_id_with_prefix}")

    job = self.start_process_execution(parameters)

    _process = dummy.Process(
            target=self._wait_for_results,
            args=([job])
        )
    _process.start()

    result = {
      "job_id": job.job_id,
      "status": job.status
    }
    return result

  def start_process_execution(self, params):
    params["mode"] = "async"
    p = PROVIDERS[self.provider_prefix]

    try:
      response = requests.post(
          f"{p['url']}/processes/{self.process_id}/execution",
          json    = params,
          auth    = (p['user'], p['password']),
          headers = {'Content-type': 'application/json', 'Accept': 'application/json'}
        )

      response.raise_for_status()

      if response.ok and response.headers:
        # Retrieve the job id from the simulation model server from the location header:
        match = re.search('http.*/jobs/(.*)$', response.headers["location"])
        if match:
          remote_job_id = match.group(1)

        job = Job()
        job.create(remote_job_id=remote_job_id, process_id_with_prefix=self.process_id_with_prefix, parameters=params)
        job.started = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        job.status = JobStatus.running.value
        job.save()

        logging.info(f' --> Job {job.job_id} for model {self.process_id_with_prefix} started running.')

        return job

    except Exception as e:
       raise CustomException(f"Job could not be started remotely: {e}")

  def _wait_for_results(self, job):
    finished = False
    p = PROVIDERS[self.provider_prefix]
    timeout = float(p['timeout'])
    start = time.time()

    try:
      while not finished:
        response = requests.get(
            f"{p['url']}/jobs/{job.remote_job_id}",
            auth    = (p['user'], p['password']),
            headers = {'Content-type': 'application/json', 'Accept': 'application/json'}
          )
        response.raise_for_status()

        job_details = response.json()

        finished = self.is_finished(job_details)

        job.progress = job_details["progress"]
        job.updated = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        job.save()

        if time.time() - start > timeout:
          raise TimeoutError(f"Job did not finish within {timeout/60} minutes. Giving up.")

      logging.info(f" --> Remote execution job {job.remote_job_id}: success = {finished}. Took approx. {int((time.time() - start)/60)} minutes.")

    except Exception as e:
      logging.error(f" --> Could not retrieve results for job {self.process_id_with_prefix} (={self.process_id})/{job.job_id} from simulation model server: {e}")
      job.status = JobStatus.failed.value
      job.message = str(e)
      job.updated = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
      job.finished = job.updated
      job.progress = 100
      job.save()
      raise CustomException("Could not retrieve results from simulation model server. {e}")

    try:
      if job_details["status"] != JobStatus.successful.value:
        job.status = JobStatus.failed.value
        job.finished = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        job.updated = job.finished
        job.progress = 100
        job.message = f'Remote execution was not successful! {job_details["message"]}'
        job.save()
        raise CustomException(f"Remote job {job.remote_job_id}: {job.message}")

      geoserver = Geoserver()

      response = requests.get(
          f"{p['url']}/jobs/{job.remote_job_id}/results?f=json",
          auth    = (p['user'], p['password']),
          headers = {'Content-type': 'application/json', 'Accept': 'application/json'}
        )
      response.raise_for_status()

      if not response.ok:
        job.status = JobStatus.failed.value
        job.message = f'Could not retrieve results for {job}! {response.status_code}: {response.reason}'
      else:
        results = response.json()

        job.set_results_metadata(results)

        geoserver.save_results(
          job_id    = job.job_id,
          data      = results
        )

      logging.info(f" --> Successfully stored results for job {self.process_id_with_prefix} (={self.process_id})/{job.job_id} to geoserver.")
      job.status = JobStatus.successful.value

    except CustomException as e:
      logging.error(f" --> Could not store results for job {self.process_id_with_prefix} (={self.process_id})/{job.job_id} to geoserver: {e}")
      job.status = JobStatus.failed.value
      job.message = str(e)

    job.finished = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    job.updated = job.finished
    job.progress = 100
    job.save()

    try:
      geoserver.cleanup()
    except Exception as e:
      pass

  def is_finished(self, job_details):
    finished = False

    if "job_end_datetime" in job_details and job_details["job_end_datetime"]:
      finished = True

    if "finished" in job_details and job_details["finished"]:
      finished = True

    if job_details["status"] in [JobStatus.dismissed.value, JobStatus.failed.value]:
      finished = True

    return finished

  def to_dict(self):
    process_dict = self.__dict__
    process_dict.pop("process_id")
    process_dict.pop("provider_prefix")
    process_dict["id"] = process_dict.pop("process_id_with_prefix")
    return process_dict

  def to_json(self):
    return json.dumps(self.to_dict(), default=lambda o: o.__dict__,
      sort_keys=True, indent=2)

  def __str__(self):
    return f'src.process.Process object: process_id={self.process_id}, process_id_with_prefix={self.process_id_with_prefix}, provider_prefix={self.provider_prefix}'

  def __repr__(self):
    return f'src.process.Process(process_id={self.process_id})'
