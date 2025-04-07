from typing import Literal
from pydantic import BaseModel, Field, HttpUrl, SecretStr, model_validator

class GraphProperties(BaseModel):
    root_path: str = Field(
        alias="root-path",
        description= (
            "If the results are stored in Geoserver,"
            "you can specify the object path to the "
            "feature collection using root-path."
            "Use dots to separate a path with several "
            "components: root-path: result.some_obj.some_features."
        )
    )
    x_path: str = Field(
        alias="x-path",
        description= (
            "If the results are stored in Geoserver,"
            "you can specify the object path to the "
            "feature collection using x-path."
            "Use dots to separate a path with several "
            "components: x-path: result.some_obj.some_features."
        )
    )
    y_path: str = Field(
        alias="x-path",
        description= (
            "If the results are stored in Geoserver,"
            "you can specify the graph properties using "
            "graph-properties."
        )
    )

class Process(BaseModel):
    name: str
    description: str | None = None
    version: str | None = None
    result_storage: Literal["geoserver", "remote"] = Field(alias="result-storage")
    exclude: bool = False
    result_path: str = Field(
        alias="result-path",
        description= (
            "If the results should be stored in Geoserver,"
            "you can specify the object path to the "
            "feature collection using result-path."
            "Use dots to separate a path with several "
            "components: result-path: result.some_obj.some_features."
        )
    )
    graph_properties: GraphProperties | None = Field(
        default=None,
        alias="graph-properties",
        description= (
            "If the results are stored in Geoserver,"
            "you can specify the graph properties using "
            "graph-properties."
        )
    )
    anonymous_access: bool = Field(
        alias="anonymous-access", default=False,
        description= (
            "If set to True, the process can be seen and run "
            "by anonymous users. Jobs and layers created "
            "by anonymous users will be cleaned up after some time."
        )
    )

    @model_validator(mode="after")
    def validate_result_path_for_geoserver(self):
        """Ensure result-path is set if result-storage is 'geoserver'."""
        if self.result_storage == "geoserver" and not self.result_path:
            raise ValueError("result-path must be set when result-storage is 'geoserver'.")
        return self

class Authentication(BaseModel):
    type: str
    user: str
    password: SecretStr

class ModelServers(BaseModel):
    name: str
    server_url: HttpUrl = Field(
        description= (
            "The URL of the model server pointing to an OGC Processes api. "
            "It should be a valid HTTP or HTTPS URL with path to the landing page."
        )
    )
    timeout: int = Field(
        default=60,
        description= (
            "Timeout in seconds for the model server. "
            "Default is 60 seconds."
        )
    )
    authentication: Authentication
    processes: dict[str, Process] = Field(
        description= (
            "Processes are defined as a dictionary with process name as key "
            "and process properties as value."
        )
    )

if __name__ == "__main__":

    print(ModelServers.model_json_schema())