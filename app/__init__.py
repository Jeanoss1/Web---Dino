from flask import Flask

def create_app():
    app = Flask(__name__, template_folder='views', static_folder='static')
    
    # Registrar las rutas
    from app.controllers.home_controller import home_bp
    app.register_blueprint(home_bp)
    from app.controllers.auth_controller import auth_bp
    app.register_blueprint(auth_bp)

    return app