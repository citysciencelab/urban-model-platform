# OGC Processes API

## API documentation
This API implements the OGC processes standard (except that it is not complete). E.g. there is no html landingpage implemented, only the API.

For an API description e.g. for the jobs list see:
https://docs.ogc.org/is/18-062r2/18-062r2.html#rc_job-list
or
https://developer.ogc.org/api/processes/index.html#tag/JobList

For convenience there is still some documentation below.

## Setup
Please copy api/configs/dev_environment.example to api/configs/dev_environment and provide credentials.

Also the list of providers delivering the OGC processes api have to be configured in providers.yml. See providers.yml.example as example. It contains credentials!

In order to remove all data and start from scratch you can remove the folder api/data for the geoserver files and the folder ./geoserver/data to erase the postgis data. The data folders will be recreated when the docker containers start up (necessary DB table creation included).

### GET api/jobs
Example parameters:
```
?limit=1&page=1&status=running&status=successful
```

Default limit: none.
Parameters are optional.

## Access DB
We have two DB users:
- the privileged POSTGRES_USER user configured in geoserver/configs/geoserver
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



