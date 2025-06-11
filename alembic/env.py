import sys
import os

# Add the root project directory to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from app.core.config import settings
from app.db.base import Base
from app.db import models  # Ensure all models are imported

# Alembic Config object, from alembic.ini
config = context.config

# Setup loggers
fileConfig(config.config_file_name)

# Metadata for autogenerate
target_metadata = Base.metadata

def run_migrations_offline():
    """Run migrations without DB connection"""
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Run migrations with DB connection"""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = settings.DATABASE_URL
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()

# Choose offline or online mode
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
