import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone
from multiprocessing import dummy

import aiohttp
from flask import g
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
import geopandas as gpd

from ump.api.entities import JobExecution, JobConfig
import ump.api.providers as providers
import ump.config as config
from ump.api.job import Job, JobStatus
from ump.errors import CustomException, InvalidUsage
from ump.geoserver.geoserver import Geoserver

logging.basicConfig(level=logging.INFO)

engine = create_engine("postgresql+psycopg2://postgres:postgres@postgis/cut_dev")

class Process:
    def __init__(self, process_id_with_prefix=None):

        self.inputs: dict
        self.outputs: dict

        self.process_id_with_prefix = process_id_with_prefix

        match = re.search(r"([^:]+):(.*)", self.process_id_with_prefix)
        if not match:
            raise InvalidUsage(
                f"Process ID {self.process_id_with_prefix} is not known! Please check endpoint api/processes for a list of available processes."
            )

        self.provider_prefix = match.group(1)
        self.process_id = match.group(2)

        if not providers.check_process_availability(
            self.provider_prefix, self.process_id
        ):
            raise InvalidUsage(
                f"Process ID {self.process_id_with_prefix} is not known! Please check endpoint api/processes for a list of available processes."
            )

        auth = g.get("auth_token")
        role = f"{self.provider_prefix}_{self.process_id}"
        restricted_access = (
            "authentication" in providers.PROVIDERS[self.provider_prefix]
        )

        if restricted_access:
            if (
                auth is None
                or self.provider_prefix not in auth["realm_access"]["roles"]
                and self.provider_prefix
                not in auth["resource_access"]["ump-client"]["roles"]
                and role not in auth["realm_access"]["roles"]
                and role not in auth["resource_access"]["ump-client"]["roles"]
            ):
                raise InvalidUsage(
                    f"Process ID {self.process_id_with_prefix} is not known! Please check endpoint api/processes for a list of available processes."
                )

        asyncio.run(self.set_details())

    async def set_details(self):
        p = providers.PROVIDERS[self.provider_prefix]

        # Check for Authentification
        auth = providers.authenticate_provider(p)

        async with aiohttp.ClientSession() as session:
            response = await session.get(
                f"{p['url']}/processes/{self.process_id}",
                auth=auth,
                headers={
                    "Content-type": "application/json",
                    "Accept": "application/json",
                },
            )

            if response.status != 200:
                raise InvalidUsage(
                    f"Model/process not found! {response.status}: {response.reason}. Check /api/processes endpoint for available models/processes."
                )

            process_details = await response.json()
            for key in process_details:
                setattr(self, key, process_details[key])

    def validate_params(self, parameters):
        if not self.inputs:
            return

        if not "job_name" in parameters:
            raise InvalidUsage(
                f"Parameter job_name is required",
                payload={"parameter_description": self.inputs["job_name"]},
            )

        for input in self.inputs:
            try:
                if not "schema" in self.inputs[input]:
                    continue

                parameter_metadata = self.inputs[input]
                schema = parameter_metadata["schema"]

                if not input in parameters["inputs"]:
                    if self.is_required(parameter_metadata):
                        raise InvalidUsage(
                            f"Parameter {input} is required",
                            payload={"parameter_description": parameter_metadata},
                        )
                    else:
                        logging.warn(
                            f"Model execution {self.process_id_with_prefix} started without parameter {input}."
                        )
                        continue

                param = parameters["inputs"][input]

                if "minimum" in schema:
                    assert param >= schema["minimum"]

                if "maximum" in schema:
                    assert param <= schema["maximum"]

                if "type" in schema:
                    if schema["type"] == "number":
                        assert (
                            type(param) == int
                            or type(param) == float
                            or type(param) == complex
                        )

                    if schema["type"] == "string":
                        assert type(param) == str

                        if "maxLength" in schema:
                            assert len(param) <= schema["maxLength"]

                        if "minLength" in schema:
                            assert len(param) >= schema["minLength"]

                    if schema["type"] == "array":
                        assert type(param) == list
                        if (
                            "items" in schema
                            and "type" in schema["items"]
                            and schema["items"]["type"] == "string"
                        ):
                            for item in param:
                                assert type(item) == str
                        if schema["items"]["type"] == "number":
                            for item in param:
                                assert (
                                    type(item) == int
                                    or type(item) == float
                                    or type(item) == complex
                                )
                        if "uniqueItems" in schema and schema["uniqueItems"]:
                            assert len(param) == len(set(param))
                        if "minItems" in schema:
                            assert len(param) >= schema["minItems"]

                if "pattern" in schema:
                    assert re.search(schema["pattern"], param)

            except AssertionError:
                raise InvalidUsage(
                    f"Invalid parameter {input} = {param}: does not match mandatory schema {schema}"
                )

    def is_required(self, parameter_metadata):
        if "required" in parameter_metadata:
            return parameter_metadata["required"]

        if "required" in parameter_metadata["schema"]:
            return parameter_metadata["schema"]["required"]

        if "minOccurs" in parameter_metadata:
            return parameter_metadata["minOccurs"] > 0

        return False

    def execute_config(self, job_config, user):
        with Session(engine) as session:
            p = providers.PROVIDERS[self.provider_prefix]

            self.validate_params(job_config.parameters)

            logging.info(
                f" --> Executing {job_config.process_id} on model server {p['url']} with params {job_config.parameters} as process {self.process_id_with_prefix} for user {user}"
            )

            job = asyncio.run(self.start_process_execution_config(job_config, user, session))

            _process = dummy.Process(target=self._wait_for_results_async, args=([job, job_config, session]))
            _process.start()

            result = {"jobID": job.job_id, "status": job.status}
            return result

    def execute(self, parameters, user, ensemble_id=None):
        p = providers.PROVIDERS[self.provider_prefix]

        self.validate_params(parameters)

        logging.info(
            f" --> Executing {self.process_id} on model server {p['url']} with params {parameters} as process {self.process_id_with_prefix} for user {user}"
        )

        job = asyncio.run(self.start_process_execution(parameters, user, ensemble_id))

        _process = dummy.Process(target=self._wait_for_results_async, args=([job]))
        _process.start()

        result = {"jobID": job.job_id, "status": job.status}
        return result

    async def start_process_execution_config(self, job_config, user, session):
        # execution mode:
        # to maintain backwards compatibility to models using
        # pre-1.0.0 versions of OGC api processes
        job_config.parameters["mode"] = "async"
        p = providers.PROVIDERS[self.provider_prefix]

        try:
            auth = providers.authenticate_provider(p)

            async with aiohttp.ClientSession() as http_session:
                process_response = await http_session.get(
                    f"{p['url']}/processes/{self.process_id}",
                    auth=auth,
                    headers={
                        "Content-type": "application/json",
                        "Accept": "application/json",
                    },
                )
                response = await http_session.post(
                    f"{p['url']}/processes/{self.process_id}/execution",
                    json=job_config.parameters,
                    auth=auth,
                    headers={
                        "Content-type": "application/json",
                        "Accept": "application/json",
                        # execution mode shall be async, if model supports it
                        "Prefer": "respond-async",
                    },
                )

                process_response.raise_for_status()

                if process_response.ok:
                    process_details = await process_response.json()
                    self.process_title = process_details["title"]

                response.raise_for_status()

                if response.ok and response.headers:
                    # Retrieve the job id from the simulation model server from the
                    # location header:
                    match = re.search(
                        "http.*/jobs/(.*)$", response.headers["location"]
                    ) or (re.search(".*/jobs/(.*)$", response.headers["location"]))
                    if match:
                        remote_job_id = match.group(1)

                    job = JobExecution(
                        remote_job_id = remote_job_id,
                        job_config_id = job_config.id,
                        job_id = f"job-{remote_job_id}",
                        created = datetime.now(timezone.utc),
                        started = datetime.now(timezone.utc),
                        user_id = user,
                        status = JobStatus.running.value
                    )

                    session.add(job)
                    session.commit()

                    logging.info(
                        f" --> Job {job.job_id} for model {self.process_id_with_prefix} started running."
                    )

                    return job

        except Exception as e:
            raise CustomException(f"Job could not be started remotely: {e}")

    async def start_process_execution(self, request_body, user, ensemble_id=None):
        # execution mode:
        # to maintain backwards compatibility to models using
        # pre-1.0.0 versions of OGC api processes
        request_body["mode"] = "async"
        p = providers.PROVIDERS[self.provider_prefix]

        # extract job_name from request_body
        name = request_body.pop("job_name")

        try:
            auth = providers.authenticate_provider(p)

            async with aiohttp.ClientSession() as session:
                process_response = await session.get(
                    f"{p['url']}/processes/{self.process_id}",
                    auth=auth,
                    headers={
                        "Content-type": "application/json",
                        "Accept": "application/json",
                    },
                )
                response = await session.post(
                    f"{p['url']}/processes/{self.process_id}/execution",
                    json=request_body,
                    auth=auth,
                    headers={
                        "Content-type": "application/json",
                        "Accept": "application/json",
                        # execution mode shall be async, if model supports it
                        "Prefer": "respond-async",
                    },
                )

                process_response.raise_for_status()

                if process_response.ok:
                    process_details = await process_response.json()
                    self.process_title = process_details["title"]

                response.raise_for_status()

                if response.ok and response.headers:
                    # Retrieve the job id from the simulation model server from the
                    # location header:
                    match = re.search(
                        "http.*/jobs/(.*)$", response.headers["location"]
                    ) or (re.search(".*/jobs/(.*)$", response.headers["location"]))
                    if match:
                        remote_job_id = match.group(1)

                    job = Job()
                    job.create(
                        remote_job_id=remote_job_id,
                        process_id_with_prefix=self.process_id_with_prefix,
                        process_title=self.process_title,
                        name=name,
                        parameters=request_body,
                        user=user,
                        ensemble_id=ensemble_id,
                    )
                    job.started = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                    job.status = JobStatus.running.value
                    job.save()

                    logging.info(
                        f" --> Job {job.job_id} for model {self.process_id_with_prefix} started running."
                    )

                    return job

        except Exception as e:
            raise CustomException(f"Job could not be started remotely: {e}")

    def _wait_for_results_async(self, job: JobExecution, job_config: JobConfig, session):
        asyncio.run(self._wait_for_results(job, job_config, session))

    async def _wait_for_results(self, job: JobExecution, job_config: JobConfig, session):

        logging.info(" --> Waiting for results in Thread")

        finished = False
        p = providers.PROVIDERS[self.provider_prefix]
        timeout = float(p["timeout"])
        start = time.time()
        job_details = {}

        try:
            while not finished:

                async with aiohttp.ClientSession() as http_session:

                    auth = providers.authenticate_provider(p)
                    async with http_session.get(
                        f"{p['url']}/jobs/{job.remote_job_id}",
                        auth=auth,
                        headers={
                            "Content-type": "application/json",
                            "Accept": "application/json",
                        },
                    ) as response:

                        response.raise_for_status()
                        job_details: dict = await response.json()

                finished = self.is_finished(job_details)

                logging.info(" --> Current Job status: " + str(job_details))

                # either remote job has progress info or else we cannot provide it either
                job.progress = job_details.get("progress")

                job.updated = datetime.now(timezone.utc)
                session.add(job)
                session.commit()

                if time.time() - start > timeout:
                    raise TimeoutError(
                        f"Job did not finish within {timeout/60} minutes. Giving up."
                    )

                time.sleep(config.fetch_job_results_interval)

            logging.info(
                f" --> Remote execution job {job.remote_job_id}: success = {finished}. Took approx. {int((time.time() - start)/60)} minutes."
            )

        except Exception as e:
            logging.error(
                f" --> Could not retrieve results for job {self.process_id_with_prefix} (={job_config.process_id})/{job.job_id} from simulation model server: {e}"
            )
            job.status = JobStatus.failed.value
            job.message = str(e)
            job.updated = datetime.now(timezone.utc)
            job.finished = job.updated
            job.progress = 100
            session.add(job)
            session.commit()
            raise CustomException(
                "Could not retrieve results from simulation model server. {e}"
            )

        # Check if job was successful
        try:
            if job_details["status"] != JobStatus.successful.value:
                job.status = JobStatus.failed.value
                job.finished = datetime.now(timezone.utc)
                job.updated = job.finished
                job.progress = 100
                job.message = (
                    f'Remote execution was not successful! {job_details["message"]}'
                )
                session.add(job)
                session.commit()
                raise CustomException(f"Remote job {job.remote_job_id}: {job.message}")

        except CustomException as e:
            logging.error(f" --> An error occurred: {e}")

        job.status = JobStatus.successful.value
        job.finished = datetime.now(timezone.utc)
        job.updated = job.finished
        job.progress = 100
        session.add(job)
        session.commit()

        # Check if results should be stored in the geoserver
        try:
            if (
                providers.check_result_storage(self.provider_prefix, job_config.process_id)
                == "geoserver"
            ):
                await self.results_to_geoserver(job)
        except Exception as e:
            logging.error(
                f" --> Could not store results for job {self.process_id_with_prefix} (={job_config.process_id})/{job.job_id} to geoserver: {e}"
            )
            job.message = str(e)
            session.add(job)
            session.commit()

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
            if type == "float64" and results_df[column].apply(float.is_integer).all():
                type = "int"

            values.append(
                {
                    column: {
                        "type": type,
                        "min": minimal_values_dict[column],
                        "max": maximal_values_dict[column],
                    }
                }
            )

        for column in results_df.select_dtypes(include=[object]).to_dict():
            values.append(
                {column: {"type": "string", "values": list(set(results_df[column]))}}
            )

        results_metadata = {"values": values}

        return results_metadata

    async def results(self, execution):
        if execution.status != JobStatus.successful.value:
            return {
                "error": f"No results available. Job status = {execution.status}.",
                "message": execution.message,
            }

        p = providers.PROVIDERS[self.provider_prefix]

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
                    f"Could not retrieve results from model server {self.provider_url} - {response.status}: {response.reason}"
                )

    async def results_to_geoserver(self, execution):
        try:
            geoserver = Geoserver()
            results = self.results(execution)

            execution.results_metadata = self.set_results_metadata(results)

            geoserver.save_results(job_id=execution.job_id, data=results)

            logging.info(
                f" --> Successfully stored results for job {self.process_id_with_prefix} (={execution.process_id})/{execution.job_id} to geoserver."
            )

        except Exception as e:
            logging.error(
                f" --> Could not store results for job {self.process_id_with_prefix} (={execution.process_id})/{execution.job_id} to geoserver: {e}"
            )

    def is_finished(self, job_details):
        finished = False

        if "finished" in job_details and job_details["finished"]:
            finished = True

        if job_details["status"] in [
            JobStatus.dismissed.value,
            JobStatus.failed.value,
            JobStatus.successful.value,
        ]:
            finished = True

        return finished

    def to_dict(self):
        process_dict = self.__dict__
        process_dict.pop("process_id")
        process_dict.pop("provider_prefix")
        process_dict["id"] = process_dict.pop("process_id_with_prefix")

        # delete all keys containing None
        for key, value in list(process_dict.items()):
            if value is None:
                process_dict.pop(key)

        return process_dict

    def to_json(self):
        return json.dumps(
            self.to_dict(), default=lambda o: o.__dict__, sort_keys=True, indent=2
        )

    def __str__(self):
        return f"src.process.Process object: process_id={self.process_id}, process_id_with_prefix={self.process_id_with_prefix}, provider_prefix={self.provider_prefix}"

    def __repr__(self):
        return f"src.process.Process(process_id={self.process_id})"
