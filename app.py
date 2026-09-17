from flask import Flask, render_template, send_file
from flask_sqlalchemy import SQLAlchemy
from models import db
from auth.routes import auth_bp
from backups.routes import backups_bp
from logs.routes import logs_bp
from config import Config
from scheduler import scheduler_service
import os

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(backups_bp)
    app.register_blueprint(logs_bp)

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/favicon.ico')
    def favicon():
        return send_file(os.path.join(app.static_folder, 'favicon.svg'), mimetype='image/svg+xml')

    with app.app_context():
        db.create_all()
        if app.config.get('USING_DEV_SECRET'):
            app.logger.warning(
                'SECRET_KEY par défaut utilisée ! '
                'Définissez SECRET_KEY dans l’environnement pour l’intranet.'
            )
        scheduler_service.set_app(app)
        scheduler_service.start()

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
