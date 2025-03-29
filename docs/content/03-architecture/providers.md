# Configuring Providers
As the Urban Model Platform does not provide any processes by itself, it needs to be connected to external model servers. This is done by configuring providers in the `providers.yaml` file. The following example shows how to configure a model server and its processes:

```code
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
      process-2
        result-storage: "remote"
        deterministic: True
      process-3
        exclude: True
```

```{warning}
Currently, model servers have to provide endpoints that comply with the OGC processes API standard in order to be loaded from this API. Otherwise, they will be silently ignored, and an error will be logged. 
```

## Configuration options

| Parameter | Type    | Possible Values         | Description                             |
| --------- | --------| ----------------------- | --------------------------------------- |
| url       | String  | "http://localhost:5005" | URL of the model server. |
| name      | String  | "Example Modelserver"   | Name of the model server.               |
| authentication | Object  | BasicAuth, None | Authentication type (currently, only BasicAuth is supported) |
| - type      | String  | BasicAuth, OAuth2, None | Type of authentication.                 |
| - user      | String  | "user"                  | Username for BasicAuth.                 |
| - password  | String  | "password"              | Password for BasicAuth.                 |
| timeout   | Integer | 60                      | Timeout for requests to the model server. |
| processes | Object  | process-1, process-2   | Processes provided by the model server. |
| - result-storage | String  | "geoserver", "remote" | Storage option for the process results. If the attribute is set to `remote`, no results will be stored in the UMP itself, but provided directly from the model server. In case it is set to `geoserver`, UMP will load the geoserver component and tries to store the result data in a specific Geoserver layer.  |
| - result-path | String  | "simulation_geometry"     | If the results are stored in the Geoserver, you can specify the object path to the feature collection using `result-path`. Use dots to separate a path with several components: `result-path: result.some_obj.some_features`. |
| - graph-properties | Object  | root-path, x-path, y-path | Configuration for graph properties. The sub-properties `root-path`, `x-path` and `y-path` can be used to simplify graph configuration in the UI. This simplifies data visualization in various UIs |
| - anonymous-access | Boolean | True, False | If set to `True`, the process can be seen and run by anonymous users. Jobs and layers created by anonymous users will be cleaned up after some time (this can be configured in `config.py`). |
| - deterministic | Boolean | True, False | If set to `True`, jobs will be cached based on a hash of the input parameters, the process version and the user id. |
| - exclude | Boolean | True, False | If set to `True`, the process will be excluded from the list of available processes. |