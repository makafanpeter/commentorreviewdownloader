from flask_script import Manager,Server
from flask_migrate import Migrate, MigrateCommand
import os

import configuration
from app import app, db
app.config.from_object(configuration.ProductionConfig)

migrate = Migrate(app, db)
manager = Manager(app)
manager.add_command("runserver", Server(host="0.0.0.0", port=5000))

manager.add_command('db', MigrateCommand)

if __name__ == '__main__':
    manager.run()