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
end $$;

select
  (select count(*) from public.students) as students_preserved,
  (select count(*) from public.payments) as payments_preserved,
  (select count(*) from public.tickets) as tickets_preserved,
  (select count(*) from public.school_years) as school_years_preserved;
