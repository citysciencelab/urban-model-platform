import json
import logging
import os
import shutil

import geopandas as gpd
import requests
from psycopg2.sql import Identifier
from sqlalchemy import create_engine

import ump.config as config
from ump.errors import GeoserverException

logging.basicConfig(level=os.environ.get("LOGLEVEL", "WARNING"))


class Geoserver:

    RESULTS_FILENAME = "results.geojson"

    def __init__(self):
        self.workspace = config.geoserver_workspace
        self.errors = []
        self.path_to_results = None
        self.job_id = None

    def create_workspace(self):

        url = f"{config.geoserver_workspaces_url}/{self.workspace}.json?quietOnNotFound=True"

        response = requests.get(
            url,
            auth=(config.geoserver_admin_user, config.geoserver_admin_password),
            headers={"Content-type": "application/json", "Accept": "application/json"},
            timeout=60,
        )

        if response.status_code == 200:
            logging.info(f" --> Workspace {self.workspace} already exists.")
            return True

        if response.status_code == 404:
            logging.info(f" --> Workspace {self.workspace} not found - creating....")
        else:
            raise GeoserverException(
                f"Geoserver workspace {self.workspace} was not found"
            )

        response = requests.post(
            config.geoserver_workspaces_url,
            auth=(config.geoserver_admin_user, config.geoserver_admin_password),
            data=f"<workspace><name>{self.workspace}</name></workspace>",
            headers={"Content-type": "text/xml", "Accept": "*/*"},
        )

        if response.ok:
            logging.info(f" --> Created new workspace {self.workspace}.")
        else:
            raise GeoserverException(f"Workspace could not be created")

    def save_results(self, job_id: str, data: dict):
        self.job_id = job_id

        try:
            self.create_workspace()
            logging.info(f" --> Workspace should be created now")

            self.geojson_to_postgis(data=data, table_name=job_id)

            success = self.create_store(store_name=job_id, table_name=job_id)

            success = self.publish_layer(store_name=job_id, layer_name=job_id)

        except Exception as e:
            raise GeoserverException(
                f"Result could not be uploaded to the geoserver.",
                payload={"error": type(e).__name__, "message": e},
            )
        return success

    def publish_layer(self, store_name: str, layer_name: str):
        try:
            response = requests.post(
                f"{config.geoserver_workspaces_url}/{self.workspace}/datastores/{store_name}/featuretypes",
                auth=(config.geoserver_admin_user, config.geoserver_admin_password),
                data=f"<featureType><name>{layer_name}</name></featureType>",
                headers={"Content-type": "text/xml"},
            )

            if not response or not response.ok:
                logging.error(
                    f"Could not publish layer {layer_name} from store {store_name}. Reason: {response}"
                )

        except Exception as e:
            raise GeoserverException(
                f"Could not publish layer {layer_name} from store {store_name}. Reason: {e}",
                payload={
                    "error": type(e).__name__,
                    "message": e,
                },
            )

        return response.ok

    def create_store(self, store_name: str, table_name: str):
        logging.info(f" --> Storing results to geoserver store {store_name}")

        xml_body = f"""
    <dataStore>
      <name>{store_name}</name>
      <connectionParameters>
        <host>{config.geoserver_postgis_host}</host>
        <port>{config.postgres_port}</port>
        <database>{config.postgres_db}</database>
        <user>{config.postgres_user}</user>
        <passwd>{config.postgres_password}</passwd>
        <dbtype>postgis</dbtype>
      </connectionParameters>
    </dataStore>
    """
        response = requests.post(
            f"{config.geoserver_workspaces_url}/{self.workspace}/datastores",
            auth=(config.geoserver_admin_user, config.geoserver_admin_password),
            data=xml_body,
            headers={"Content-type": "application/xml"},
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
        engine = create_engine(
            f"postgresql://{config.postgres_user}:{config.postgres_password}@{config.postgres_host}/{config.postgres_db}"
        )
        gdf = gpd.GeoDataFrame.from_features(data["features"])
        table = Identifier(table_name)
        gdf.to_postgis(name=table.string, con=engine)

    def cleanup(self):
        if self.path_to_results and os.path.exists(self.path_to_results):
            shutil.rmtree(self.path_to_results)
