from datetime import datetime
import uuid
import json
import ump.config as config
from ump.api.db_handler import DBHandler
from ump.api.job_status import JobStatus
import requests
import logging
import yaml
import geopandas as gpd
import re
from ump.errors import InvalidUsage, CustomException

PROVIDERS: dict = {}

with open(config.PROVIDERS_FILE) as file:
  if content:=yaml.safe_load(file):
    PROVIDERS.update(
        content
  )

class Job:
  DISPLAYED_ATTRIBUTES = [
      "processID", "type", "jobID", "status", "message",
      "created", "started", "finished", "updated", "progress",
      "links", "parameters", "results_metadata"
    ]

  SORTABLE_COLUMNS = ['created', 'finished', 'updated', 'started', 'process_id', 'status', 'message']

  def __init__(self, job_id=None):
    self.job_id            = job_id
    self.status            = None
    self.message           = ""
    self.progress          = 0
    self.created           = None
    self.started           = None
    self.finished          = None
    self.updated           = None
    self.results_metadata  = {}

    if job_id and not self._init_from_db(job_id):
        raise CustomException(f"Job could not be found!")

  def create(self, job_id=None, remote_job_id=None, process_id_with_prefix=None, parameters={}):
    self._set_attributes(job_id=job_id, remote_job_id=remote_job_id, process_id_with_prefix=process_id_with_prefix, parameters=parameters)

    self.status    = JobStatus.accepted.value
    self.created   = datetime.utcnow()
    self.updated   = datetime.utcnow()

    query = """
      INSERT INTO jobs
      (job_id, remote_job_id, process_id, provider_prefix, provider_url, status, progress, parameters, message, created, started, finished, updated)
      VALUES
      (%(job_id)s, %(remote_job_id)s, %(process_id)s, %(provider_prefix)s, %(provider_url)s, %(status)s, %(progress)s, %(parameters)s, %(message)s, %(created)s, %(started)s, %(finished)s, %(updated)s)
    """
    with DBHandler() as db:
      db.run_query(query, query_params=self._to_dict())

    logging.info(f" --> Job {self.job_id} for {self.process_id} created.")

  def _set_attributes(self, job_id=None, remote_job_id=None, process_id_with_prefix=None, parameters={}):
    self.job_id = job_id
    self.remote_job_id = remote_job_id

    if remote_job_id and not job_id:
      self.job_id = f"job-{remote_job_id}"

    if job_id and not remote_job_id:
      match = re.search('job-(.*)$', job_id)
      self.remote_job_id = match.group(1)

    self.process_id_with_prefix = process_id_with_prefix
    self.parameters             = parameters

    if process_id_with_prefix:
      match = re.search(r'(.*):(.*)', self.process_id_with_prefix)
      if not match:
        raise InvalidUsage(f"Process ID {self.process_id_with_prefix} is not known! Please check endpoint api/processes for a list of available processes.")

      self.provider_prefix = match.group(1)
      self.process_id      = match.group(2)
      self.provider_url    = PROVIDERS[self.provider_prefix]['url']

    if not self.job_id:
      self.job_id  = str(uuid.uuid4())

  def _init_from_db(self, job_id):
    query = """
      SELECT * FROM jobs WHERE job_id = %(job_id)s
    """
    with DBHandler() as db:
      job_details = db.run_query(query, query_params={'job_id': job_id})

    if len(job_details) > 0:
      self._init_from_dict(dict(job_details[0]))
      return True
    else:
      return False

  def _init_from_dict(self, data):
    self.job_id           = data['job_id']
    self.remote_job_id    = data['remote_job_id']
    self.process_id       = data['process_id']
    self.provider_prefix  = data['provider_prefix']
    self.provider_url     = data['provider_url']
    self.process_id_with_prefix = f"{data['provider_prefix']}:{data['process_id']}"
    self.status           = data['status']
    self.message          = data['message']
    self.created          = data['created']
    self.started          = data['started']
    self.finished         = data['finished']
    self.updated          = data['updated']
    self.progress         = data['progress']
    self.parameters       = data['parameters']
    self.results_metadata = data['results_metadata']

  def _to_dict(self):
    return {
      "process_id": self.process_id,
      "job_id":     self.job_id,
      "remote_job_id": self.remote_job_id,
      "provider_prefix": self.provider_prefix,
      "provider_url": self.provider_url,
      "status":     self.status,
      "message":    self.message,
      "created":    self.created,
      "started":    self.started,
      "finished":   self.finished,
      "updated":    self.updated,
      "progress":   self.progress,
      "parameters": json.dumps(self.parameters),
      "results_metadata": json.dumps(self.results_metadata)
    }

  def save(self):
    self.updated = datetime.utcnow()

    query = """
      UPDATE jobs SET
      (process_id, provider_prefix, provider_url, status, progress, parameters, message, created, started, finished, updated, results_metadata)
      =
      (%(process_id)s, %(provider_prefix)s, %(provider_url)s, %(status)s, %(progress)s, %(parameters)s, %(message)s, %(created)s, %(started)s, %(finished)s, %(updated)s, %(results_metadata)s)
      WHERE job_id = %(job_id)s
    """
    with DBHandler() as db:
      db.run_query(query, query_params=self._to_dict())

  def set_results_metadata(self, results_as_json):
    results_df = gpd.GeoDataFrame.from_features(results_as_json)

    minimal_values_df = results_df.min(numeric_only=True)
    maximal_values_df = results_df.max(numeric_only=True)

    minimal_values_dict = minimal_values_df.to_dict()
    maximal_values_dict = maximal_values_df.to_dict()

    types = results_df.dtypes.to_dict()

    values = []
    for column in maximal_values_dict:

      type = str(types[column])
      if type == 'float64' and results_df[column].apply(float.is_integer).all():
        type = 'int'

      values.append(
        {
          column:
          {
            "type": type,
            "min":  minimal_values_dict[column],
            "max":  maximal_values_dict[column]
          }
        }
      )

    for column in results_df.select_dtypes(include=[object]).to_dict():
      values.append(
        {
          column:
          {
            "type": "string",
            "values": list(set(results_df[column]))
          }
        }
      )

    self.results_metadata = { "values": values }

    return self.results_metadata

  def display(self):
    job_dict = self._to_dict()
    job_dict["type"] = "process"
    job_dict["jobID"] = job_dict.pop("job_id")
    job_dict["parameters"] = self.parameters
    job_dict["results_metadata"] = self.results_metadata
    job_dict["processID"] = self.process_id_with_prefix
    job_dict["links"] = []

    for attr in job_dict:
      if isinstance(job_dict[attr], datetime):
        job_dict[attr] = job_dict[attr].strftime('%Y-%m-%dT%H:%M:%S.%fZ')

    if self.status in (
      JobStatus.successful.value,
      JobStatus.running.value,
      JobStatus.accepted.value
    ):

        job_result_url = f"{config.api_server_url}/api/jobs/{self.job_id}/results"

        job_dict['links'] = [{
            'href': job_result_url,
            'rel': 'service',
            'type': 'application/json',
            'hreflang': 'en',
            'title': f'Results of job {self.job_id} as geojson - available when job is finished.'
        }]

    return {k: job_dict[k] for k in self.DISPLAYED_ATTRIBUTES}

  def results(self):
    if self.status != JobStatus.successful.value:
      return { "error": f"No results available. Job status = {self.status}.", "message": self.message }

    p = PROVIDERS[self.provider_prefix]
    self.provider_url    = p['url']

    response = requests.get(
        f"{self.provider_url}/jobs/{self.remote_job_id}/results?f=json",
        auth    = (p['user'], p['password']),
        headers = {'Content-type': 'application/json', 'Accept': 'application/json'}
      )
    if response.ok:
      return response.json()
    else:
      raise CustomException(f"Could not retrieve results from model server {self.provider_url} - {response.status_code}: {response.reason}")

  def __str__(self):
    return f"""
      ----- src.job.Job -----
      job_id={self.job_id}, process_id={self.process_id},
      status={self.status}, message={self.message},
      progress={self.progress}, parameters={self.parameters},
      started={self.started}, created={self.created},
      finished={self.finished}, updated={self.updated}
    """

  def __repr__(self):
    return f'src.job.Job(job_id={self.job_id})'
