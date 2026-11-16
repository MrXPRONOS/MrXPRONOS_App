# CinéX — entrée publicitaire sans adhésion obligatoire

## Parcours recommandé

Utiliser dans Telegram Ads le lien **public** du canal, `https://t.me/<username>`.
Les abonnés potentiels voient les publications publiques (affiches et messages)
et peuvent toucher le bouton Telegram « Rejoindre » à leur initiative.
Le bot ne peut ni imposer un bandeau superposé au canal, ni contacter quelqu'un
qui a simplement ouvert le canal et n'a pas fait de demande.

**Attention :** dans le relais CinéX existant, les affiches sont publiques, mais
les vidéos sont généralement envoyées au canal privé, puis liées depuis l'affiche.
La prévisualisation du canal public ne signifie donc pas que chaque vidéo est
immédiatement lisible sans rejoindre le privé. Pour permettre le visionnage
immédiat dans le même canal, il faut publier les vidéos que tu as le droit de
diffuser directement dans ce canal public : cela est un changement de stratégie
de publication indépendant de cette fonctionnalité.

## Système optionnel existant réutilisé

- Bot : `@mrxpronos_canal_bot`, réutilisé sans créer de nouveau token.
- Fonction Supabase : `telegram-membership`, compatible avec les 3 canaux
  existants (LIVE, COUPONS, ACTU_FOOT) et CINEX.
- Lien additionnel `MX_ADHESION_CINEX` : uniquement pour la personne qui
  choisit elle-même « S'abonner (facultatif) ». Le webhook répond en privé
  à sa demande puis l'approuve automatiquement.
- Message explicatif épinglé dans le canal public.
- Si la personne ne clique pas sur le bouton, aucun message privé n'est envoyé.

## Installation

1. Canal public CinéX avec identifiant `@username`. Définir
   **`CINEX_MEMBERSHIP_CHANNEL`** (variable GitHub) vers ce canal.
   Si absente, `TG_PUBLIC_CHANNEL` est utilisée.
2. Ajouter le bot existant en administrateur du canal avec les droits
   **Publier des messages** et **Inviter des utilisateurs** ;
   le droit d'épingler peut être requis par Telegram selon l'interface.
3. GitHub Actions → **CineX - Abonnement facultatif (configuration)**
   → **Run workflow**, `activate=false` pour le diagnostic.
4. Après vérification, exécuter `activate=true` UNE SEULE FOIS.
   Cela déploie le webhook partagé et publie un message épinglable.
   Éviter les réexécutions d'activation, qui créent un nouveau lien et un nouveau post.
5. Prendre l'URL `CANAL_PUBLIC_CINEX` affichée dans les logs pour Telegram Ads.
   Ne pas mettre l'URL d'adhésion en lien publicitaire si l'objectif est l'accès direct.

**N'affecte pas les films, la programmation CinéX ou les 3 canaux XPRONOS.**
Aucun secret n'est stocké dans les fichiers.

## Limitations

Telegram Ads peut refuser une publicité selon ses règles propres, notamment
la destination ou les droits des films. Utiliser exclusivement du contenu
autorisé et vérifier les conditions publicitaires avant de payer la campagne.
