(API)=
# Flask API

The Urban Model Platform is built on top of the OGC API Processes standard. It provides a RESTful API for managing and executing processes on various model servers. 

## OGC API Processes
This API is built on the OGC API Processes standard. To learn more about the standard, please refer to the [OGC API Processes - Part 1: Core](https://docs.ogc.org/is/18-062r2/18-062r2.html).

## API Endpoints
The API provides several endpoints for managing and executing processes. We extended the API Processes standard to include additional endpoints for managing jobs and ensembles. The following table summarizes the available endpoints:


### Top-level Endpoints
| Endpoint                     | Method | Description                                                                 | Required by OGC API Processes |
|------------------------------|--------|-----------------------------------------------------------------------------|-----------------------------------|
| `/`                          | GET    | Retrieve the API root information.                                          | ✅ |
| `/processes`                 | GET    | Retrieve a list of available processes. [See more](processes)               | ✅ |
| `/jobs`                      | GET    | Retrieve a list of jobs.  [See more](jobs)                                  | ✅ |
| `/ensembles`                 | GET    | Retrieve a list of ensembles. [See more](ensembles)                         | ❌ |
| `/ready`                     | GET    | Check the readiness of the application.                                     | ❌ |


```{warning}
Currently, there is no HTML landing page implemented.
```


```{warning}
Currently, the conformance classes endpoint as required by the OGC API Processes is not implemented.
```

To learn more about all available routes, please see below:

(processes)=
### Processes

| Endpoint                     | Method | Description                                                                 | Required by OGC API Processes |
|------------------------------|--------|-----------------------------------------------------------------------------|-----------------------------------|
| `/processes`                 | GET    | Retrieve a list of available processes.                                     | ✅ |
| `/processes/{id}`            | GET    | Retrieve details of a specific process by its ID, such as input and output parameters   |✅ |
| `/processes/{id}/execution`  | POST   | Execute a specific process                                                  | ✅ |
| `/processes/providers`       | GET    | Returns the providers configuration                                         | ❌ |

(jobs)=
### Jobs

| Endpoint                     | Method | Description                                                                 | Required by OGC API Processes |
|------------------------------|--------|-----------------------------------------------------------------------------|-----------------------------------|
| `/jobs`                      | GET    | Retrieve a list of jobs.                                                    | ✅ |
| `/jobs/{id}`                 | GET    | Retrieve details of a specific job by its ID.                               | ✅ |
| `/jobs/{id}/results`         | GET    | Retrieve the results of a specific job.                                     | ✅ |
| `/jobs/{id}/users`           | GET    | Retrieves all users that have access to a specific job                      | ❌ |
| `/jobs/{id}/comments`        | GET    | Retrieves all comments for a specific job                                   | ❌ |
| `/jobs/{id}/comments`        | POST   | Creates a comment for a specific job                                        | ❌ |
| `/jobs/{id}/share/{email}`   | GET    | Shares a specific job with another user                                     | ❌ |


(ensembles)=
### Ensembles
Ensembles are collections of jobs that can be executed together. The following endpoints are available for managing ensembles:

| Endpoint  | Method | Description   | Required by OGC API Processes |
|-----------|--------|---------------|-------------------------------|
| `/ensembles`                   | GET    | Gets all ensembles the current user has access to    | ❌ |
| `/ensembles`                   | POST   | Creates an ensemble                                  | ❌ |
| `/ensembles/{id}`               | GET    | Gets an ensemble by its ID                          | ❌ |
| `/ensembles/{id}`               | DELETE | Deletes an ensemble by its ID                       | ❌ |
| `/ensembles/{id}/execute`       | GET    | Creates and executes the jobs in an ensemble        | ❌ |
| `/ensembles/{id}/jobs`          | GET    | Gets all jobs included in an ensemble               | ❌ |
| `/ensembles/{id}/jobs/{id}`     | DELETE | Deletes a job from an ensemble                      | ❌ |
| `/ensembles/{id}/comments`      | GET    | Gets the comments for an ensemble                   | ❌ |
| `/ensembles/{id}/users`         | GET    | Gets all users that have access to an ensemble      | ❌ |
| `/ensembles/{id}/share/{email}` | GET    | Shares an ensemble with another user                | ❌ |
| `/ensembles/{id}/addjob/{id}`   | GET    | Adds a job to an ensemble                           | ❌ |
| `/ensembles/{id}/comments`      | POST   | Creates a comment for an ensemble                   | ❌ |

(users)=
### Users
| Endpoint                       | Method | Description                            | Required by OGC API Processes |
|--------------------------------|--------|----------------------------------------|-------------------------------|
| `/users/{id}/details`          | GET    | Retrieves user details by user ID      | ❌                            |



