from flask_bcrypt import Bcrypt
from flask_login import LoginManager

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access the admin area."
login_manager.login_message_category = "warning"

bcrypt = Bcrypt()

# Assigned in create_app() after config is loaded
db_pool = None
