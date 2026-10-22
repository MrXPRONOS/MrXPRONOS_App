# Ciné Radar — Direction artistique premium

## Référence
Cette version reproduit les quatre états de la maquette validée dans ChatGPT (catalogue général, Films, recherche, aperçu de canal) avec une identité dark cinema et des accents néon bleus/violets.

## Fonctions EXISTANTES conservées
- Choisir Tous, Films, Séries ou Animés ;
- Rechercher un canal public par nom ou genre ;
- Afficher les cartes des canaux trouvés, leurs vrais noms et le total réel ;
- Consulter la fiche d'aperçu (photo, description publiques quand accessibles) ;
- Ouvrir directement le canal sur Telegram.

Aucune création de compte, aucun favori, partage ou copie de liens, notifications ou nouvelles fonctionnalités de navigation. Le bot Telegram garde son parcours simple : catégorie → canal.

## Palette et composants
- Arrière-plan : `#07101e`, cartes : `#111e34`, relief : `#152640`, bordures : `#2b4166`.
- Accent violet : `#8558fa` ; accent bleu : `#398aff` ; texte : `#f4f8ff`.
- Onglets compacts à petites icônes SVG : bleu/violet en sélection.
- Bannières animées uniquement par transitions subtiles CSS, sans dépendances graphiques tierces.
- Grille : deux colonnes sur mobile, trois sur tablette, quatre sur grand écran.
- Modal d'aperçu : plein écran / panneau immersif sur mobile ; panneaux centrés sur grand écran ; grande image, photo du canal, titre, catégorie, description et bouton d'ouverture.

## Images et fiabilité
Les noms et chiffres illustratifs du concept visuel ne sont pas utilisés. Seules les chaînes du catalogue D1 apparaissent.
Ciné Radar affiche les vraies photos publiques dès que Telegram les rend accessibles et qu'elles figurent dans le cache public.
Lorsqu'une photo n'est pas disponible, une illustration vectorielle **d'ambiance cinématographique**, non présentée comme une véritable affiche de film ni comme une photographie du canal, s'affiche pour maintenir un design homogène.

## Performance et accessibilité
- Catalogue préchargé dans le HTML, catégories/recherche instantanées côté client.
- Préchargement limité des photos, cache D1 et mémoire pour les métadonnées publiques ; aucune collecte d'historique utilisateur.
- Boutons avec zones tactiles et `aria-label`, contrôle clavier Échap pour fermer l'aperçu, respect des préférences de réduction des animations.
- HTML/texte provenant des canaux injecté avec `textContent` plutôt qu'en HTML libre ; liens Telegram validés avant ouverture.

### Fichiers
`app-page.mjs` : style, maquette et composants ; `worker.mjs` : sert la page et injecte les canaux publics ; `radar-lean.mjs` : bot/catalogue ; `channel-preview.mjs` : aperçu de profils publics.
