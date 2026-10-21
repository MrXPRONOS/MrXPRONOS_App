FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \n    PYTHONDONTWRITEBYTECODE=1 \n    DB_PATH=/app/data/coupons_v4.db
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py db.py odds.py ./
RUN groupadd --system bot && useradd --system --gid bot bot \n    && mkdir -p /app/data && chown -R bot:bot /app/data
USER bot

CMD ["python", "bot.py"]
