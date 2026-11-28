-- GESTION BÉATRICE — test isolé du RPC de paiement USD/CDF.
-- Exécuté uniquement dans PostgreSQL éphémère de GitHub Actions.
-- Toutes les données de test sont annulées à la fin.

begin;

do $$
declare
  v_auth_id uuid := gen_random_uuid();
  v_cashier_id uuid;
  v_school_year_id uuid;
  v_category_id smallint;
  v_class_id smallint;
  v_fee_type_id smallint;
  v_student_id uuid;
  v_enrollment_id uuid;
  v_tariff_id uuid;
  v_total_usd numeric(14,2);
  v_args text;
  v_rejected boolean := false;
begin
  select pg_get_function_identity_arguments(p.oid)
    into v_args
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'register_school_payment';

  if v_args is null or position('p_currency text' in v_args) = 0 then
    raise exception 'TEST FAILED: le paramètre p_currency du RPC doit être TEXT (signature trouvée: %)', v_args;
  end if;

  if to_regprocedure('public.register_school_payment(uuid,uuid,uuid,numeric,character,text,text,text)') is not null then
    raise exception 'TEST FAILED: ancienne surcharge CHARACTER toujours présente';
  end if;

  if has_function_privilege('anon', 'public.register_school_payment(uuid,uuid,uuid,numeric,text,text,text,text)', 'EXECUTE')
     or has_function_privilege('authenticated', 'public.register_school_payment(uuid,uuid,uuid,numeric,text,text,text,text)', 'EXECUTE')
     or not has_function_privilege('service_role', 'public.register_school_payment(uuid,uuid,uuid,numeric,text,text,text,text)', 'EXECUTE') then
    raise exception 'TEST FAILED: droits EXECUTE incorrects sur le RPC de paiement';
  end if;

  insert into auth.users(id, email)
  values (v_auth_id, 'rpc-currency-test-' || v_auth_id::text || '@example.test');

  insert into public.profiles(auth_user_id, full_name, username, role, is_active)
  values (v_auth_id, 'Caissier test isolé', 'RPC_TEST_' || left(v_auth_id::text, 8), 'CAISSIER', true)
  returning id into v_cashier_id;

  select c.id, cl.id
    into v_category_id, v_class_id
  from public.categories c
  join public.classes cl on cl.category_id = c.id
  where c.code = 'MATERNELLE' and cl.code = 'MAT1'
  limit 1;

  select id into v_fee_type_id from public.fee_types order by id limit 1;

  if v_category_id is null or v_class_id is null or v_fee_type_id is null then
    raise exception 'TEST FAILED: références de test manquantes dans le schéma';
  end if;

  insert into public.school_years(label, start_date, end_date, opening_date, is_active)
  values ('TEST-RPC-' || left(v_auth_id::text, 8), date '2026-09-07', date '2027-07-02', date '2026-09-07', true)
  returning id into v_school_year_id;

  insert into public.students(full_name)
  values ('Élève test RPC isolé')
  returning id into v_student_id;

  insert into public.student_enrollments(student_id, school_year_id, category_id, class_id)
  values (v_student_id, v_school_year_id, v_category_id, v_class_id)
  returning id into v_enrollment_id;

  insert into public.fee_tariffs(school_year_id, fee_type_id, category_id, class_id, amount, currency, is_active)
  values (v_school_year_id, v_fee_type_id, v_category_id, v_class_id, 100, 'USD', true)
  returning id into v_tariff_id;

  -- Premier versement partiel en USD : 50 USD.
  perform * from public.register_school_payment(
    v_enrollment_id, v_tariff_id, v_cashier_id, 50, 'USD',
    'Test partiel USD', 'RPC-TEST-USD-' || left(v_auth_id::text, 8),
    'T-RPC-USD-' || left(v_auth_id::text, 8)
  );

  -- Complément en CDF au taux fixe : 115 000 CDF = 50 USD.
  perform * from public.register_school_payment(
    v_enrollment_id, v_tariff_id, v_cashier_id, 115000, 'CDF',
    'Test complément CDF', 'RPC-TEST-CDF-' || left(v_auth_id::text, 8),
    'T-RPC-CDF-' || left(v_auth_id::text, 8)
  );

  select sum(amount_usd) into v_total_usd
  from public.payments
  where enrollment_id = v_enrollment_id and status = 'VALIDE';

  if v_total_usd <> 100 then
    raise exception 'TEST FAILED: total USD après paiement partiel + complément = %, attendu 100', v_total_usd;
  end if;

  if not exists (
    select 1 from public.payments
    where enrollment_id = v_enrollment_id
      and currency = 'CDF' and amount_paid = 115000
      and amount_usd = 50 and exchange_rate = 2300
  ) then
    raise exception 'TEST FAILED: le complément CDF ou son équivalent USD/taux est incorrect';
  end if;

  -- Une tentative de dépasser le tarif doit être rejetée.
  begin
    perform * from public.register_school_payment(
      v_enrollment_id, v_tariff_id, v_cashier_id, 2300, 'CDF',
      'Test dépassement', 'RPC-TEST-OVER-' || left(v_auth_id::text, 8),
      'T-RPC-OVER-' || left(v_auth_id::text, 8)
    );
  exception when others then
    if position('Payment exceeds the remaining balance' in SQLERRM) > 0 then
      v_rejected := true;
    else
      raise;
    end if;
  end;

  if not v_rejected then
    raise exception 'TEST FAILED: le RPC a accepté un paiement supérieur au solde restant';
  end if;

  raise notice 'TEST RÉUSSI : USD + complément CDF à 2300 + refus du dépassement.';
end;
$$;

rollback;
