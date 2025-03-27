
![UMP-Banner](https://github.com/user-attachments/assets/f70d498a-ef6d-4a3a-9e1e-429da130c65d)


# Urban Model Platform
The Urban Model Platform is an Open Urban Platform to distribute and access (simulation) models for Urban Digital Twins. It builds on the [OGC API Processes](https://docs.ogc.org/is/18-062r2/18-062r2.html) open standard and was developed by the City Science Lab at HafenCity University Hamburg and the Agency for Geoinformation and Suveying in the context of the [Connected Urban Twins](https://www.connectedurbantwins.de/) project.

The repository contains a Python implementation of the OGC API Processes standard that can be used as a "system of systems" open platform. In the context of digital urban twins, such a platform can provide the infrastructure to integrate and combine domain-specific models ranging from simple regression models to advanced simulation and AI models. Instead of executing jobs and processes on the server itself, the Urban Model Platform is configured with multiple providers or model servers.

This architecture is independent of any frontend application. One could use e.g. the [Scenario Explorer](https://github.com/citysciencelab/scenario-explorer-addon) as a client frontend, but due to the standardized API, mutliple frontends are possible.


## Application architecture and dependency diagram

```mermaid
flowchart TB
    %% Define styles
    classDef api fill:#4a90e2,stroke:#333,stroke-width:2px,color:white
    classDef auth fill:#ff9,stroke:#333,stroke-width:2px,color:black
    classDef db fill:#ffb366,stroke:#333,stroke-width:2px,color:black
    classDef gateway fill:#e4e4e4,stroke:#333,stroke-width:2px,color:black
    classDef geoserver fill:#9acd32,stroke:#333,stroke-width:2px,color:black

    %% Components
    api[UMP API]
    gateway[k8s Gateway Api]
    keycloak[Keycloak]
    geoserver[GeoServer]
    db_api[API PostgreSQL]
    db_auth[Auth PostgreSQL]
    db_spatial[Spatial PostgreSQL]

    %% Dependencies
    gateway --> api
    api --> keycloak
    api --> db_api
    api --> geoserver
    keycloak --> db_auth
    geoserver --> db_spatial

    %% Apply styles
    class api api
    class gateway gateway
    class keycloak auth
    class geoserver geoserver
    class db_api,db_auth,db_spatial db

    %% Layered subgraphs
    subgraph Network Layer
        gateway
    end

    subgraph Application Layer
        subgraph Authentication
            keycloak
        end
        subgraph Core Application
            api
        end
        subgraph Geospatial Web Data
            geoserver
        end
    end

    subgraph Storage Layer
        subgraph Databases
            db_api
            db_auth
            db_spatial
        end
    end
```

