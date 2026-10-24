FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Hugging Face Spaces run the container as user 1000, so the app folder must be writable
# (SQLite file and signing key are created here when no DATABASE_URL / SIGNING_KEY_HEX is set).
RUN useradd -m -u 1000 user && chown -R 1000:1000 /srv
USER 1000
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
