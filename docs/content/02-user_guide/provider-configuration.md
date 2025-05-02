(providers)=
# Configuring Providers
As the Urban Model Platform does not provide any processes by itself, it needs to be connected to external model servers. This is done by configuring providers in the `providers.yaml` file. The following example shows how to configure a model server and its processes:


```yaml
# providers.yaml
modelserver-1:
  url: "http://localhost:5005"
  name: "Example Modelserver"
  authentication:
    type: "BasicAuth"
    user: "user"
    password: "password"
  timeout:  60
  processes:
    process-1:
      result-storage: "geoserver"
      result-path: simulation_geometry
      graph-properties:
        root-path: results.simulation_results
        x-path: results.simulation_results.x
        y-path: results.simulation_results.y
      anonymous-access: True
    process-2:
      result-storage: "remote"
      deterministic: True
    process-3:
      exclude: True
```

```{warning}
Currently, model servers have to provide endpoints that comply with the OGC processes API standard in order to be loaded from this API. Otherwise, they will be silently ignored, and an error will be logged. 
```

## Configuration options

| Parameter | Type    | Possible Values         | Description                             |
| --------- | --------| ----------------------- | --------------------------------------- |
| url       | String  | Any http/https URL | URL of the model server. |
| name      | String  | Any   | Name of the model server.               |
| **authentication** | Object  |  |  |
| authentication.type      | String  | BasicAuth | Type of authentication  (currently, only BasicAuth is supported) |
| authentication.user      | String  | Any                  | Username for BasicAuth.                 |
| authentication.password  | String  | Any              | Password for BasicAuth.                 |
| timeout   | Integer | 60                      | Time before a request to a modelserver is given up. |
| **processes** | Object  |    | |
| processes.result-storage | String  | ["geoserver" \\| "remote"] | Storage option for the process results. If the attribute is set to `remote`, no results will be stored in the UMP itself, but provided directly from the model server. In case it is set to `geoserver`, UMP will load the geoserver component and tries to store the result data in a specific Geoserver layer.  |
| processes.result-path | String  | Any | If the results are stored in the Geoserver, you can specify the object path to the feature collection using `result-path`. Use dots to separate a path with several components: `result.some_obj.some_features`. |
| processes.graph-properties | Object  | root-path, x-path, y-path | Configuration for graph properties. The sub-properties `root-path`, `x-path` and `y-path` can be used to simplify graph configuration in the UI. This simplifies data visualization in various UIs |
| processes.anonymous-access | Boolean | [True \\| False] | If set to `True`, the process can be seen and run by anonymous users. Jobs and layers created by anonymous users will be cleaned up after some time (this can be configured in `config.py`). |
| processes.deterministic | Boolean | [True \\| False] | If set to `True`, jobs will be cached based on a hash of the input parameters, the process version and the user id. |
| processes.exclude | Boolean | [True \\| False] | If set to `True`, the process will be excluded from the list of available processes. |