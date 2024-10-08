import asyncio
import json
import logging
import re
import time
from datetime import datetime
from multiprocessing import dummy

import aiohttp
import yaml

import ump.api.providers as providers
import ump.config as config
from ump.api.job import Job, JobStatus
from ump.errors import CustomException, InvalidUsage
from ump.geoserver.geoserver import Geoserver

logging.basicConfig(level=logging.INFO)


class Process:
    def __init__(self, process_id_with_prefix=None):
        self.process_id_with_prefix = process_id_with_prefix

        match = re.search(r"(.*):(.*)", self.process_id_with_prefix)
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

    def execute(self, parameters):
        p = providers.PROVIDERS[self.provider_prefix]

        self.validate_params(parameters)

        logging.info(
            f" --> Executing {self.process_id} on model server {p['url']} with params {parameters} as process {self.process_id_with_prefix}"
        )

        job = asyncio.run(self.start_process_execution(parameters))

        _process = dummy.Process(target=self._wait_for_results_async, args=([job]))
        _process.start()

        result = {"job_id": job.job_id, "status": job.status}
        return result

    async def start_process_execution(self, params):

        params["mode"] = "async"
        p = providers.PROVIDERS[self.provider_prefix]

        try:

            auth = providers.authenticate_provider(p)

            async with aiohttp.ClientSession() as session:
                response = await session.post(
                    f"{p['url']}/processes/{self.process_id}/execution",
                    json=params,
                    auth=auth,
                    headers={
                        "Content-type": "application/json",
                        "Accept": "application/json",
                    },
                )

                response.raise_for_status()

                if response.ok and response.headers:
                    # Retrieve the job id from the simulation model server from the location header:
                    match = re.search("http.*/jobs/(.*)$", response.headers["location"])
                    if match:
                        remote_job_id = match.group(1)

                    job = Job()
                    job.create(
                        remote_job_id=remote_job_id,
                        process_id_with_prefix=self.process_id_with_prefix,
                        parameters=params,
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

    def _wait_for_results_async(self, job):
        asyncio.run(self._wait_for_results(job))

    async def _wait_for_results(self, job):

        logging.info(" --> Waiting for results in Thread")

        finished = False
        p = providers.PROVIDERS[self.provider_prefix]
        timeout = float(p["timeout"])
        start = time.time()
        job_details = {}

        try:
            while not finished:

                async with aiohttp.ClientSession() as session:

                    auth = providers.authenticate_provider(p)

                    response = await session.get(
                        f"{p['url']}/jobs/{job.remote_job_id}",
                        auth=auth,
                        headers={
                            "Content-type": "application/json",
                            "Accept": "application/json",
                        },
                    )

                    response.raise_for_status()

                job_details = await response.json()

                finished = self.is_finished(job_details)

                logging.info(" --> Current Job status: " + str(job_details))

                job.progress = job_details["progress"]
                job.updated = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                job.save()

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
                f" --> Could not retrieve results for job {self.process_id_with_prefix} (={self.process_id})/{job.job_id} from simulation model server: {e}"
            )
            job.status = JobStatus.failed.value
            job.message = str(e)
            job.updated = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            job.finished = job.updated
            job.progress = 100
            job.save()
            raise CustomException(
                "Could not retrieve results from simulation model server. {e}"
            )

        # Check if job was successful
        try:
            if job_details["status"] != JobStatus.successful.value:
                job.status = JobStatus.failed.value
                job.finished = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                job.updated = job.finished
                job.progress = 100
                job.message = (
                    f'Remote execution was not successful! {job_details["message"]}'
                )
                job.save()
                raise CustomException(f"Remote job {job.remote_job_id}: {job.message}")

        except CustomException as e:
            logging.error(f" --> An error occurred: {e}")

        job.status = JobStatus.successful.value
        job.finished = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        job.updated = job.finished
        job.progress = 100
        job.save()

        # Check if results should be stored in the geoserver
        try:
            if (
                providers.check_result_storage(self.provider_prefix, self.process_id)
                == "geoserver"
            ):
                await job.results_to_geoserver()
        except Exception as e:
            logging.error(
                f" --> Could not store results for job {self.process_id_with_prefix} (={self.process_id})/{job.job_id} to geoserver: {e}"
            )
            job.message = str(e)
            job.save()

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
        return process_dict

    def to_json(self):
        return json.dumps(
            self.to_dict(), default=lambda o: o.__dict__, sort_keys=True, indent=2
        )

    def __str__(self):
        return f"src.process.Process object: process_id={self.process_id}, process_id_with_prefix={self.process_id_with_prefix}, provider_prefix={self.provider_prefix}"

    def __repr__(self):
        return f"src.process.Process(process_id={self.process_id})"
