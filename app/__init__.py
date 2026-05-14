from flask import Flask, Response
from psycopg2.pool import ThreadedConnectionPool

from app.config import Config
from app import extensions


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    extensions.db_pool = ThreadedConnectionPool(
        minconn=1,
        maxconn=10,
        dsn=app.config["DATABASE_URL"],
    )

    extensions.login_manager.init_app(app)
    extensions.bcrypt.init_app(app)
    extensions.csrf.init_app(app)
    extensions.limiter.init_app(app)

    from app.auth.routes import auth_bp, load_user
    from app.public.routes import public_bp
    from app.admin.routes import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)

    extensions.login_manager.user_loader(load_user)

    @app.after_request
    def set_security_headers(response: Response) -> Response:
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
            "img-src 'self' data:; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'none'"
        )
        return response

    from app.email.scheduler import init_scheduler
    init_scheduler(app)

    return app
