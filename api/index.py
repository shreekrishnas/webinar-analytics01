import sys
import os

# Ensure the project root is on the path so all imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Run DB init at module load time (Vercel cold start) — don't rely on lifespan alone
from database import engine
import models
models.Base.metadata.create_all(bind=engine)
from seed_data import seed_database
seed_database()

from main import app
