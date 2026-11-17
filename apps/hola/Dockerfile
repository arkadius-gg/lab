# Imagen de hola. Las pruebas se ejecutan al construir: si una falla, la imagen no se crea.
FROM python:3.13-slim-trixie
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py test_app.py ./
RUN python -m unittest -q
USER 65534:65534
EXPOSE 8080
CMD ["python", "app.py"]
