from flask import Flask
from flask_login import LoginManager
from config import Config
from models import db, Admin, SiteConfig


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view = 'admin.login'
    login_manager.login_message = '请先登录'

    @login_manager.user_loader
    def load_user(user_id):
        return Admin.query.get(int(user_id))

    @app.context_processor
    def inject_globals():
        cfg = SiteConfig.query.get('announcement')
        return {'announcement': cfg.value if cfg else '', 'st_abbr': Config.STUDENT_TYPE_ABBR}

    from routes.main import bp as main_bp
    from routes.admin import bp as admin_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5001, exclude_patterns=['*/site-packages/*', '*/Lib/*'])
