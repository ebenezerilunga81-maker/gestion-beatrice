-- GESTION BÉATRICE — smoke tests structurels PostgreSQL
-- À exécuter UNIQUEMENT dans une base de TEST après installation du schéma.
-- Ce script ne crée ni ne modifie de données métier.

do $$
declare
  v_count integer;
  v_bad text;
begin
  select count(*) into v_count from public.classes;
  if v_count <> 15 then
    raise exception 'TEST FAILED: 15 classes attendues, trouvé %', v_count;
  end if;

  select count(*) into v_count from public.options;
  if v_count <> 8 then
    raise exception 'TEST FAILED: 8 options attendues, trouvé %', v_count;
  end if;

  select count(*) into v_count from public.fee_types;
  if v_count <> 3 then
    raise exception 'TEST FAILED: 3 types de frais attendus, trouvé %', v_count;
  end if;

  select string_agg(t, ', ') into v_bad
  from unnest(array[
    'profiles','school_years','holidays','categories','classes','options',
    'fee_types','students','student_enrollments','fee_tariff_templates',
    'fee_tariffs','payments','tickets','audit_logs'
  ]) as x(t)
  where not coalesce((
    select c.relrowsecurity
    from pg_catalog.pg_class c
    join pg_catalog.pg_namespace n on n.oid=c.relnamespace
    where n.nspname='public' and c.relname=x.t
  ),false);
  if v_bad is not null then
    raise exception 'TEST FAILED: RLS absent sur : %', v_bad;
  end if;

  if has_table_privilege('authenticated','public.payments','INSERT')
     or has_table_privilege('authenticated','public.payments','UPDATE')
     or has_table_privilege('authenticated','public.payments','DELETE') then
    raise exception 'TEST FAILED: écriture directe payments accordée à authenticated';
  end if;
  if has_table_privilege('anon','public.payments','SELECT') then
    raise exception 'TEST FAILED: lecture anon de payments autorisée';
  end if;
  if not has_table_privilege('authenticated','public.payments','SELECT') then
    raise exception 'TEST FAILED: lecture authenticated de payments non accordée';
  end if;

  if not exists (
    select 1 from pg_catalog.pg_proc p
    join pg_catalog.pg_namespace n on n.oid=p.pronamespace
    where n.nspname='public' and p.proname='register_payment'
      and p.prosecdef
  ) then
    raise exception 'TEST FAILED: RPC register_payment SECURITY DEFINER absente';
  end if;

  if not exists (
    select 1 from pg_catalog.pg_proc p
    join pg_catalog.pg_namespace n on n.oid=p.pronamespace
    where n.nspname='public' and p.proname='correct_own_payment'
      and p.prosecdef
  ) then
    raise exception 'TEST FAILED: RPC correct_own_payment SECURITY DEFINER absente';
  end if;

  if has_function_privilege('anon','public.register_payment(uuid,uuid,numeric,text)','EXECUTE')
     or has_function_privilege('anon','public.annul_payment(uuid,text)','EXECUTE')
     or has_function_privilege('anon','public.correct_own_payment(uuid,numeric,timestamp with time zone,text)','EXECUTE')
     or has_function_privilege('anon','public.validate_student_decision(uuid,text,uuid)','EXECUTE') then
    raise exception 'TEST FAILED: anon peut exécuter une RPC métier sensible';
  end if;

  if not has_function_privilege('authenticated','public.register_payment(uuid,uuid,numeric,text)','EXECUTE')
     or not has_function_privilege('authenticated','public.annul_payment(uuid,text)','EXECUTE')
     or not has_function_privilege('authenticated','public.correct_own_payment(uuid,numeric,timestamp with time zone,text)','EXECUTE')
 then
    raise exception 'TEST FAILED: une RPC métier manque son droit EXECUTE authenticated';
  end if;

  raise notice 'SMOKE TESTS RÉUSSIS — structure, RLS, grants et RPC.';
end;
$$;
