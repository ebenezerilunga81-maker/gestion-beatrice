# Plan de tests — GESTION BÉATRICE

Date de préparation : 27 novembre 2026  
Cible : base PostgreSQL jetable / environnement isolé uniquement.

## Règles impératives
- Ne pas exécuter ces tests sur le projet Supabase officiel.
- Ne pas utiliser le projet CNAC-Mobile.
- Ne jamais déposer une clé `service_role` dans un navigateur, un dépôt Git ou les journaux.
- Le smoke test SQL suppose que le schéma a déjà été installé dans une base de test. Il ne déploie pas le schéma.
- Le validateur Python est un contrôle statique de source, pas un parseur PostgreSQL.

## Fichiers
- `tests/validate_schema_source.py` : contrôles statiques du brouillon SQL.
- `tests/schema_smoke_tests.sql` : contrôle structurel des objets, RLS et privilèges après installation sur une base de test.

## Scénarios d'intégration à exécuter avec trois comptes Auth fictifs

### Administrateur
1. Peut créer une année scolaire ; préfet et caissier doivent être refusés.
2. La rentrée calculée est le premier lundi de septembre.
3. Si ce lundi est un jour férié officiel RDC enregistré, la date est reportée au prochain jour ouvrable.
4. Peut valider une décision à partir du 2 juillet de l'année de fin de l'inscription ; avant cette date, refus.
5. Peut valider PROMU et REDOUBLE ; ne peut ni encaisser ni annuler ni rectifier un paiement.

### Préfet
1. Peut lire les paiements, tickets et recettes de tous les caissiers.
2. Peut annuler un paiement VALIDE avec un motif non vide ; le paiement et le ticket restent conservés.
3. Une annulation sans motif, répétée ou par un autre rôle doit échouer.
4. Ne peut ni encaisser, ni rectifier, ni valider une décision scolaire.

### Caissier
1. Peut encaisser uniquement si l'année est active et sa date d'ouverture atteinte.
2. Un paiement partiel produit un ticket unique et une entrée d'audit.
3. Un paiement supérieur au solde restant est refusé.
4. Le tarif d'une autre année, classe ou catégorie est refusé.
5. Peut lire uniquement ses paiements et tickets.
6. Peut rectifier uniquement un paiement valide qu'il a lui-même créé ; le dépassement du tarif est refusé et l'audit conserve l'avant/après.
7. Ne peut pas annuler, supprimer, valider une décision, gérer les comptes ou modifier les tarifs.

## Tests transversaux
- Un élève ne peut avoir qu'une inscription par année scolaire.
- Une option est obligatoire en humanités et interdite en maternelle/primaire.
- Une seule année scolaire peut être active.
- Les devises acceptées sont USD et CDF ; aucun cumul entre devises.
- Une annulation conserve le ticket et exclut le montant du solde dû.
- Un utilisateur désactivé ou sans profil actif ne peut appeler aucune RPC métier.
- Les accès directs aux tables d'écriture restent refusés au rôle authenticated ; les mutations passent par le backend de confiance ou les RPC autorisées.

## État
Aucun de ces scénarios d'intégration n'a encore été exécuté. Le SQL n'a pas été appliqué à Supabase. Après création d'une base jetable, lancer d'abord le validateur source, installer le schéma sur cette base, exécuter le smoke test, puis réaliser les scénarios d'intégration avec comptes Auth temporaires.
