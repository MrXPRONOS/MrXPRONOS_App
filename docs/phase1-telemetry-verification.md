# Vérification de la phase 1 — télémétrie visiteurs

## Contrôles effectués (6 novembre 2026)

- Enquête sur les anciens événements : fortes rafales les 12, 13 et 18 octobre ; le filtre CI du tableau existant est conservé et la nouvelle supervision signale les minutes avec ≥30 visites sans suppression des événements historiques.
- Période du 22 octobre au 4 novembre : zéro événement de visite enregistré. **Impossible d'affirmer** que le site n'avait aucun trafic pendant cette période.
- Schéma Supabase créé via migration `visitor_telemetry_phase1` : trois tables RLS, deux RPC avec droits séparés, indices sur sessions et dates.
- Test transactionnel avec `BEGIN ... ROLLBACK` : même `event_id` envoyé deux fois => une seule page vue ; événement d'engagement => une session engagée ; deux événements stockés.
- Test transactionnel sous rôle `anon` : page enregistrée ; chemins contenant `..` et usurpation de session d'un autre identifiant rejetés ; une seule page vue persistée dans la transaction. Rollback effectué.
- Aucun historique artificiellement converti en sessions ; l'historique de `public.analytics` est conservé.
- L'ancien outil de supervision continue à lire `admin_monitor_snapshot` sans changement de sa logique de filtrage.

## Parcours navigateur à vérifier après déploiement

1. Ouvrir l'accueil en navigation privée sur ordinateur ; dans le tableau admin, contrôler une session, un navigateur et une page V2.
2. Rafraîchir la page avec le même onglet : deux pages vues, toujours une session et une visite unique du jour.
3. Ouvrir `pronos.html` et `historique.html` : même session, pages vues supplémentaires.
4. Recharger et attendre 15 secondes avec onglet visible : session engagée.
5. Ouvrir le site sur un Android/iPhone : autre identifiant de navigateur, appareil `mobile`.
6. Ajouter l'app à l'écran d'accueil, ouvrir en standalone : compter les sessions standalone sans supposer que cela prouve l'installation.
7. Simuler une perte réseau puis naviguer : la file d'événements se conserve dans `sessionStorage` et se renvoie à la prochaine initialisation réussie.
8. Après 30 min d'inactivité : nouvel identifiant de session ; même navigateur historique.
9. Vérifier `admin-supervision.html` avec un compte admin et sans être connecté (RPC de supervision inaccessible sans admin).

**Limite** : les tests sur appareils physiques, après déploiement, ne sont pas attestés par les tests SQL ci-dessus ; ils nécessitent des sessions réelles et un accès aux navigateurs.

## Définition

- « Sessions V2 » : onglets/visites regroupés par identifiant de session, conservé dans `sessionStorage` et renouvelé après 30 minutes d'inactivité de navigation.
- « Visiteurs V2 » : identifiants de navigateur pseudonymisés côté serveur, **pas des êtres humains vérifiés**.
- « Engagée » : session avec événement de visibilité de 15 secondes.
- « Retours » : identifiants vus sur au moins deux jours UTC dans la fenêtre.
- « Suspicion » : au moins 30 événements `visit` en une minute ; nécessite revue, non suppression automatique.

## Précautions

- La limite générale du canal `analytics` demeure une défense contre les abus, pas une preuve anti-bot.
- Les clients anciens déjà mis en cache peuvent envoyer un `visit` historique pendant la transition.
- Les événements perdus lorsque le navigateur est fermé sans réseau ne peuvent pas être récupérés par ce système.
- Le tableau ancien et le nouveau ne sont pas directement comparables sur la période antérieure à l'activation V2.
