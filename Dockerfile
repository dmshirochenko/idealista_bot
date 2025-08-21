# 1. Use the specific Python version
FROM python:3.10-slim

# 2. Set the working directory
WORKDIR /app

# 3. Install pipenv, which is needed to read the Pipfile.lock
RUN pip install pipenv

# 4. Copy only the Pipfile and Pipfile.lock to leverage the build cache
COPY Pipfile Pipfile.lock ./

# 5. Install dependencies from Pipfile.lock into the system's Python environment
# --system: Installs to the global site-packages, not a virtualenv
# --deploy: Ensures the lock file is up-to-date and fails if not
RUN pipenv install --system --deploy --ignore-pipfile

# 6. Create a non-root user and switch to it
RUN useradd --create-home appuser
USER appuser

# 7. Copy the rest of the application code, owned by the new user
COPY --chown=appuser:appuser . .

# 8. Set the command to run the application
# config.yaml is copied by the step above.
CMD [ "python3", "-u", "flathunt.py", "-c", "config.yaml" ]