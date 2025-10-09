from fastapi import FastAPI
from ump.core.interfaces.processes import ProcessesPort

# Note: this a driver adapter, so it depends on the core interface (ProcessesPort)
# but the core does not depend on this adapter
# it does not need to implement a port/interface itself
# it just uses the interface of the core (ProcessesPort)
def create_app(process_port: ProcessesPort):

    app = FastAPI()

    @app.get("/processes")
    def get_all_processes():
        return process_port.get_all_processes()

    return app
