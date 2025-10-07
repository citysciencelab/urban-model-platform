from fastapi import FastAPI
from ump.core.services.process_manager import ProcessManager

def create_app(process_manager: ProcessManager):
    app = FastAPI()

    @app.get("/processes")
    def get_processes():
        return process_manager.list_all_processes()

    return app
