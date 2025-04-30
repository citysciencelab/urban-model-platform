from ump.main import app
from ump.config import app_settings as config
import gunicorn

if __name__ == "__main__":

    # Run the Flask app with uvicorn
    gunicorn.run(
        app,
        host="0.0.0.0",
        port=5000,
        log_level=config.UMP_LOG_LEVEL,
        workers=1  # Adjust the number of workers as needed
    )