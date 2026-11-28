-- Effectifs déclarés par établissement et ventilés par classe pour chaque année.
-- Aucune donnée financière ou historique existante n'est modifiée.
begin;

create table if not exists public.school_year_headcounts (
  id uuid primary key default gen_random_uuid(),
  school_year_id uuid not null unique references public.school_years(id) on delete restrict,
  total_students integer not null check (total_students >= 0),
  total_boys integer not null check (total_boys >= 0),
  total_girls integer not null check (total_girls >= 0),
  notes text,
  declared_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint headcount_gender_total_check check (total_boys + total_girls = total_students)
);

create table if not exists public.school_year_class_headcounts (
  id uuid primary key default gen_random_uuid(),
  school_year_id uuid not null references public.school_years(id) on delete restrict,
  class_id smallint not null references public.classes(id) on delete restrict,
  option_id smallint references public.options(id) on delete restrict,
  boys integer not null default 0 check (boys >= 0),
  girls integer not null default 0 check (girls >= 0),
  declared_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint class_headcount_gender_total_check check (boys + girls >= 0),
  constraint class_headcount_unique unique (school_year_id, class_id, option_id)
);

create index if not exists school_year_class_headcounts_year_idx
  on public.school_year_class_headcounts(school_year_id, class_id);

alter table public.school_year_headcounts enable row level security;
alter table public.school_year_class_headcounts enable row level security;

drop policy if exists "admin manages declared school headcounts" on public.school_year_headcounts;
create policy "admin manages declared school headcounts"
on public.school_year_headcounts
for all to authenticated
using (public.current_app_role() = 'ADMINISTRATEUR')
with check (public.current_app_role() = 'ADMINISTRATEUR');

drop policy if exists "admin manages class headcounts" on public.school_year_class_headcounts;
create policy "admin manages class headcounts"
on public.school_year_class_headcounts
for all to authenticated
using (public.current_app_role() = 'ADMINISTRATEUR')
with check (public.current_app_role() = 'ADMINISTRATEUR');

comment on table public.school_year_headcounts is
'Effectif total déclaré par établissement pour une année scolaire. Source manuelle, indépendante des paiements.';
comment on table public.school_year_class_headcounts is
'Ventilation manuelle des effectifs par classe et option pour une année scolaire.';

commit;
