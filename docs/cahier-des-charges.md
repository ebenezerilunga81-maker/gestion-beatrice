# Cahier des charges — GESTION BÉATRICE

**Version :** 0.1 — exigences recueillies  
**Statut :** document de cadrage évolutif

## 1. Objectif général

Mettre en place une application permettant d'enregistrer et de suivre les paiements des frais scolaires, de conserver l'historique des versements et de donner aux responsables une vue fiable sur les recettes et les soldes.

## 2. Profils et responsabilités

### 2.1 Préfets

Les préfets assurent la supervision générale. Ils doivent pouvoir consulter :
- les élèves et leurs paiements enregistrés ;
- les élèves ayant payé et les dossiers sans paiement enregistré ;
- les recettes et les montants encaissés ;
- les soldes restant dus ;
- les différentes catégories de frais et leur suivi.

### 2.2 Caissiers

Les caissiers travaillent au guichet. Ils doivent pouvoir :
- enregistrer un nouvel élève lors de son premier paiement ;
- rechercher un élève par son nom ;
- consulter les paiements déjà enregistrés ;
- voir les montants encaissés et les soldes ;
- enregistrer les versements et imprimer un ticket.

Les droits exacts de création, modification, désactivation et suppression des comptes restent à préciser.

## 3. Organisation scolaire

Les catégories et classes sont prédéfinies dans l'application.

| Catégorie | Classes |
|---|---|
| Maternelle | Première maternelle, Deuxième maternelle, Troisième maternelle |
| Primaire | Première primaire, Deuxième primaire, Troisième primaire, Quatrième primaire, Cinquième primaire, Sixième primaire, Septième primaire, Huitième primaire |
| Secondaire | Première secondaire, Deuxième secondaire, Troisième secondaire, Quatrième secondaire |

Chaque élève doit obligatoirement être associé à une catégorie et à une classe. La liste des classes proposée doit dépendre de la catégorie sélectionnée.

### 3.1 Options du secondaire

Pour les élèves du secondaire, l'option doit être enregistrée avec la classe. Les options communiquées sont :
1. Pédagogique
2. Scientifique
3. Coupe et couture
4. Commerciale et gestion
5. Latin philo
6. Mécanique
7. Électricité
8. Construction

Ces options concernent les quatre classes du secondaire. Leur caractère obligatoire pour chaque inscription secondaire reste à confirmer.

## 4. Types de frais et tarifs

Les types de frais prédéfinis sont :
- Frais scolaires
- Frais techniques
- Frais orgamat

Les tarifs de référence seront définis à l'avance pour chaque type de frais. Les montants exacts ne sont pas encore communiqués.

## 5. Élèves et identification

Pour la première version, il n'y a pas de préinscription complète des élèves. Lors du premier paiement, le caissier saisit le nom de l'élève et sélectionne sa catégorie, sa classe et, pour le secondaire, son option.

La recherche se fait par nom. Pour éviter de créer plusieurs fiches pour un même élève, un mécanisme d'identification complémentaire pourra être défini. Le nom seul peut être insuffisant en cas d'homonymie ; aucun champ supplémentaire obligatoire n'est imposé à ce stade.

Lorsqu'aucun dossier correspondant n'est trouvé, l'application doit afficher un message prudent, par exemple :

> Aucun enregistrement de paiement ne correspond à ce nom. Veuillez vérifier l'orthographe ou procéder à un nouvel enregistrement si nécessaire.

L'absence de dossier dans l'application signifie qu'aucun paiement n'y est enregistré ; elle ne prouve pas à elle seule que l'élève n'a jamais payé.

## 6. Enregistrement des paiements

Parcours prévu au guichet :
1. Saisir le nom de l'élève.
2. Sélectionner la catégorie.
3. Sélectionner la classe correspondante.
4. Sélectionner l'option si l'élève est au secondaire.
5. Sélectionner le type de frais.
6. Saisir le montant réellement reçu.
7. Valider le paiement.
8. Enregistrer le versement et actualiser le solde.
9. Imprimer le ticket.

## 7. Paiements partiels et soldes

Le paiement peut être inférieur au tarif de référence. L'application doit conserver chaque versement et calculer :
- le montant total dû ;
- le montant cumulé payé ;
- le solde restant.

Exemple illustratif : montant dû de 50 000 FC, versement de 20 000 FC, solde de 30 000 FC. Les versements ultérieurs doivent être ajoutés à l'historique du même élève et du même frais concerné.

## 8. Tickets

Un ticket doit pouvoir être imprimé après l'enregistrement d'un paiement. Les champs exacts à afficher (numéro, date, identité, classe, option, type de frais, montant reçu, solde, caissier, etc.) restent à valider.

## 9. Tableaux de bord et recherche

Les préfets et les caissiers doivent pouvoir rechercher les élèves par nom et consulter les paiements enregistrés. Les tableaux de bord devront présenter les informations financières utiles à leurs responsabilités, notamment les recettes, les versements et les soldes.

Les règles précises de calcul des recettes, les filtres (période, classe, catégorie, type de frais) et les rapports à imprimer seront détaillés ultérieurement.

## 10. Architecture technique retenue

- **GitHub :** dépôt du code source.
- **Supabase :** base de données PostgreSQL centralisée.
- **Render :** hébergement de l'application.

Les clés et mots de passe devront rester dans les variables d'environnement et ne jamais être commis dans GitHub.

## 11. Principes de fiabilité à respecter

- Conserver l'historique des versements partiels.
- Ne pas effacer silencieusement les opérations financières.
- Associer chaque paiement au caissier qui l'a enregistré.
- Prévoir une référence unique pour chaque paiement ou ticket.
- Contrôler les accès selon le rôle.
- Protéger les données et les secrets de connexion.

## 12. Points restant à définir

- Tarifs exacts par type de frais et éventuelles différences selon la classe ou l'option.
- Champs d'identification supplémentaires pour distinguer les homonymes.
- Permissions précises de gestion des comptes.
- Règle de traitement des corrections ou annulations de paiements.
- Contenu et format du ticket.
- Rapports, filtres et périodes de consultation.
- Confirmation du caractère obligatoire de l'option pour tous les élèves du secondaire.
- Politique de sauvegarde et de restauration.

Ce document sera complété au fur et à mesure des décisions validées. Aucune règle non confirmée ne doit être considérée comme définitive.
