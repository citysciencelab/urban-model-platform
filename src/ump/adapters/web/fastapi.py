from fastapi import FastAPI
from ump.core.interfaces.processes import ProcessesPort

def create_app(process_port: ProcessesPort):

    app = FastAPI()

    @app.get("/processes")
    def get_all_processes():
        return process_port.get_all_processes()

    return app
