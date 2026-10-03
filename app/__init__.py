from flask import Flask
from app.config import Config
from app.database import init_db

def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    # Inicializa o pool de conexões MySQL
    init_db()

    # Registro de Blueprints
    from app.routes.main_routes import main_bp
    from app.routes.api_routes import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    return app