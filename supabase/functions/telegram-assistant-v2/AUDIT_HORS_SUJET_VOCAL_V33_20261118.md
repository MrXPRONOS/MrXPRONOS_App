# Routage des demandes hors domaine et vocaux incompréhensibles — V33

**Date :** 18 novembre 2026  
**Fonction déployée :** `telegram-assistant-v2` **V33 ACTIVE** sur Supabase  
**Bot historique des coupons :** `telegram_webhook` **V38 ACTIVE** (non modifié)  
**Branche :** `feature/telegram-assistant-nvidia-v2-20261107`  
**Tests :** [GitHub Actions #44207017023](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/44207017023)

## Comportements introduits

1. **Vocal mal compris :** un échec du téléchargement/transcription, une transcription jugée peu fiable ou corrompue produit uniquement :  
   > 🎙️ Je n’ai pas bien compris ton vocal. Écris-moi ta question ici, je te répondrai.  
   Aucun extrait reconnu incertain ne s'affiche dans le chat.

2. **Texte incompréhensible :** un texte vide de sens, ou une question que l'IA classe explicitement comme incompréhensible, reçoit :  
   > Je n’ai pas bien compris ton message. Peux-tu le reformuler par écrit ?

3. **Texte clairement hors domaine Mr XPRONOS :** pas de réponse Telegram automatique au client. Un message privé **« 📌 QUESTION HORS DOMAINE — Mr XPRONOS »** est envoyé à l'administrateur avec l'expéditeur, la référence du chat, le message masqué pour certains secrets et les commandes **/history** et **/reply**.

4. **Retour au sujet :** le chat ne passe **pas** en pause humaine permanente à cause du hors-sujet. Le client peut ensuite demander des pronostics, une inscription ou un lien et obtenir une réponse normale. Un nouvel abonné hors sujet ne reçoit pas l'accueil avant une première demande pertinente.

5. **Classification prudente :** les demandes explicitement étrangères (météo, recettes, CV, santé, crypto hors paris, équipements, élevage, football versus autres sports) sont reconnues par le serveur. Pour les demandes générales sans lien clairement déterminé, l'IA doit renvoyer un champ JSON `scope` égal à `in_scope`, `out_of_scope` ou `unclear`. Les salutations, questions de suivi, partenaires, le site et les droits sur les données restent traités normalement. Les noms de partenaires ou liens douteux ne sont pas substitués par un lien inventé.

## Validation reproductible

**Suite complète : 210 tests réussis / 210**, zéro échec.

**Nouveau test d'intégration, via le véritable `handleUpdate` :**
- 13 messages répartis entre plusieurs clients fictifs
- **4 alertes « hors domaine » à l'administrateur**
- **4 messages hors sujet sans réponse au client**
- **2 vocaux mal compris** avec demande explicite de message écrit
- Retour aux coupons après une question météo ou une recette
- Premier message hors sujet sans accueil automatique
- Texte incohérent recevant une demande de reformulation
- Cas d'un sujet hors domaine identifié par le champ `scope` du modèle
- Vérification d'une question liée au droit à la suppression des données

**Test du classificateur : 27 formulations** couvrant les sujets pertinents, hors-sujet, ambigus et incompréhensibles, y compris la confusion entre **« à côté »** et une **cote de bookmaker**.

## Limites

Les tests isolent Supabase, Telegram et NVIDIA derrière des fournisseurs simulés : **l'expédition d'une alerte vers le véritable compte administrateur, la reconnaissance acoustique réelle et la capacité des modèles à classer toutes les formulations inédites ne sont pas confirmées par ces tests.**

La notification ne peut pas être garantie si l'identifiant de l'administrateur est mal configuré, si le compte administrateur n'a jamais autorisé le bot ou si Telegram refuse l'envoi. En cas d'échec, la fonction émet un avertissement technique et conserve le message client dans l'historique serveur. Un contrôle depuis un second compte Telegram est nécessaire.

**Tests pratiques conseillés :** depuis un compte non administrateur, envoyer « Quel temps fera-t-il demain ? », « Peux-tu me donner les pronostics du jour ? », un vocal inaudible et « Je veux créer un compte sur Melbet ». Confirmer que l'administrateur reçoit uniquement l'alerte hors domaine et que le client voit le message d'invitation à écrire pour le vocal.

**Hors périmètre :** cette modification ne change ni la priorité Mistral Large 4, ni le délai configuré par modèle, ni le webhook historique des coupons.
