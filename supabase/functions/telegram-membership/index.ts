import { serve } from "https://deno.land/std@0.170.0/http/server.ts";

const TELEGRAM_BOT_TOKEN =
  Deno.env.get("TELEGRAM_BOT_TOKEN") ||
  Deno.env.get("FOOTBALL_NEWS_BOT_TOKEN") ||
  "";

const LINK_PREFIX = "MX_ADHESION_";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

async function sha256Hex(value: string) {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(value),
  );
  return [...new Uint8Array(digest)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function expectedWebhookSecret() {
  return "mx_" + (await sha256Hex(TELEGRAM_BOT_TOKEN)).slice(0, 48);
}

async function telegram(method: string, payload: Record<string, unknown>) {
  const response = await fetch(
    `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/${method}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  const body = await response.json().catch(() => ({}));
  if (!response.ok || body?.ok !== true) {
    throw new Error(
      `Telegram ${method}: ${response.status} ${JSON.stringify(body).slice(0, 500)}`,
    );
  }
  return body.result;
}

function displayName(request: any) {
  const user = request?.from || {};
  const full = [user.first_name, user.last_name].filter(Boolean).join(" ").trim();
  return full || user.username || "supporter";
}

function channelLabel(request: any) {
  const linkName = String(request?.invite_link?.name || "");
  const key = linkName.startsWith(LINK_PREFIX)
    ? linkName.slice(LINK_PREFIX.length)
    : "";
  const labels: Record<string, string> = {
    LIVE: "Pronos Live",
    COUPONS: "Coupons du jour",
    ACTU_FOOT: "Actu Foot",
  };
  return labels[key] || request?.chat?.title || "Mr XPRONOS";
}

serve(async (req) => {
  if (req.method !== "POST") {
    return json({ ok: true, service: "telegram-membership" });
  }

  if (!TELEGRAM_BOT_TOKEN) {
    console.error("TELEGRAM_BOT_TOKEN absent");
    return json({ ok: false, error: "Bot token absent" }, 500);
  }

  const expected = await expectedWebhookSecret();
  const received = req.headers.get("x-telegram-bot-api-secret-token") || "";
  if (received !== expected) {
    console.warn("Webhook secret invalide");
    return json({ ok: false, error: "Unauthorized" }, 401);
  }

  let update: any;
  try {
    update = await req.json();
  } catch {
    return json({ ok: false, error: "JSON invalide" }, 400);
  }

  const request = update?.chat_join_request;
  if (!request) {
    return json({ ok: true, ignored: "not_chat_join_request" });
  }

  const inviteName = String(request?.invite_link?.name || "");
  if (!inviteName.startsWith(LINK_PREFIX)) {
    console.log("JOIN_REQUEST_IGNORED", {
      chat_id: request?.chat?.id,
      invite_name: inviteName,
    });
    return json({ ok: true, ignored: "not_mrxpronos_membership_link" });
  }

  const chatId = request?.chat?.id;
  const userId = request?.from?.id;
  const userChatId = request?.user_chat_id;

  if (!chatId || !userId) {
    return json({ ok: false, error: "Join request incomplete" }, 400);
  }

  const label = channelLabel(request);
  const name = displayName(request);

  // Telegram permet au bot d'écrire au user_chat_id pendant quelques minutes
  // tant que la demande n'a pas encore été traitée.
  if (userChatId) {
    try {
      await telegram("sendMessage", {
        chat_id: userChatId,
        parse_mode: "HTML",
        disable_web_page_preview: true,
        text:
          `👋 <b>Bienvenue ${name} !</b>\n\n` +
          `Ta demande pour <b>${label}</b> est bien reçue. ✅\n` +
          "Je valide ton accès maintenant.\n\n" +
          "🔔 Une fois dans le canal, pense à <b>activer la cloche</b> " +
          "pour recevoir les nouvelles publications Mr XPRONOS.",
      });
    } catch (error) {
      // Une erreur de DM ne doit pas empêcher l'adhésion.
      console.warn("JOIN_WELCOME_DM_FAILED", String(error));
    }
  }

  try {
    await telegram("approveChatJoinRequest", {
      chat_id: chatId,
      user_id: userId,
    });
  } catch (error) {
    console.error("JOIN_APPROVAL_FAILED", String(error));
    return json({ ok: false, error: "approval_failed" }, 502);
  }

  console.log("JOIN_APPROVED", {
    chat_id: chatId,
    user_id: userId,
    channel: label,
    invite_name: inviteName,
  });

  return json({ ok: true, approved: true, channel: label });
});
