-- Les tables d'effectifs sont consommées exclusivement par l'API serveur
-- avec service_role. Aucun accès direct anon/authenticated n'est nécessaire.
begin;
revoke all on table public.school_year_headcounts from anon, authenticated, public;
revoke all on table public.school_year_class_headcounts from anon, authenticated, public;
grant select, insert, update on table public.school_year_headcounts to service_role;
grant select, insert, update on table public.school_year_class_headcounts to service_role;
commit;
