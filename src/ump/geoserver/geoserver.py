import logging
import os
import shutil

import geopandas as gpd
import requests
from psycopg2.sql import Identifier

from ump.api.db_handler import db_engine as engine
from ump.config import app_settings as config
from ump.errors import GeoserverException

class Geoserver:
    RESULTS_FILENAME = "results.geojson"

    def __init__(self):
        self.workspace = config.UMP_GEOSEVER_WORKSPACE_NAME
        self.errors = []
        self.path_to_results = None
        self.job_id = None

    def create_workspace(self):
        url = f"{config.UMP_GEOSERVER_PATH_WORKSPACE}/{self.workspace}.json?quietOnNotFound=True"

        response = requests.get(
            url,
            auth=(config.UMP_GEOSERVER_USER, config.UMP_GEOSERVER_PASSWORD),
            headers={"Content-type": "application/json", "Accept": "application/json"},
            timeout=60,
        )

        if response.status_code == 200:
            logging.info(" --> Workspace %s already exists.", self.workspace)
            return True

        if response.status_code == 404:
            logging.info(" --> Workspace %s not found - creating....", self.workspace)
        else:
            raise GeoserverException(
                f"Geoserver workspace {self.workspace} was not found"
            )

        response = requests.post(
            config.UMP_GEOSERVER_PATH_WORKSPACE,
            auth=(config.UMP_GEOSERVER_USER, config.UMP_GEOSERVER_PASSWORD),
            data=f"<workspace><name>{self.workspace}</name></workspace>",
            headers={"Content-type": "text/xml", "Accept": "*/*"},
            timeout=config.UMP_GEOSERVER_CONNECTION_TIMEOUT,
        )

        if response.ok:
            logging.info(" --> Created new workspace %s.", self.workspace)
        else:
            raise GeoserverException("Workspace could not be created")

    def save_results(self, job_id: str, data: dict):
        self.job_id = job_id

        try:
            self.create_workspace()
            logging.info(" --> Workspace should be created now")

            self.geojson_to_postgis(data=data, table_name=job_id)

            success = self.create_store(store_name=job_id)

            success = self.publish_layer(store_name=job_id, layer_name=job_id)

        except Exception as e:
            raise GeoserverException(
                "Result could not be uploaded to the geoserver.",
                payload={"error": type(e).__name__, "message": e},
            ) from e
        return success

    def publish_layer(self, store_name: str, layer_name: str):
        try:
            response = requests.post(
                f"{config.UMP_GEOSERVER_PATH_WORKSPACE}/{self.workspace}"
                + f"/datastores/{store_name}/featuretypes",
                auth=(config.UMP_GEOSERVER_USER, config.UMP_GEOSERVER_PASSWORD),
                data=f"<featureType><name>{layer_name}</name></featureType>",
                headers={"Content-type": "text/xml"},
                timeout=config.UMP_GEOSERVER_CONNECTION_TIMEOUT,
            )

            if not response or not response.ok:
                logging.error(
                    "Could not publish layer %s from store %s. Reason: %s",
                    layer_name,
                    store_name,
                    response,
                )

        except Exception as e:
            raise GeoserverException(
                f"Could not publish layer {layer_name} from store {store_name}. Reason: {e}",
                payload={
                    "error": type(e).__name__,
                    "message": e,
                },
            ) from e

        return response.ok
    # TODO: to simplify the dev setup the UMP and geoserver database hosts
    # can be the same but in production they should be different, at least the database used
    # also the user should decide if he/she wants to use the same database (host) for ump and geoserver

    def create_store(self, store_name: str):
        logging.info(" --> Storing results to geoserver store %s", store_name)

        xml_body = f"""
            <dataStore>
            <name>{store_name}</name>
            <connectionParameters>
                <host>{config.UMP_GEOSERVER_DB_HOST}</host>
                <port>{config.UMP_GEOSERVER_DB_PORT}</port>
                <database>{config.UMP_GEOSERVER_DB_NAME}</database>
                <user>{config.UMP_GEOSERVER_DB_USER}</user>
                <passwd>{config.UMP_GEOSERVER_DB_PASSWORD}</passwd>
                <dbtype>postgis</dbtype>
            </connectionParameters>
            </dataStore>
        """
        response = requests.post(
            (
                f"{str(config.UMP_GEOSERVER_URL_WORKSPACE)}"
                f"/{self.workspace}/datastores"
            ),
            auth=(config.UMP_GEOSERVER_USER, config.UMP_GEOSERVER_PASSWORD),
            data=xml_body,
            headers={"Content-type": "application/xml"},
            timeout=config.UMP_GEOSERVER_CONNECTION_TIMEOUT,
        )

        if not response or not response.ok:
            raise GeoserverException(
                f"Could not store data from postgis to geoserver store {store_name}",
                payload={
                    "status_code": response.status_code,
                    "message": response.reason,
                },
            )
        return response.ok

    def geojson_to_postgis(self, table_name: str, data: dict):

        gdf = gpd.GeoDataFrame.from_features(data["features"], crs = 'EPSG:4326')
        table = Identifier(table_name)
        gdf.to_postgis(name=table.string, con=engine)

    def cleanup(self):
        if self.path_to_results and os.path.exists(self.path_to_results):
            shutil.rmtree(self.path_to_results)
