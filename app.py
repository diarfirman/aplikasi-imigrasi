import logging
from datetime import datetime

from flask import Flask, render_template, request

from config import Config
from logging_config import setup_logging
from telemetry import setup_telemetry
from routes.search import search_bp
from routes.passenger import passenger_bp
from routes.admin import admin_bp

logger = logging.getLogger(__name__)


def create_app():
    # Logging harus diinisialisasi PERTAMA — sebelum modul lain menulis log apapun
    setup_logging(level="DEBUG" if Config.DEBUG else "INFO")

    app = Flask(__name__)
    app.config.from_object(Config)
    app.secret_key = Config.SECRET_KEY

    # OTel disetup setelah app Flask ada (FlaskInstrumentor butuh objek app)
    # dan sebelum blueprint didaftarkan
    setup_telemetry(app)

    app.register_blueprint(search_bp)
    app.register_blueprint(passenger_bp, url_prefix="/passenger")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    @app.before_request
    def log_request():
        logger.info(
            "HTTP request",
            extra={
                "http.method": request.method,
                "http.path": request.path,
                "remote_addr": request.remote_addr,
            },
        )

    @app.after_request
    def log_response(response):
        logger.info(
            "HTTP response",
            extra={
                "http.method": request.method,
                "http.path": request.path,
                "http.status_code": response.status_code,
            },
        )
        return response

    @app.context_processor
    def inject_globals():
        return {"now": datetime.now()}

    @app.errorhandler(404)
    def not_found(e):
        logger.warning("404 Not Found", extra={"path": request.path})
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        logger.error("500 Internal Server Error", exc_info=e)
        return render_template("500.html"), 500

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=Config.DEBUG, host="0.0.0.0", port=5000)
