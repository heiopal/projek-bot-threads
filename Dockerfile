FROM python:3.11-slim

# Create user with UID 1000 (required by Hugging Face Spaces)
RUN useradd -m -u 1000 user

WORKDIR /app

COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user:user . .

USER user

EXPOSE 7860

CMD ["python", "app.py"]
