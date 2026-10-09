# Envoi des coupons Telegram toutes les 15 minutes avec cron-job.org

Le workflow à déclencher est `.github/workflows/bsd-v2-telegram-hourly.yml`.
Il utilise déjà un registre Supabase pour éviter de renvoyer un coupon déjà publié.

## Configuration de la tâche cron-job.org

- Nom : `Mr XPRONOS — Envoi des coupons Telegram`
- URL : `https://api.github.com/repos/MrXPRONOS/MrXPRONOS_App/actions/workflows/bsd-v2-telegram-hourly.yml/dispatches`
- Méthode : `POST`
- Fuseau : UTC (Togo)
- Fréquence : **chaque heure, aux minutes 05, 20, 35 et 50**.

En-têtes HTTP :

```text
Accept: application/vnd.github+json
Authorization: Bearer <JETON_GITHUB_PRIVÉ>
X-GitHub-Api-Version: 2022-11-28
Content-Type: application/json
```

Le jeton fine-grained GitHub doit avoir `Actions: Read and write` pour **MrXPRONOS/MrXPRONOS_App**. Ne pas le publier ou le coller dans une discussion.

Corps JSON :

```json
{
  "ref": "main",
  "inputs": {
    "trigger_source": "cron-job.org"
  }
}
```

## Vérifier avant le basculement

1. Lancer une fois la tâche depuis cron-job.org.
2. Vérifier qu'une exécution GitHub Actions nommée **BSD V2 - Coupons Telegram (cron-job.org)** apparaît puis finit avec succès. Un HTTP 204 signifie seulement que l'appel a été accepté.
3. Vérifier le journal `BSD_V2_TELEGRAM` (`sent`, `combos_sent`, `errors`). L'absence de coupons peut être normale si aucun match ne correspond aux fenêtres de publication.
4. Supprimer le bloc `schedule` de ce workflow **seulement après ce test** : sinon le cron GitHub demeure en secours.
5. Le bouton GitHub `Run workflow` reste disponible.

Les matchs du jour, de nuit et les combinés ne changent pas. Pour la nuit, la campagne est déclenchée durant l'heure de 20 h (Togo), sous réserve des conditions du programme.

**Limite :** cron-job.org peut envoyer la demande à l'heure souhaitée, mais GitHub peut encore mettre le job en file d'attente.
