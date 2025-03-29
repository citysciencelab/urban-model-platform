(GeoServer)=
# GeoServer


```{warning}
Currently, the GeoServer is not integrated with Keycloak. This means that if you configure a process with `result-storage: geoserver`, the results will be publicly accessible without authentication. 
```

All processes that are configured with `result-storage: geoserver` will be stored in a GeoServer instance. The results can be visualized on a map using the respective WFS and WMS layers. The GeoServer is configured to use the same database as the Urban Model Platform, so the results will be stored in the same database as the other data.

```{seealso}
See the [Docker Configuration User Guide](docker_configuration) for more information on the environment variables used to configure the GeoServer.
```

## Result Storage

Once the results of a process with the `result-storage: geoserver` configuration are available, the UMP will try to store the results in a GeoServer instance. The results will be stored in a GeoServer layer with the name of the jobId. The layer will be created in the workspace specified in the environment variables. 