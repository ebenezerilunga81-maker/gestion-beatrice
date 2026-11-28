-- Tests de structure pour le module Effectifs scolaires.
-- À exécuter après la migration 202611280001_school_year_headcounts.sql.
do $$
begin
  if to_regclass('public.school_year_headcounts') is null then
    raise exception 'Table school_year_headcounts absente';
  end if;
  if to_regclass('public.school_year_class_headcounts') is null then
    raise exception 'Table school_year_class_headcounts absente';
  end if;
  if not exists (
    select 1 from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relname = 'school_year_headcounts'
      and c.relrowsecurity
  ) then
    raise exception 'RLS non activée sur school_year_headcounts';
  end if;
  if not exists (
    select 1 from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relname = 'school_year_class_headcounts'
      and c.relrowsecurity
  ) then
    raise exception 'RLS non activée sur school_year_class_headcounts';
  end if;
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.school_year_headcounts'::regclass
      and conname = 'headcount_gender_total_check'
  ) then
    raise exception 'Contrainte de cohérence garçons/filles absente';
  end if;
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.school_year_class_headcounts'::regclass
      and conname = 'class_headcount_unique'
  ) then
    raise exception 'Contrainte d''unicité classe/option absente';
  end if;
  if has_table_privilege('anon', 'public.school_year_headcounts', 'select')
     or has_table_privilege('authenticated', 'public.school_year_headcounts', 'select')
     or has_table_privilege('anon', 'public.school_year_class_headcounts', 'select')
     or has_table_privilege('authenticated', 'public.school_year_class_headcounts', 'select') then
    raise exception 'Accès direct anon/authenticated non révoqué sur les effectifs';
  end if;
  if not has_table_privilege('service_role', 'public.school_year_headcounts', 'select')
     or not has_table_privilege('service_role', 'public.school_year_class_headcounts', 'insert') then
    raise exception 'Privilèges service_role manquants sur les effectifs';
  end if;
end $$;

select
  (select count(*) from public.students) as students_preserved,
  (select count(*) from public.payments) as payments_preserved,
  (select count(*) from public.tickets) as tickets_preserved,
  (select count(*) from public.school_years) as school_years_preserved;
