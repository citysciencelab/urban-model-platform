import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone
from multiprocessing import dummy

import aiohttp
from flask import g

import ump.api.providers as providers
from ump.api.db_handler import engine
from ump.api.models.job import Job, JobStatus
from ump.api.models.ogc_exception import OGCExceptionResponse
from ump.api.models.providers_config import ProcessConfig, ProviderConfig
from ump.config import app_settings as config
from ump.errors import CustomException, InvalidUsage, OGCProcessException
from ump.utils import fetch_json

logger = logging.getLogger(__name__)

client_timeout = aiohttp.ClientTimeout(
    total=5,  # Set a reasonable timeout for the requests
    connect=2,  # Connection timeout
    sock_connect=2,  # Socket connection timeout
    sock_read=5,  # Socket read timeout
)


class Process:
    def __init__(self, process_id_with_prefix):
        self.inputs: dict
        self.outputs: dict

        self.process_id_with_prefix = process_id_with_prefix
        self.id = None
        self.title = None
        self.version = None
        self.job_control_options = None
        self.description = None
        self.keywords = None
        self.metadata = None
        self.links = None

        match = re.search(r"([^:]+):(.*)", self.process_id_with_prefix)
        if not match:
            logger.warning(
                "Process ID '%s' does not match pattern 'provider:process_id'. "
                "See /api/processes for a list of available processes.",
                self.process_id_with_prefix,
            )
            raise OGCProcessException(
                OGCExceptionResponse(
                    type="http://www.opengis.net/def/exceptions/ogcapi-processes-1/1.0/no-such-process",
                    title="Invalid Process ID",
                    status=400,
                    detail=(
                        f"Process ID '{self.process_id_with_prefix}' "
                        "does not match pattern: 'provider:process_id'}. "
                        "See /api/processes for a list of available processes."
                    ),
                    instance=f"/processes/{self.process_id_with_prefix}",
                )
            )
        self.provider_prefix = match.group(1)
        self.process_id = match.group(2)

        # this checks if the process is known from providers and confiured as available
        # for what purpose? -> security! -if a user selects a process which is not 
        # confiured to be available, but exists
        available, process_config = providers.check_process_availability(
            self.provider_prefix, self.process_id
        )
        if not available:
            logger.warning(
                "Process ID '%s' is not available. "
                "Either the process is not configured or it is excluded from the API.",
                self.process_id_with_prefix,
            )
            # raise OGCProcessException to inform users, but with less detail
            raise OGCProcessException(
                OGCExceptionResponse(
                    type="http://www.opengis.net/def/exceptions/ogcapi-processes-1/1.0/no-such-process",
                    title="Not available.",
                    status=400,
                    detail=(
                        f"Process ID '{self.process_id_with_prefix}' is not available."
                    ),
                    instance=f"/processes/{self.process_id_with_prefix}",
                )
            )
        logger.debug(
            "Process %s is available. Loading process details.",
            self.process_id_with_prefix,
        )

        # if anonymous access isn’t enabled, require a token
        if process_config and not process_config.anonymous_access:
            logger.debug(
                "Process %s requires authentication. Checking user roles.",
                self.process_id_with_prefix,
            )

            auth = getattr(g, "auth_token", None)
            role = f"{self.provider_prefix}_{self.process_id}"
            realm_roles = auth.get("realm_access", {}).get("roles", []) if auth else []

            # TODO: uses hard-coded client name 'ump-client' to get client roles
            client_roles = (
                (auth.get("resource_access", {}).get("ump-client", {}).get("roles", []))
                if auth
                else []
            )

            allowed = any(
                r in realm_roles + client_roles for r in [self.provider_prefix, role]
            )

            if not auth or not allowed:
                logger.warning(
                    "User is not allowed to access process %s. "
                    "Either the process is not configured for anonymous access or "
                    "the user does not have the required roles.",
                    self.process_id_with_prefix,
                )
                raise OGCProcessException(
                    OGCExceptionResponse(
                        type="http://www.opengis.net/def/exceptions/ogcapi-processes-1/1.0/no-such-process",
                        title="Not available.",
                        status=400,
                        detail=(
                            f"Process ID '{self.process_id_with_prefix}' "
                            "is not available."
                        ),
                        instance=f"/processes/{self.process_id_with_prefix}",
                    )
                )

        asyncio.run(self.load_process_details())

    async def load_process_details(self):
        provider_config = providers.get_providers()[self.provider_prefix]

        # return auth (BasicAuth curently, only)
        # TODO: add support for other auth methods: JWT, ...
        auth = providers.authenticate_provider(provider_config)

        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            process_details = await fetch_json(
                session,
                f"{provider_config.server_url}processes/{self.process_id}",
                auth=auth,
            )
            for key in process_details:
                setattr(self, key, process_details[key])

    def validate_exec_body(self, parameters):
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
                        logger.warning(
                            "Model execution %s started without parameter %s.",
                            self.process_id_with_prefix,
                            input,
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

            except AssertionError as exc:
                raise InvalidUsage(
                    f"Invalid parameter {input} = {param}: does not match mandatory schema {schema}"
                ) from exc

    def is_required(self, parameter_metadata):
        if "required" in parameter_metadata:
            return parameter_metadata["required"]

        if "required" in parameter_metadata["schema"]:
            return parameter_metadata["schema"]["required"]

        if "minOccurs" in parameter_metadata:
            return parameter_metadata["minOccurs"] > 0

        return False

    def check_for_cache(self, parameters, user_id):
        """
        Checks if the job has already been executed. Returns the job id if it has, None otherwise.
        """
        # p = providers.PROVIDERS[self.provider_prefix]["processes"][self.process_id]
        provider: ProviderConfig = providers.get_providers()[self.provider_prefix]
        process_config: ProcessConfig = provider.processes[self.process_id]

        if process_config.deterministic:
            return None

        sql = """
        select job_id from jobs where hash = encode(
            sha512(
                (
                    %(parameters)s :: json :: text || %(process_version)s || %(user_id)s) :: bytea
                ),
            'base64'
        )
        """
        with engine.begin() as conn:
            result = conn.exec_driver_sql(
                sql,
                {
                    "parameters": json.dumps(parameters),
                    "process_version": self.version,
                    "user_id": user_id,
                },
            )
            for row in result:
                return row.job_id
        return None

    def execute(self, exec_body, user):
        provider: ProviderConfig = providers.get_providers()[self.provider_prefix]

        # TODO: make this optional (remote servers should do this themselves)
        self.validate_exec_body(exec_body)

        logger.info(
            "Executing %s on model server %s with params %s as process %s for user %s",
            self.process_id,
            str(provider.server_url),
            exec_body,
            self.process_id_with_prefix,
            user,
        )

        job = asyncio.run(self.start_process_execution(exec_body, user))

        _process = dummy.Process(target=self._wait_for_results_async, args=[job])
        _process.start()

        result = {"jobID": job.job_id, "status": job.status}
        return result

    async def start_process_execution(self, request_body, user):
        # execution mode:
        # to maintain backwards compatibility to models using
        # pre-1.0.0 versions of OGC api processes
        # TODO: need to add prefer-header
        request_body["mode"] = "async"
        provider: ProviderConfig = providers.get_providers()[self.provider_prefix]

        # extract job_name from request_body
        # TODO: this is undocumented, non-OGC standard
        name = request_body.pop("job_name", None)

        job_id = self.check_for_cache(request_body, user)
        if job_id:
            logger.info("Job found, returning cached job.")
            return Job(job_id, user)

        # TODO: this try...except block is too big!
        # also it does not catch the exact error from the backend server in some cases
        # only telling the user that he has a Bad request
        try:
            auth = providers.authenticate_provider(provider)

            # short timeout and prefer-async: no sync execution supported
            async with aiohttp.ClientSession(timeout=client_timeout) as session:
                process_response = await session.get(
                    f"{provider.server_url}processes/{self.process_id}",
                    auth=auth,
                    headers={
                        "Content-type": "application/json",
                        "Accept": "application/json",
                    },
                )
                response = await session.post(
                    f"{provider.server_url}processes/{self.process_id}/execution",
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
                    self.title = process_details["title"]

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
                        process_title=self.title,
                        name=name,
                        parameters=request_body,
                        user=user,
                        process_version=self.version,
                    )
                    job.started = datetime.now(timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%S.%fZ"
                    )

                    status_response = await session.get(
                        f"{provider.server_url}jobs/{remote_job_id}?f=json",
                        auth=auth,
                        headers={
                            "Content-type": "application/json",
                            "Accept": "application/json",
                        },
                    )
                    status_response.raise_for_status()
                    status_json = await status_response.json()

                    job.status = status_json.get("status")
                    job.save()

                    logger.info(
                        " --> Job %s for model %s started running.",
                        job.job_id,
                        self.process_id_with_prefix,
                    )

                    return job

        except Exception as e:
            raise CustomException(f"Job could not be started remotely: {e}") from e

    def _wait_for_results_async(self, job: Job):
        asyncio.run(self._wait_for_results(job))

    async def _wait_for_results(self, job: Job):
        logger.info(" --> Waiting for results in Thread")

        finished = False

        provider: ProviderConfig = providers.get_providers()[self.provider_prefix]

        timeout = float(provider.timeout)
        start = time.time()
        job_details = {}

        try:
            while not finished:
                async with aiohttp.ClientSession(timeout=client_timeout) as session:
                    auth = providers.authenticate_provider(provider)
                    async with session.get(
                        f"{provider.server_url}jobs/{job.remote_job_id}?f=json",
                        auth=auth,
                        headers={
                            "Content-type": "application/json",
                            "Accept": "application/json",
                        },
                    ) as response:
                        response.raise_for_status()
                        job_details: dict = await response.json()

                finished = self.is_finished(job_details)

                logger.info(" --> Current Job status: %s", str(job_details))

                # either remote job has progress info or else we cannot provide it either
                job.progress = job_details.get("progress")

                job.updated = datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                job.save()

                if time.time() - start > timeout:
                    raise TimeoutError(
                        f"Job did not finish within {timeout / 60} minutes. Giving up."
                    )

                time.sleep(config.UMP_REMOTE_JOB_STATUS_REQUEST_INTERVAL)

            logger.info(
                " --> Remote execution job %s: success = %s. Took approx. %s minutes.",
                job.remote_job_id,
                finished,
                int((time.time() - start) / 60),
            )

        except Exception as e:
            logger.error(
                "Could not retrieve results for job %s (=%s)/%s from remote server: %s",
                self.process_id_with_prefix,
                self.process_id,
                job.job_id,
                e,
            )
            job.status = JobStatus.failed.value
            job.message = str(e)
            job.updated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            job.finished = job.updated
            job.progress = 100
            job.save()
            raise CustomException(
                f"Could not retrieve results from simulation model server. {e}"
            ) from e

        # Check if job was successful
        try:
            if job_details["status"] != JobStatus.successful.value:
                job.status = JobStatus.failed.value
                job.finished = datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                job.updated = job.finished
                job.progress = 100
                job.message = (
                    f"Remote execution was not successful! {job_details['message']}"
                )
                job.save()
                raise CustomException(f"Remote job {job.remote_job_id}: {job.message}")

        except CustomException as e:
            logger.error(" --> An error occurred: %s", e)

        job.status = JobStatus.successful.value
        job.finished = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
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
            logger.error(
                " --> Could not store results for job %s (=%s)/%s to geoserver: %s",
                self.process_id_with_prefix,
                self.process_id,
                job.job_id,
                e,
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
        return (
            f"src.process.Process object: process_id={self.process_id}, "
            + f"process_id_with_prefix={self.process_id_with_prefix}, "
            + f"provider_prefix={self.provider_prefix}"
        )

    def __repr__(self):
        return f"src.process.Process(process_id={self.process_id})"
