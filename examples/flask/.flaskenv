# This file doesn't get included in the docker build and python-dotenv only gets installed
# in dev dependencies.  So this will only be applied for local non-docker development.
FLASK_DEBUG = 1
