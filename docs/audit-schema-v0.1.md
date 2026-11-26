# Audit du schéma initial — GESTION BÉATRICE
Date : 26 novembre 2026
Statut : audit préparatoire — aucune migration exécutée.

## État vérifié
- Projet Supabase ciblé : GESTION BÉATRICE OFFICIEL (`dqxaogxgnjqyvjoscwep`).
- Le schéma `public` ne contient encore aucune table.
- Aucune migration n'est enregistrée.
- L'analyse de sécurité Supabase ne signale actuellement aucun lint, ce qui ne valide pas le brouillon SQL : les tables n'existent pas encore.
- Le projet CNAC-Mobile (`wsvypouqrrqduajylmdz`) n'a pas été touché.

## Conclusion
Le fichier `database/schema_initial.sql` est un bon inventaire de départ, mais il ne doit pas être exécuté tel quel. Il manque des règles métier essentielles et plusieurs politiques d'accès ne correspondent pas aux rôles convenus.

## Corrections obligatoires avant toute migration

### P0 — Sécurité et contrôle d'accès
1. Ajouter le rôle `ADMINISTRATEUR` dans le modèle des profils et les contrôles d'accès.
2. Définir précisément les droits par rôle dans la base, pas uniquement dans l'interface :
   - ADMINISTRATEUR : comptes, années, jours fériés, tarifs, consultation générale et validation individuelle des décisions ; aucune opération de caisse.
   - PRÉFET : supervision, consultation générale, suppression de paiement avec motif ; pas de validation de promotion et pas de modification de paiement.
   - CAISSIER : encaissement, consultation de ses propres paiements/recettes, rectification de ses propres paiements ; aucune suppression.
3. La politique actuelle `tickets_read_authenticated` donne à tout utilisateur authentifié accès à tous les tickets. Restreindre les tickets du caissier à ses propres paiements et réserver la vue complète au préfet/administrateur selon les besoins validés.
4. Encadrer les fonctions `SECURITY DEFINER` : schéma non exposé lorsque possible, `search_path` fixe, contrôle d'identité et de rôle, révocation de l'exécution publique/anon, puis attribution explicite des droits nécessaires.
5. Ne pas permettre la création ou la modification de profils/rôles depuis le navigateur. La création des utilisateurs Auth et de leurs profils doit passer par un serveur de confiance utilisant la clé secrète côté serveur uniquement.
6. Interdire les écritures directes non prévues dans les tables d'audit et les référentiels.
7. Vérifier les privilèges SQL et l'exposition Data API explicitement. Depuis le 30 octobre 2026, les nouvelles tables ne sont plus automatiquement exposées à la Data API : n'exposer que les tables nécessaires, avec RLS activée et droits explicites.

### P0 — Paiements et tickets
1. Le contrôle d'insertion actuel ne vérifie pas que la date d'ouverture de l'année scolaire est atteinte.
2. Il ne bloque pas les inscriptions dont la décision est encore `EN_ATTENTE`.
3. Il ne vérifie pas le montant cumulé déjà payé par rapport au tarif dû. Ajouter une validation transactionnelle qui empêche le dépassement, sauf si l'établissement valide explicitement une règle de trop-perçu.
4. Vérifier strictement que le tarif appartient à la même année, catégorie, classe et option que l'inscription. La catégorie et la classe doivent elles-mêmes être cohérentes.
5. Générer automatiquement le numéro de ticket côté base dans la même transaction que le paiement. Ne pas laisser le client choisir librement `payment_reference` ou `ticket_number`.
6. Créer le ticket automatiquement après un paiement validé ; empêcher l'insertion manuelle d'un ticket arbitraire.
7. La suppression doit se faire par une fonction transactionnelle dédiée exigeant un motif non vide, autorisée uniquement au préfet, et écrivant l'audit dans la même transaction. Révoquer le DELETE direct.
8. La rectification doit être limitée au paiement du caissier connecté, avec audit avant/après ; verrouiller les champs d'identité, de tarif, d'auteur et de référence.
9. Clarifier si le paiement peut être effectué en USD et CDF selon la devise du tarif ; le montant payé doit toujours être comparé dans la même devise.

### P0 — Inscriptions et décisions
1. Ajouter la décision `FIN_CYCLE` pour la fin de 4e humanité.
2. Une décision ne peut être validée que par l'ADMINISTRATEUR après la proclamation du 2 juillet.
3. Ajouter une fonction transactionnelle pour PROMU, REDOUBLE, SORTANT et FIN_CYCLE, avec contrôle de classe suivante et d'option.
4. Le caissier ne doit pas pouvoir créer ou changer une décision ni inscrire un élève dans une année future. Séparer l'admission initiale de la caisse.
5. Ajouter des contraintes garantissant que `class_id` appartient à `category_id`, et que les options ne sont autorisées que pour les humanités. L'option doit être obligatoire pour les classes d'humanité si c'est bien la règle de l'école.
6. Conserver une inscription distincte par élève et par année, sans écraser les archives.

### P1 — Années scolaires et tarifs
1. Calculer automatiquement le premier lundi de septembre, puis reporter au prochain jour ouvrable si cette date est un jour férié officiel RDC.
2. Contrôler l'activation d'une seule année scolaire et interdire les paiements avant sa date officielle d'ouverture.
3. Copier les tarifs de référence à la création d'une année, mais conserver les tarifs annuels indépendants et historiser toute modification.
4. Protéger les tarifs déjà utilisés par des paiements ; une modification ne doit pas changer rétroactivement les soldes ou tickets existants.
5. Compléter l'audit des changements de tarifs, années, profils et décisions, pas seulement des paiements.

### P1 — Données et qualité
1. Prévoir un identifiant secondaire d'élève pour distinguer les homonymes (par exemple date de naissance ou matricule), à confirmer avant la migration.
2. Normaliser les devises en valeurs contrôlées `USD` et `CDF`.
3. Ajouter les contraintes et index nécessaires pour les recherches de caisse par année active, nom et classe.
4. Prévoir des tests RLS avec trois comptes fictifs distincts (administrateur, préfet, caissier) avant l'ouverture aux vrais utilisateurs.

## Ordre de réalisation proposé
1. Corriger le modèle relationnel et les contraintes.
2. Construire les fonctions métier transactionnelles et la génération des tickets.
3. Écrire les politiques RLS et les privilèges SQL par rôle.
4. Préparer des migrations versionnées et un jeu de tests automatisés.
5. Vérifier le schéma et les politiques sur le projet officiel, puis lancer les migrations après validation explicite.
6. Connecter l'interface à Supabase Auth et à l'API ; conserver les secrets uniquement côté serveur.

## Règle de protection
Aucune commande de création ou de modification de tables n'a été exécutée sur Supabase pendant cet audit. La base officielle reste intacte jusqu'à validation du schéma corrigé.
