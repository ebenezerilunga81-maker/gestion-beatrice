# Cahier des charges — GESTION BÉATRICE

**Version :** 0.3 — reconduction automatique des tarifs intégrée  
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

Les droits sont différenciés : les caissiers enregistrent et peuvent rectifier les paiements, mais ne peuvent pas les supprimer. Les préfets supervisent les recettes et peuvent supprimer un paiement avec motif et traçabilité, mais ne peuvent pas modifier un paiement. Le caissier suit ses propres recettes ; le préfet supervise les recettes de tous les caissiers.

## 3. Organisation scolaire

Les catégories et classes sont prédéfinies dans l'application.

| Catégorie | Classes |
|---|---|
| Maternelle | Première maternelle, Deuxième maternelle, Troisième maternelle |
| Primaire | Première primaire, Deuxième primaire, Troisième primaire, Quatrième primaire, Cinquième primaire, Sixième primaire, Septième primaire, Huitième primaire |
| Humanité | Première humanité, Deuxième humanité, Troisième humanité, Quatrième humanité |

Chaque élève doit obligatoirement être associé à une catégorie et à une classe. La liste des classes proposée doit dépendre de la catégorie sélectionnée.

### 3.1 Options du humanités

Pour les élèves des humanités, l'option doit être enregistrée avec la classe. Les options communiquées sont :
1. Pédagogique
2. Scientifique
3. Coupe et couture
4. Commerciale et gestion
5. Latin philo
6. Mécanique
7. Électricité
8. Construction

Ces options concernent les quatre classes du humanités. Leur caractère obligatoire pour chaque inscription humanités reste à confirmer.

## 4. Types de frais et tarifs

Les types de frais prédéfinis sont :
- Frais scolaires
- Frais techniques
- Frais orgamat

### Grille tarifaire communiquée

Les tarifs sont exprimés dans deux devises, selon le type de frais :

| Catégorie / classe | Frais scolaires |
|---|---:|
| Première, deuxième et troisième maternelle | 210 USD |
| Première à huitième primaire | 170 USD |
| Première, deuxième et troisième humanité | 180 USD |
| Quatrième humanité | 220 USD |

Les autres frais sont uniformes pour les 15 classes :
- Frais techniques : 30 USD par élève.
- Frais orgamat : 7 000 CDF par élève.

Les frais techniques et orgamat sont distincts des frais scolaires et peuvent être suivis séparément. La grille de référence sera automatiquement copiée dans les tarifs de chaque nouvelle année scolaire lors de sa création. Cette reconduction est le comportement normal : elle évite de ressaisir les tarifs chaque année et conserve un historique indépendant par année scolaire. Avant l'ouverture de l'année, un préfet ou un administrateur habilité pourra modifier les tarifs de cette année si l'établissement adopte une nouvelle grille. Ces ajustements ne modifieront ni la grille de référence ni les tarifs des années déjà enregistrées. Si aucune modification n'est décidée, les tarifs copiés resteront applicables.

Pour les humanités, les tarifs communiqués sont identiques quelle que soit l'option ; le modèle de données permet néanmoins une différenciation par option si une décision future le demande.

## 5. Élèves et identification

Pour la première version, il n'y a pas de préinscription complète des élèves. Lors du premier paiement, le caissier saisit le nom de l'élève et sélectionne sa catégorie, sa classe et, pour le humanités, son option.

La recherche se fait par nom. Pour éviter de créer plusieurs fiches pour un même élève, un mécanisme d'identification complémentaire pourra être défini. Le nom seul peut être insuffisant en cas d'homonymie ; aucun champ supplémentaire obligatoire n'est imposé à ce stade.

Lorsqu'aucun dossier correspondant n'est trouvé, l'application doit afficher un message prudent, par exemple :

> Aucun enregistrement de paiement ne correspond à ce nom. Veuillez vérifier l'orthographe ou procéder à un nouvel enregistrement si nécessaire.

L'absence de dossier dans l'application signifie qu'aucun paiement n'y est enregistré ; elle ne prouve pas à elle seule que l'élève n'a jamais payé.

## 6. Enregistrement des paiements

Parcours prévu au guichet :
1. Saisir le nom de l'élève.
2. Sélectionner la catégorie.
3. Sélectionner la classe correspondante.
4. Sélectionner l'option si l'élève est au humanités.
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

- Date d'application initiale de la grille tarifaire (à confirmer). La reconduction automatique annuelle est validée ; les éventuelles modifications doivent être effectuées par un préfet ou administrateur habilité avant l'ouverture de l'année concernée.
- Champs d'identification supplémentaires pour distinguer les homonymes.
- Permissions précises de gestion des comptes utilisateurs (création, désactivation et administration).
- Processus technique de rectification en caisse et de suppression par le préfet avec motif obligatoire.
- Contenu et format du ticket.
- Rapports, filtres et périodes de consultation.
- Confirmation du caractère obligatoire de l'option pour tous les élèves des humanités.
- Politique de sauvegarde et de restauration.

Ce document sera complété au fur et à mesure des décisions validées. Aucune règle non confirmée ne doit être considérée comme définitive.
