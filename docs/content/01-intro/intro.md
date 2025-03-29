# Introduction

Urban Digital Twins are digital representations of urban environments that integrate various data sources, models, and simulations to support decision-making and urban planning. Based on a modular approach {cite:p}`schubbe2023urbane`, the Urban Model Platform (UMP) serves as a middleware to provide access to simulation models and algorithms for Urban Digital Twins. It is designed to be flexible, extensible, and easy to use, enabling users to integrate different models into their digital twin applications.


## Background
Reality is complex and dynamic, and urban environments are no exception. Rather, urban environments are characterized by a multitude of interrelated systems, processes, and actors. This complexity makes it challenging to understand and predict the behavior of urban systems, especially in the context of rapid urbanization, climate change, and other global challenges. In many cases, models are not solely representations of a system, but its co-creators {cite:p}`herzog2024guide, thompson2022escape`. Multiple models {cite:p}`batty2021multiple` are often needed to capture the complexity of urban systems, and these models need to be integrated into a coherent framework that allows for their interaction and collaboration. The Urban Model Platform aims to provide such a framework, enabling users to access and utilize a wide range of models and algorithms for urban analysis and decision-making.

Such models can be of various types: Agent-based models, AI and Machine Learning Models, system dynamics models, and others. They can be used to simulate various aspects of urban systems, such as land use, transportation, energy consumption, and social dynamics. The Urban Model Platform provides a unified interface for accessing these models, allowing users to easily integrate them into their applications and workflows. One thing all models have in common is that they transform a number of inputs into a number of outputs. To describe such input-output relationships, the Urban Model Platform uses the [OGC API Processes standard](https://github.com/opengeospatial/ogcapi-processes), which provides a standardized way to describe and access processes and workflows in geospatial applications. This standardization enables interoperability between different models and systems, making it easier to integrate and use them in various contexts.

## Architecture
The Urban Model Platform is designed as a modular and extensible architecture that allows for the integration of various models and algorithms. The platform consists of several components, including:

- **Flask API**: The backend API serves as the central hub for accessing and managing models and algorithms. It provides a RESTful interface based on the OGC API Processes for users to interact with the platform, submit jobs, and retrieve results.
- **Geoserver**: The Geoserver component is responsible for serving geospatial data and visualizations. It allows users to access and visualize the results of simulations and analyses performed by the models.
- **Keycloak**: Keycloak is used for authentication and authorization, ensuring that only authorized users can access the platform and its resources.
- **PostgreSQL**: The PostgreSQL database is used to store the data and metadata associated with the models and simulations. It provides a robust and scalable solution for managing large volumes of data.
- **Model Servers**: The platform can connect to various model servers, each hosting different models and algorithms.



## Bibliography
```{bibliography}
:style: plain
```
