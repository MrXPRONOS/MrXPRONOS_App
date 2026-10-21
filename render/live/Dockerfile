# Full original Mr XPRONOS LIVE engine — Deno runtime, free Render web service.
# Contains the existing shared providers and bundled Telegram fonts unchanged.
FROM denoland/deno:2.6.1
WORKDIR /app
COPY supabase/functions/ ./supabase/functions/
COPY render/live/ ./render/live/
RUN deno run --allow-read render/live/verify_engine.ts
RUN deno cache supabase/functions/live/index.ts
RUN deno cache supabase/functions/telegram-live/index.ts
ENV DENO_NO_UPDATE_CHECK=1
EXPOSE 10000
CMD ["run", "--allow-all", "render/live/server.ts"]
