from sqlalchemy.orm import declarative_base

# Shared Base for all models to ensure they share the same metadata registry
Base = declarative_base()
