# Cahier des charges — GESTION BÉATRICE

**Version :** 0.5 — recentrage confirmé sur la gestion financière scolaire  
**Statut :** orientation fonctionnelle validée ; implémentation à réaliser progressivement

## 1. Objectif général

GESTION BÉATRICE est une application de **gestion financière scolaire**. Elle sert à enregistrer les frais encaissés, suivre les paiements partiels, calculer les soldes, produire les tickets, consulter les recettes et comparer les encaissements aux effectifs réels communiqués par l'administration.

L'application n'est pas un logiciel de gestion académique ou de gestion pédagogique des élèves.

## 2. Périmètre fonctionnel validé

### 2.1 Fonctions conservées

- Gestion des comptes et des rôles ADMINISTRATEUR, PRÉFET et CAISSIER.
- Paramétrage des années scolaires et des tarifs.
- Enregistrement des paiements complets ou partiels.
- Identification minimale des élèves nécessaire à la caisse.
- Recherche et réutilisation d'une fiche élève existante pendant toute l'année scolaire.
- Consultation du cumul payé et du solde par type de frais.
- Historique des paiements, tickets, rectifications et traçabilité.
- Tableaux de bord, rapports financiers et archives annuelles.
- Saisie administrative des effectifs réels par année, section et classe, avec distinction filles/garçons.

### 2.2 Fonctions exclues

L'application ne doit plus assurer :
- les inscriptions scolaires ou académiques comme processus de gestion autonome ;
- les décisions de fin d'année (promu, redouble, sortant, fin de cycle) ;
- les promotions ou redoublements automatiques ou manuels ;
- les saisies de notes, résultats ou autres données pédagogiques ;
- le suivi du parcours académique de l'élève.

Les données de classe et de section restent utilisables comme **repères de classement financier** pour appliquer les tarifs, filtrer les rapports et comparer les paiements aux effectifs. Elles ne constituent pas une inscription académique.

## 3. Profils et responsabilités

### 3.1 Administrateur

L'administrateur peut :
- créer, modifier, désactiver et réactiver les comptes autorisés ;
- consulter les activités, élèves, paiements, recettes et soldes ;
- configurer les années scolaires, jours fériés et grilles tarifaires ;
- saisir et corriger les effectifs globaux et détaillés par année, section et classe ;
- consulter les tableaux comparatifs entre effectifs déclarés, paiements et soldes.

L'administrateur ne réalise pas les opérations de caisse et ne modifie ni ne supprime directement les paiements.

### 3.2 Préfet

Le préfet supervise les opérations financières. Il peut consulter les élèves, les paiements, recettes, soldes, rapports et archives, et exercer les droits de correction/suppression de paiements déjà définis dans les règles de contrôle et d'audit.

Le préfet ne gère pas les inscriptions, les décisions ni les promotions.

### 3.3 Caissier

Le caissier recherche une fiche élève existante, enregistre les versements, imprime les tickets et consulte les opérations autorisées. Il peut créer une fiche minimale lorsqu'aucune fiche n'existe au moment du premier paiement.

Le caissier ne gère ni les effectifs administratifs, ni les comptes utilisateurs, ni les décisions académiques.

## 4. Identification minimale des élèves à la caisse

La base des élèves est conservée uniquement pour identifier les payeurs et rattacher correctement leurs paiements.

Au premier paiement de l'année, si aucune fiche correspondante n'existe, le caissier crée une fiche minimale avec les informations nécessaires à l'identification et à la tarification (nom, section, classe et option si applicable).

Lorsqu'un élève revient payer un autre frais ou compléter un paiement, le caissier saisit son nom : le système propose les fiches correspondantes. Après sélection, il retrouve notamment :
- les frais scolaires déjà payés et le solde restant ;
- les frais techniques déjà payés et le solde restant ;
- les frais orgamat déjà payés et le solde restant ;
- les autres paiements de l'année et leur historique.

Le système doit réutiliser la fiche existante et empêcher la création involontaire d'un doublon. En cas d'homonymie, il présente plusieurs candidats clairement différenciés ; il ne fusionne jamais automatiquement des personnes.

Il n'existe plus de processus autonome d'inscription ou de validation d'inscription. La création d'une fiche au premier paiement est une opération d'identification nécessaire à la caisse.

## 5. Organisation des sections et classes

Les sections et classes servent au classement des paiements, à l'application des tarifs et à la production des rapports.

| Section | Classes |
|---|---|
| Maternelle | Première, deuxième et troisième maternelle |
| Primaire | Première à huitième primaire |
| Humanités | Première à quatrième humanité |

Pour les humanités, l'option peut être conservée comme information de classement et de tarification lorsqu'elle est applicable. Elle ne constitue pas un dossier pédagogique.

## 6. Effectifs scolaires déclarés par l'administration

