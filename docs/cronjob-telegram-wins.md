# Programmer la validation Telegram avec cron-job.org

Le workflow GitHub à déclencher est `.github/workflows/bsd-v2-telegram-wins.yml`.
Il conserve provisoirement le cron GitHub `40 * * * *` comme secours. **Ne le désactivez qu'après avoir observé un lancement extérieur réussi.**

## 1. Autorisation GitHub

Créez un *fine-grained Personal Access Token* GitHub limité au dépôt **MrXPRONOS/MrXPRONOS_App**, avec la permission de dépôt **Actions: Read and write**. Ne mettez ce jeton ni dans le code ni dans les issues GitHub.

## 2. Créer la tâche sur cron-job.org

- URL : `https://api.github.com/repos/MrXPRONOS/MrXPRONOS_App/actions/workflows/bsd-v2-telegram-wins.yml/dispatches`
- Méthode : **POST**
- Calendrier : **toutes les heures à la minute 40**, fuseau UTC/Togo
- En-tête : `Accept: application/vnd.github+json`
- En-tête : `Authorization: Bearer <VOTRE_JETON_GITHUB>`
- En-tête : `X-GitHub-Api-Version: 2022-11-28`
- En-tête : `Content-Type: application/json`
- Corps (JSON) :

```json
{
  "ref": "main",
  "inputs": {
    "trigger_source": "cron-job.org"
  }
}
```

Un HTTP **204** indique que GitHub a accepté la demande de lancement. Cela ne prouve pas que l'exécution s'est achevée : contrôlez son résultat dans GitHub Actions. Ne diffusez jamais le jeton GitHub ou les en-têtes d'authentification dans des captures publiques.

## 3. Essai puis basculement

1. Exécutez une fois la tâche cron-job.org en mode manuel et vérifiez que GitHub Actions crée une exécution intitulée `BSD V2 - Validation Telegram (cron-job.org)`.
2. Vérifiez que le job `settle` aboutit et inspectez le rapport `BSD_V2_VERIFY`.
3. Après confirmation, retirez uniquement le bloc `schedule` de `.github/workflows/bsd-v2-telegram-wins.yml` pour ne garder que `workflow_dispatch` et ainsi éviter les lancements en double.
4. En cas de panne cron-job.org, le déclenchement manuel `Run workflow` demeure disponible.

### Limitations

cron-job.org est un déclencheur externe. GitHub Actions peut encore mettre en file d'attente les jobs : ce dispositif augmente la régularité des **demandes** de lancement, mais ne garantit ni démarrage ni achèvement à la seconde près.

La validation doit pouvoir relire l'historique `data.json` pour vérifier des pronostics déjà envoyés qui ne figurent plus dans le flux actuel.
