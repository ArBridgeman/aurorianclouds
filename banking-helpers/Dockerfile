FROM docker.io/library/python:3.11-slim

SHELL ["/bin/bash", "-c"]
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install Poetry
RUN pip install --upgrade pip && \
    pip install 'poetry==1.8.3'

WORKDIR /app

# Copy Poetry files
COPY poetry.lock poetry.toml pyproject.toml ./

# Configure Poetry and install dependencies
RUN poetry config virtualenvs.create false && \
    poetry install --only main

# Copy application code
COPY banking_helpers/ ./banking_helpers/

# Expose Streamlit port
EXPOSE 8501

# Health check - simple port check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.connect(('localhost', 8501)); s.close()" || exit 1

# Run Streamlit
CMD ["poetry", "run", "streamlit", "run", "banking_helpers/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
