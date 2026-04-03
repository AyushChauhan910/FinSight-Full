# Use a Python image
FROM python:3.12-slim

# Create a user (Hugging Face requires apps to run as user 1000)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app

# Copy requirements and install
COPY --chown=user requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy ALL your actual code AND your chroma_db folder
COPY --chown=user . .

# Expose port 7860 (Hugging Face strictly looks for this port)
EXPOSE 7860

# Start the API
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
