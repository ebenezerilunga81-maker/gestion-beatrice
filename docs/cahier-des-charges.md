# Cahier des charges — GESTION BÉATRICE

**Version :** 0.4 — rôles et validation des décisions de passage précisés  
**Statut :** document de cadrage évolutif

## 1. Objectif général

Mettre en place une application permettant d'enregistrer et de suivre les paiements des frais scolaires, de conserver l'historique des versements et de donner aux responsables une vue fiable sur les recettes et les soldes.

## 2. Profils et responsabilités

L'application distingue trois profils : **ADMINISTRATEUR**, **PRÉFET** et **CAISSIER**. Chaque profil dispose uniquement des permissions correspondant à ses responsabilités.

### 2.1 Administrateur

L'administrateur assure l'administration de l'application et la validation annuelle des décisions de passage des élèves. Il peut :
- créer les comptes du préfet et des caissiers ;
- modifier les informations des comptes, désactiver ou réactiver un compte ;
- consulter les activités et les opérations effectuées par les utilisateurs ;
- configurer les années scolaires et les jours fériés ;
- créer et gérer la grille tarifaire de chaque année scolaire ;
- consulter les élèves, les paiements et l'ensemble des recettes ;
- après la proclamation des résultats, valider individuellement la décision de chaque élève pour l'année scolaire suivante : PROMU, REDOUBLE ou SORTANT ; la fin de cycle est enregistrée pour un élève qui termine la quatrième humanité.

L'administrateur ne réalise pas les opérations de caisse et ne modifie ni ne supprime directement les paiements.

### 2.2 Préfet

Le préfet assure la supervision pédagogique et financière de l'établissement. Il peut :
- consulter les élèves, leurs inscriptions et les décisions de passage validées par l'administrateur ;
- consulter tous les paiements, toutes les recettes et tous les soldes ;
- superviser l'ensemble des caissiers ;
- consulter les archives scolaires ;
- supprimer un paiement uniquement avec un motif obligatoire et une traçabilité complète.

Le préfet ne valide pas les décisions de passage en classe supérieure et ne modifie pas les paiements.

### 2.3 Caissier

Le caissier travaille au guichet. Il peut :
- rechercher un élève inscrit pour l'année scolaire active ;
- enregistrer les versements et imprimer les tickets ;
- consulter ses propres paiements et ses propres recettes ;
- rectifier ses propres paiements, avec conservation des anciennes et nouvelles valeurs.

Le caissier ne peut ni supprimer un paiement, ni valider une décision de passage, ni administrer les comptes utilisateurs.

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

- Date d'application initiale de la grille tarifaire (à confirmer). La reconduction automatique annuelle est validée ; les modifications des tarifs annuels relèvent de l'administrateur.
- Champs d'identification supplémentaires pour distinguer les homonymes.
- Processus technique de rectification en caisse et de suppression par le préfet avec motif obligatoire.
- Écran, calendrier et procédure de validation individuelle des décisions de passage par l'administrateur après la proclamation du 2 juillet.
- Définir précisément les règles de passage automatique de classe après validation : promotion à la classe suivante, redoublement dans la même classe, sortie sans réinscription et fin de cycle après la quatrième humanité.
- Contenu et format du ticket.
- Rapports, filtres et périodes de consultation.
- Confirmation du caractère obligatoire de l'option pour tous les élèves des humanités.
- Politique de sauvegarde et de restauration.

Ce document sera complété au fur et à mesure des décisions validées. Aucune règle non confirmée ne doit être considérée comme définitive.
