from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
import pytz

# Initialize Flask extensions
db = SQLAlchemy()
bcrypt = Bcrypt()

# Set Colombo timezone
colombo_tz = pytz.timezone('Asia/Colombo') 