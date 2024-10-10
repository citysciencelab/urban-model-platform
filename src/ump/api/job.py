import json
import logging
import re
import uuid
from datetime import datetime, timezone

import aiohttp
import geopandas as gpd

import ump.api.providers as providers
import ump.config as config
from ump.api.db_handler import DBHandler
from ump.api.job_status import JobStatus
from ump.errors import CustomException, InvalidUsage
from ump.geoserver.geoserver import Geoserver


class Job:
    DISPLAYED_ATTRIBUTES = [
        "processID",
        "type",
        "jobID",
        "status",
        "message",
        "created",
        "started",
        "finished",
        "updated",
        "progress",
        "links",
        "parameters",
        "results_metadata",
        "name",
        "process_title",
        "process_version",
        "user_id",
    ]

    SORTABLE_COLUMNS = [
        "created",
        "finished",
        "updated",
        "started",
        "process_id",
        "status",
        "message",
    ]

    def __init__(self, job_id=None, user=None):
        self.job_id = job_id
        self.status = None
        self.message = ""
        self.progress = 0
        self.created = None
        self.started = None
        self.finished = None
        self.updated = None
        self.results_metadata = {}
        self.user_id = None
        self.name = None
        self.process_title = None
        self.process_version = None
        self.remote_job_id = None
        self.process_id_with_prefix = None
        self.parameters = None
        self.provider_prefix = None
        self.process_id = None
        self.provider_url = None

        if job_id and not self._init_from_db(job_id, user):
            raise CustomException("Job could not be found!")

    def create(
        self,
        job_id=None,
        remote_job_id=None,
        process_id_with_prefix=None,
        process_title=None,
        name=None,
        parameters=None,
        user=None,
        process_version=None,
    ):
        self._set_attributes(
            job_id,
            remote_job_id,
            process_id_with_prefix,
            process_title,
            name,
            parameters,
            user_id=user,
            process_version=process_version,
        )

        self.status = JobStatus.accepted.value
        self.created = datetime.now(timezone.utc)
        self.updated = datetime.now(timezone.utc)

        query = """
            INSERT INTO jobs
            (job_id, remote_job_id, process_id, provider_prefix, provider_url, status, progress, parameters, message, created, started, finished, updated, user_id, process_title, name, process_version)
            VALUES
            (%(job_id)s, %(remote_job_id)s, %(process_id)s, %(provider_prefix)s, %(provider_url)s, %(status)s, %(progress)s, %(parameters)s, %(message)s, %(created)s, %(started)s, %(finished)s, %(updated)s, %(user_id)s, %(process_title)s, %(name)s, %(process_version)s)
        """
        with DBHandler() as db:
            logging.error(self._to_dict())
            db.run_query(query, query_params=self._to_dict())

        logging.info(" --> Job %s for %s created.", self.job_id, self.process_id)

    def _set_attributes(
        self,
        job_id=None,
        remote_job_id=None,
        process_id_with_prefix=None,
        process_title=None,
        name=None,
        parameters=None,
        user_id=None,
        process_version=None,
    ):
        self.job_id = job_id
        self.remote_job_id = remote_job_id
        self.user_id = user_id
        self.process_title = process_title
        self.name = name
        self.process_version = process_version

        if remote_job_id and not job_id:
            self.job_id = f"job-{remote_job_id}"

        if job_id and not remote_job_id:
            match = re.search("job-(.*)$", job_id)
            self.remote_job_id = match.group(1)

        self.process_id_with_prefix = process_id_with_prefix
        self.parameters = parameters

        if process_id_with_prefix:
            match = re.search(r"(.*):(.*)", self.process_id_with_prefix)
            if not match:
                raise InvalidUsage(
                    f"Process ID {self.process_id_with_prefix} is not known! " +
                    "Please check endpoint api/processes for a list of available processes."
                )

            self.provider_prefix = match.group(1)
            self.process_id = match.group(2)
            self.provider_url = providers.PROVIDERS[self.provider_prefix]["url"]

        if not self.job_id:
            self.job_id = str(uuid.uuid4())

    def _init_from_db(self, job_id, user):
        query = """
      SELECT j.* FROM jobs j left join jobs_users u on j.job_id = u.job_id WHERE j.job_id = %(job_id)s
    """
        if user is None:
            query += " and j.user_id is null"
        else:
            query += f" and (j.user_id = '{user}' or j.user_id is null or u.user_id = '{user}')"

        with DBHandler() as db:
            job_details = db.run_query(query, query_params={"job_id": job_id})

        if len(job_details) > 0:
            logging.error(job_details[0])
            self._init_from_dict(dict(job_details[0]))
            return True
        return False

    def _init_from_dict(self, data):
        self.job_id = data["job_id"]
        self.remote_job_id = data["remote_job_id"]
        self.process_id = data["process_id"]
        self.provider_prefix = data["provider_prefix"]
        self.provider_url = data["provider_url"]
        self.process_id_with_prefix = f"{data['provider_prefix']}:{data['process_id']}"
        self.status = data["status"]
        self.message = data["message"]
        self.created = data["created"]
        self.started = data["started"]
        self.finished = data["finished"]
        self.updated = data["updated"]
        self.progress = data["progress"]
        self.parameters = data["parameters"]
        self.results_metadata = data["results_metadata"]
        self.user_id = data["user_id"]
        self.process_title = data["process_title"]
        self.name = data["name"]
        self.process_version = data["process_version"]
        logging.error('next')
        logging.error(data)
        logging.error(self._to_dict())
        logging.error(self.display())

    def _to_dict(self):
        return {
            "process_id": self.process_id,
            "job_id": self.job_id,
            "remote_job_id": self.remote_job_id,
            "provider_prefix": self.provider_prefix,
            "provider_url": self.provider_url,
            "status": self.status,
            "message": self.message,
            "created": self.created,
            "started": self.started,
            "finished": self.finished,
            "updated": self.updated,
            "progress": self.progress,
            "process_title": self.process_title,
            "name": self.name,
            "parameters": json.dumps(self.parameters),
            "results_metadata": json.dumps(self.results_metadata),
            "user_id": self.user_id,
            "process_version": self.process_version,
        }

    def save(self):
        self.updated = datetime.now(timezone.utc)

        query = """
            UPDATE jobs SET
            (process_id, provider_prefix, provider_url, status, progress, parameters, message, created, started, finished, updated, results_metadata, process_version)
            =
            (%(process_id)s, %(provider_prefix)s, %(provider_url)s, %(status)s, %(progress)s, %(parameters)s, %(message)s, %(created)s, %(started)s, %(finished)s, %(updated)s, %(results_metadata)s, %(process_version)s)
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

            data_type = str(types[column])
            if data_type == "float64" and results_df[column].apply(float.is_integer).all():
                data_type = "int"

            values.append(
                {
                    column: {
                        "type": data_type,
                        "min": minimal_values_dict[column],
                        "max": maximal_values_dict[column],
                    }
                }
            )

        for column in results_df.select_dtypes(include=[object]).to_dict():
            try:
                values.append(
                    {
                        column: {
                            "type": "string",
                            "values": list(set(results_df[column])),
                        }
                    }
                )
            except Exception as e:
                logging.error("Unable to store column %s, skipping: %s", column, e)

        self.results_metadata = {"values": values}

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
                job_dict[attr] = job_dict[attr].strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        if self.status in (
            JobStatus.successful.value,
            JobStatus.running.value,
            JobStatus.accepted.value,
        ):

            job_result_url = f"{config.api_server_url}/api/jobs/{self.job_id}/results"

            job_dict["links"] = [
                {
                    "href": job_result_url,
                    "rel": "service",
                    "type": "application/json",
                    "hreflang": "en",
                    "title": f"Results of job {self.job_id} as geojson" +
                        " - available when job is finished.",
                }
            ]

        return {k: job_dict[k] for k in self.DISPLAYED_ATTRIBUTES}

    async def results(self):
        if self.status != JobStatus.successful.value:
            return {
                "error": f"No results available. Job status = {self.status}.",
                "message": self.message,
            }

        p = providers.PROVIDERS[self.provider_prefix]
        self.provider_url = p["url"]

        async with aiohttp.ClientSession() as session:
            auth = providers.authenticate_provider(p)

            response = await session.get(
                f"{self.provider_url}/jobs/{self.remote_job_id}/results?f=json",
                auth=auth,
                headers={
                    "Content-type": "application/json",
                    "Accept": "application/json",
                },
            )

            if response.status == 200:
                return await response.json()
            else:
                raise CustomException(
                    "Could not retrieve results from model server " +
                    f"{self.provider_url} - {response.status}: {response.reason}"
                )

    async def results_to_geoserver(self):
        try:

            results = await self.results()
            while "results" in results:
                results = results["results"]
            geoserver = Geoserver()

            self.set_results_metadata(results)

            geoserver.save_results(job_id=self.job_id, data=results)

            logging.info(
                " --> Successfully stored results for job %s (=%s)/%s to geoserver.",
                self.process_id_with_prefix, self.process_id, self.job_id
            )

        except Exception as e:
            logging.error(
                " --> Could not store results for job %s (=%s)/%s to geoserver: %s",
                self.process_id_with_prefix,
                self.process_id,
                self.job_id,
                e,
            )

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
        return f"src.job.Job(job_id={self.job_id})"
