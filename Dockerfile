FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
ENV LDV_DB=/data/ldv.db PORT=5000
EXPOSE 5000
CMD ["python", "app.py"]
