# GESTION BÉATRICE

Application de gestion des frais scolaires et de suivi des paiements.

## Objectif

Centraliser l'enregistrement des paiements des élèves, le suivi des versements partiels, le calcul des soldes et la consultation des recettes par les préfets et les caissiers.

## Architecture retenue

- **Base de données :** Supabase (PostgreSQL).
- **Hébergement de l'application :** Render.
- **Dépôt de code :** GitHub.

Aucun secret, mot de passe ou clé d'accès ne doit être enregistré dans ce dépôt. Les paramètres de connexion seront configurés dans les variables d'environnement des services concernés.

## Profils utilisateurs

- **Préfets :** supervision générale, consultation des élèves et paiements, suivi des recettes, des soldes et des catégories de frais.
- **Caissiers :** enregistrement des paiements, recherche des élèves, consultation des paiements enregistrés et impression des tickets.

Les permissions détaillées de gestion des comptes seront précisées avant leur implémentation.

## Fonctionnalités prévues

- Enregistrement d'un élève au moment de son premier paiement.
- Recherche d'un élève par son nom et rattachement des versements ultérieurs à sa fiche.
- Gestion des paiements complets ou partiels et calcul du solde restant.
- Historique des versements.
- Impression d'un ticket après validation du paiement.
- Tableaux de suivi adaptés aux préfets et aux caissiers.

## Structure scolaire

- **Maternelle :** Première, Deuxième et Troisième maternelle.
- **Primaire :** Première à Huitième primaire.
- **Secondaire :** Première à Quatrième secondaire.

Les huit options du secondaire sont : Pédagogique, Scientifique, Coupe et couture, Commerciale et gestion, Latin philo, Mécanique, Électricité et Construction.

## Types de frais

- Frais scolaires
- Frais techniques
- Frais orgamat

Les tarifs de référence seront paramétrés. Le caissier saisira le montant réellement reçu, qui peut être inférieur au tarif.

## État du projet

Phase de cadrage et de préparation. Les écrans, règles métier détaillées, schéma de base de données, authentification et déploiement seront réalisés progressivement après validation.

Voir [le cahier des charges](docs/cahier-des-charges.md) pour les exigences recueillies.