Un module **Effectifs scolaires** doit permettre à l'administrateur de saisir manuellement, pour chaque année scolaire :
- l'effectif total de l'établissement ;
- les effectifs par section ;
- les effectifs par classe ;
- le nombre de garçons et le nombre de filles pour chaque niveau de détail.

Les totaux doivent être calculés et contrôlés par l'application. Les valeurs saisies doivent être conservées par année scolaire afin de permettre les comparaisons historiques. Les effectifs ne doivent pas être déduits du nombre de fiches d'élèves ou de paiements, car ils sont communiqués par l'établissement et peuvent inclure des élèves qui n'ont pas encore payé.

Les tableaux de bord financiers doivent pouvoir rapprocher, sans les confondre :
- l'effectif réel déclaré ;
- le nombre d'élèves ayant effectué au moins un paiement ;
- les montants attendus selon les tarifs applicables et les effectifs ;
- les montants encaissés ;
- les soldes restant à recouvrer, selon les règles de calcul validées.

Toute formule de calcul des montants attendus doit s'appuyer sur les tarifs et effectifs enregistrés ; aucune estimation ne doit être présentée comme un encaissement réel.

## 7. Types de frais et tarifs

Les codes techniques existants doivent rester inchangés : `SCOLAIRES`, `TECHNIQUES` et `ORGAMAT`.

Les tarifs restent configurables par année scolaire, section/classe, option si applicable et type de frais. Les tarifs historiques ne sont jamais modifiés rétroactivement.

La grille tarifaire de référence précédemment communiquée demeure à confirmer/maintenir dans le paramétrage existant ; aucune migration ne doit recréer, écraser ou recalculer les tarifs déjà enregistrés.

## 8. Paiements partiels, soldes et tickets

Chaque versement est conservé comme une opération distincte, associé à l'élève, au type de frais, à l'année scolaire et au caissier qui l'a enregistré.

L'application calcule pour chaque frais :
- le montant dû selon le tarif applicable ;
- le cumul des versements valides ;
- le solde restant.

Les paiements en CDF et USD conservent la devise, le montant et le taux appliqué au moment de l'opération. Les anciens paiements ne sont jamais recalculés avec un nouveau taux de change.

Chaque paiement validé produit une référence/ticket unique. Les rectifications et annulations suivent les règles de traçabilité déjà définies ; aucune opération financière ne doit être effacée silencieusement.

## 9. Nouvelle année scolaire et archives

À l'ouverture d'une nouvelle année scolaire :
- les paiements de l'année précédente restent consultables dans les archives ;
- les fiches d'identification des élèves sont conservées et peuvent être retrouvées ;
- les nouveaux paiements sont rattachés à la nouvelle année et ne sont jamais mélangés aux paiements antérieurs ;
- les effectifs de la nouvelle année sont saisis séparément par l'administration ;
- les paramètres annuels nécessaires à la caisse sont préparés pour la nouvelle année.

Aucune décision de promotion, de redoublement ou de sortie n'est enregistrée par l'application. La classe utilisée pour les paiements de la nouvelle année est renseignée selon les informations communiquées par l'établissement, sans automatisme de passage de classe.

Les archives financières annuelles sont en lecture seule et préservent les tickets et historiques.

## 10. Tableaux de bord, rapports et archivage

Les écrans de supervision sont orientés vers les finances : recettes par période, type de frais, section, classe et caissier ; montants dus, montants payés, soldes et comparaisons avec les effectifs déclarés.

Un seul espace **Archivage** regroupe la consultation annuelle des paiements. Les filtres et présentations détaillés sont définis dans les décisions fonctionnelles déjà validées.

## 11. Architecture et protection des données

- **GitHub :** dépôt du code source.
- **Supabase :** base de données PostgreSQL centralisée.
- **Render :** hébergement de l'application.

Les clés et mots de passe restent dans les variables d'environnement. Les règles d'accès doivent être vérifiées côté serveur et en base de données. Aucune donnée financière historique ne peut être supprimée lors du retrait des fonctions académiques.

## 12. Règles de migration et de mise en production

La refonte doit être réalisée progressivement, sur une branche de travail et testée avant fusion et déploiement.

- Ne pas supprimer physiquement les élèves, paiements, tickets, tarifs ou archives existants.
- Ne pas supprimer une table ou une colonne historique tant qu'il existe des dépendances ou des données à préserver.
- Retirer d'abord les interfaces et opérations académiques, puis adapter le modèle de données uniquement après audit des dépendances.
- Toute migration doit être additive ou réversible autant que possible, documentée et testée sur les données de test.
- Vérifier les parcours de recherche d'élève, paiement partiel, second paiement, consultation de l'historique, ticket, archives et effectifs.
- Ne mettre en production qu'après vérification des tests et contrôle de l'intégrité des données.

Ce cahier des charges remplace les passages antérieurs qui prévoyaient la gestion des inscriptions, décisions et promotions. Les règles financières et de conservation des archives restent applicables.
