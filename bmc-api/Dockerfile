FROM python:3.12-slim

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set the working directory.
WORKDIR /app

# --- START REVISED SECTION ---

# 1. Copy the file that defines your dependencies.
COPY pyproject.toml README.md ./

# 2. Create the virtual environment first.
RUN uv venv

# 3. Install the project and all its dependencies from pyproject.toml.
# This command correctly installs "extras" (like [standard]).
RUN uv pip install .

# --- END REVISED SECTION ---

# Copy the application into the container.
COPY src/bmc bmc/

CMD ["/app/.venv/bin/fastapi", "run", "bmc/infrastructure/api.py", "--port", "8000", "--host", "0.0.0.0", "--reload"]