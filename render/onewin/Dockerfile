FROM python:3.11-slim

WORKDIR /app

COPY render/onewin/requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

ENV PYTHONUNBUFFERED=1
ENV PORT=10000

EXPOSE 10000

CMD ["sh", "-c", "gunicorn --workers 1 --threads 2 --timeout 180 --bind 0.0.0.0:10000 tools.odds_diagnostic.onewin_render_server:app & GUNICORN_PID=$!; python tools/odds_diagnostic/onewin_togo_local_probe.py || true; wait $GUNICORN_PID"]
