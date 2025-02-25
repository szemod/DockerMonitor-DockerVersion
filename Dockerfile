# Official Python slim image
FROM python:3.8-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5434

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5434", "web_ctop:app"]
