-- GESTION BÉATRICE — environnement Supabase simulé pour tests PostgreSQL locaux/CI.
-- ATTENTION : réservé à une base éphémère de TEST. Ne jamais exécuter sur Supabase officiel.

do $$
begin
  if not exists (select 1 from pg_catalog.pg_roles where rolname = 'anon') then
    create role anon nologin;
  end if;
  if not exists (select 1 from pg_catalog.pg_roles where rolname = 'authenticated') then
    create role authenticated nologin;
  end if;
  if not exists (select 1 from pg_catalog.pg_roles where rolname = 'service_role') then
    create role service_role nologin bypassrls;
  end if;
end;
$$;

create schema if not exists auth;
create table if not exists auth.users (
  id uuid primary key,
  email text unique,
  created_at timestamptz not null default now()
);

-- Simule la récupération de l'identifiant utilisateur depuis le JWT Supabase.
-- Le test peut définir request.jwt.claim.sub avec SET ou set_config().
create or replace function auth.uid()
returns uuid
language sql
stable
set search_path = ''
as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
$$;

grant usage on schema auth to anon, authenticated, service_role;
grant execute on function auth.uid() to anon, authenticated, service_role;
grant select on auth.users to service_role;
