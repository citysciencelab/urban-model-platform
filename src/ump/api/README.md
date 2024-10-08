# OGC Processes API

## API documentation
This API implements the OGC processes standard (except that it is not complete). E.g. there is no html landingpage implemented, only the API.

For an API description e.g. for the jobs list see:
https://docs.ogc.org/is/18-062r2/18-062r2.html#rc_job-list
or
https://developer.ogc.org/api/processes/index.html#tag/JobList

For convenience there is still some documentation below.

## Setup
Also the list of providers delivering the OGC API Processes  have to be configured in [providers.yaml](../../../providers.yaml.example) along with the processes that the UMP should provide. The structure looks as following: 

```
modelserver-1:
    url: "http://localhost:5005"
    name: "CSL Test Modelserver"
    authentication:
      type: "BasicAuth"
      user: "user"
      password: "password"
    timeout:  60
    processes:
      process-1:
        result-storage: "geoserver"
      process-2
        result-storage: "remote"
      process-3
        exclude: True

```

For each process, it is possible to choose from result-storage options. If the attribute `result-storage` is set to `remote`, no results will be stored in the UMP itself, but provided directly from the model server. In case it is set to `geoserver`, UMP will load the geoserver component and tries to store the result data in a specific Geoserver layer. 




### GET api/jobs
Example parameters:
```
?limit=1&page=1&status=running&status=successful
```

Default limit: none.
Parameters are optional.

## Access DB
We have two DB users:
- the privileged POSTGRES_USER user configured in .env file
- the user used by the API with privileges on the jobs table (e.g. see api/initializers/db/create_db_user.sh). Its credentials are configured in docker-compose.yml.

```
docker-compose exec postgis bash
psql -U <username> -d <db_name>
```

## Environment Variables
...to be configured in the files dev_environment or prod_environment.

|   Variable    | Default value | Description |
| ------------- | ------------- | ----------- |
|  LOGLEVEL=DEBUG | WARNING | Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL or NOTSET | 
|  FLASK_DEBUG | 0 |  |
|  API_SERVER_URL      | localhost:3000 | This is only used to return the complete URL in the result of the job details as specified in OGC. |
|  CORS_URL_REGEX | * | Restrict CORS support to configured URL. Should be the frontend url.  |
|  POSTGRES_DB | cut_dev | Database name |
|  POSTGRES_HOST | postgis | Database name |
|  POSTGRES_USER | postgres | Database name |
|  POSTGRES_PASSWORD | postgres | Database name |
|  POSTGRES_PORT | 5432 | Database name |
|  GEOSERVER_WORKSPACE  | CUT | All layers are being stored to one geoserver workspace. Configure its name here.
|  GEOSERVER_ADMIN_USER | admin | |
|  GEOSERVER_ADMIN_PASSWORD | geoserver | |
|  GEOSERVER_BASE_URL | http://geoserver:8080/geoserver | Url to the geoserver. |

TODO: UPDATE!


