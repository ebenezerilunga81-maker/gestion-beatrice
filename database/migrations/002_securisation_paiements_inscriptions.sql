-- GESTION BÉATRICE
-- Migration 002 : sécurisation des inscriptions, paiements, tickets et décisions
-- PRÉREQUIS : schema_initial.sql puis 001_roles_admin_et_decisions.sql
-- Cette migration n'a PAS été exécutée sur Supabase.
-- À tester sur une base de préproduction avant toute installation réelle.

begin;

-- ---------------------------------------------------------------------------
-- 1. Cohérence structurelle : une classe doit appartenir à la catégorie indiquée.
-- ---------------------------------------------------------------------------
do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'classes_id_category_id_key'
                 and conrelid = 'public.classes'::regclass) then
    alter table public.classes
      add constraint classes_id_category_id_key unique (id, category_id);
  end if;

  if not exists (select 1 from pg_constraint where conname = 'enrollments_class_category_fk'
                 and conrelid = 'public.student_enrollments'::regclass) then
    alter table public.student_enrollments
      add constraint enrollments_class_category_fk
      foreign key (class_id, category_id)
      references public.classes(id, category_id) on delete restrict;
  end if;

  if not exists (select 1 from pg_constraint where conname = 'fee_tariffs_class_category_fk'
                 and conrelid = 'public.fee_tariffs'::regclass) then
    alter table public.fee_tariffs
      add constraint fee_tariffs_class_category_fk
      foreign key (class_id, category_id)
      references public.classes(id, category_id) on delete restrict;
  end if;

  if not exists (select 1 from pg_constraint where conname = 'fee_templates_class_category_fk'
                 and conrelid = 'public.fee_tariff_templates'::regclass) then
    alter table public.fee_tariff_templates
      add constraint fee_templates_class_category_fk
      foreign key (class_id, category_id)
      references public.classes(id, category_id) on delete restrict;
  end if;
end $$;

-- Les options ne sont permises que pour les classes d'humanité.
-- L'option reste facultative tant que l'établissement n'a pas confirmé son caractère obligatoire.
create or replace function public.guard_humanity_option()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  category_code text;
begin
  if new.option_id is not null then
    select code into category_code
    from public.categories where id = new.category_id;

    if category_code is distinct from 'HUMANITE' then
      raise exception 'Une option ne peut être attribuée qu’à une classe des humanités.';
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists enrollment_humanity_option_guard on public.student_enrollments;
create trigger enrollment_humanity_option_guard
before insert or update of category_id, option_id on public.student_enrollments
for each row execute function public.guard_humanity_option();

drop trigger if exists tariff_humanity_option_guard on public.fee_tariffs;
create trigger tariff_humanity_option_guard
before insert or update of category_id, option_id on public.fee_tariffs
for each row execute function public.guard_humanity_option();

drop trigger if exists fee_template_humanity_option_guard on public.fee_tariff_templates;
create trigger fee_template_humanity_option_guard
before insert or update of category_id, option_id on public.fee_tariff_templates
for each row execute function public.guard_humanity_option();

-- ---------------------------------------------------------------------------
-- 2. Paiements : conditions métier et montant cumulé plafonné au tarif.
-- ---------------------------------------------------------------------------
create or replace function public.guard_payment_business_rules()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  enrollment_row public.student_enrollments%rowtype;
  tariff_row public.fee_tariffs%rowtype;
  already_paid numeric(14,2);
begin
  select * into enrollment_row
  from public.student_enrollments
  where id = new.enrollment_id;

  if not found then
    raise exception 'Inscription introuvable.';
  end if;

  select * into tariff_row
  from public.fee_tariffs
  where id = new.fee_tariff_id;

  if not found then
    raise exception 'Tarif introuvable.';
  end if;

  if tariff_row.school_year_id <> enrollment_row.school_year_id
     or tariff_row.category_id <> enrollment_row.category_id
     or (tariff_row.class_id is not null and tariff_row.class_id <> enrollment_row.class_id)
     or (tariff_row.option_id is not null and tariff_row.option_id is distinct from enrollment_row.option_id)
     or not tariff_row.is_active then
    raise exception 'Le tarif ne correspond pas à l’inscription de cet élève.';
  end if;

  if tg_op = 'INSERT' then
    if enrollment_row.decision = 'EN_ATTENTE' then
      raise exception 'Le paiement est bloqué : la décision de passage de l’élève est encore en attente.';
    end if;

    if not exists (
      select 1 from public.school_years y
      where y.id = enrollment_row.school_year_id
        and y.is_active = true
        and current_date >= y.opening_date
    ) then
      raise exception 'La caisse de cette année scolaire n’est pas encore ouverte.';
    end if;
  end if;

  excluded_payment_id := null;
  if tg_op = 'UPDATE' then
    excluded_payment_id := old.id;
  end if;

  select coalesce(sum(p.amount_paid), 0)
    into already_paid
  from public.payments p
  where p.fee_tariff_id = new.fee_tariff_id
    and p.enrollment_id = new.enrollment_id
    and (excluded_payment_id is null or p.id <> excluded_payment_id);

  if already_paid + new.amount_paid > tariff_row.amount then
    raise exception 'Ce versement dépasserait le montant total dû. Solde disponible : % %.',
      greatest(tariff_row.amount - already_paid, 0), tariff_row.currency;
  end if;

  return new;
end;
$$;

drop trigger if exists payments_business_rules on public.payments;
create trigger payments_business_rules
before insert or update on public.payments
for each row execute function public.guard_payment_business_rules();

-- Remplacer la garde existante : seuls les paiements propres du caissier peuvent être rectifiés ;
-- seul le préfet peut supprimer, via la fonction RPC contrôlée plus bas.
create or replace function public.guard_payment_changes()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  actor_role text;
  actor_id uuid;
begin
  actor_role := public.current_app_role();
  actor_id := public.current_profile_id();

  if tg_op = 'UPDATE' then
    if actor_role <> 'CAISSIER' or actor_id is null or actor_id <> old.cashier_id then
      raise exception 'Seul le caissier auteur peut rectifier son paiement.';
    end if;

    if new.id is distinct from old.id
       or new.enrollment_id is distinct from old.enrollment_id
       or new.fee_tariff_id is distinct from old.fee_tariff_id
       or new.cashier_id is distinct from old.cashier_id
       or new.payment_reference is distinct from old.payment_reference
       or new.created_at is distinct from old.created_at then
      raise exception 'La rectification ne peut changer que le montant, la date ou les notes.';
    end if;
    return new;
  elsif tg_op = 'DELETE' then
    if actor_role <> 'PREFET' or actor_id is null then
      raise exception 'Seul un préfet actif peut supprimer un paiement.';
    end if;
    if nullif(current_setting('app.audit_reason', true), '') is null then
      raise exception 'Un motif est obligatoire pour supprimer un paiement.';
    end if;
    return old;
  end if;
  return null;
end;
$$;

-- ---------------------------------------------------------------------------
-- 3. RPC sécurisées : création, rectification et suppression.
-- Les clients authentifiés ne reçoivent plus de droits DML directs sur ces tables.
-- ---------------------------------------------------------------------------
create sequence if not exists public.ticket_number_seq;

create or replace function public.register_school_payment(
  p_enrollment_id uuid,
  p_fee_tariff_id uuid,
  p_amount numeric,
  p_payment_reference text,
  p_notes text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  actor_id uuid;
  new_payment public.payments%rowtype;
  new_ticket public.tickets%rowtype;
begin
  actor_id := public.current_profile_id();

  if actor_id is null or public.current_app_role() <> 'CAISSIER' then
    raise exception 'Seul un caissier actif peut enregistrer un paiement.';
  end if;

  if p_amount is null or p_amount <= 0 then
    raise exception 'Le montant du paiement doit être positif.';
  end if;

  if nullif(trim(p_payment_reference), '') is null then
    raise exception 'La référence du paiement est obligatoire.';
  end if;

  insert into public.payments
    (enrollment_id, fee_tariff_id, cashier_id, amount_paid, payment_reference, notes)
  values
    (p_enrollment_id, p_fee_tariff_id, actor_id, p_amount, trim(p_payment_reference), p_notes)
  returning * into new_payment;

  insert into public.tickets(payment_id, ticket_number)
  values (
    new_payment.id,
    'GB-' || to_char(current_timestamp, 'YYYY') || '-' ||
    lpad(nextval('public.ticket_number_seq')::text, 7, '0')
  )
  returning * into new_ticket;

  return jsonb_build_object(
    'payment_id', new_payment.id,
    'ticket_id', new_ticket.id,
    'ticket_number', new_ticket.ticket_number,
    'amount_paid', new_payment.amount_paid,
    'payment_date', new_payment.payment_date
  );
end;
$$;

create or replace function public.correct_own_school_payment(
  p_payment_id uuid,
  p_amount numeric,
  p_payment_date timestamptz,
  p_notes text,
  p_reason text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  actor_id uuid;
  changed_payment public.payments%rowtype;
begin
  actor_id := public.current_profile_id();

  if actor_id is null or public.current_app_role() <> 'CAISSIER' then
    raise exception 'Seul un caissier actif peut rectifier un paiement.';
  end if;
  if nullif(trim(p_reason), '') is null then
    raise exception 'Le motif de rectification est obligatoire.';
  end if;
  if p_amount is null or p_amount <= 0 or p_payment_date is null then
    raise exception 'Montant ou date de paiement invalide.';
  end if;

  perform set_config('app.audit_reason', trim(p_reason), true);

  update public.payments
  set amount_paid = p_amount,
      payment_date = p_payment_date,
      notes = p_notes,
      updated_at = now()
  where id = p_payment_id
    and cashier_id = actor_id
  returning * into changed_payment;

  if not found then
    raise exception 'Paiement introuvable ou vous n’êtes pas son auteur.';
  end if;

  return jsonb_build_object('payment_id', changed_payment.id, 'amount_paid', changed_payment.amount_paid);
end;
$$;

create or replace function public.delete_school_payment(
  p_payment_id uuid,
  p_reason text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  actor_id uuid;
  deleted_id uuid;
begin
  actor_id := public.current_profile_id();

  if actor_id is null or public.current_app_role() <> 'PREFET' then
    raise exception 'Seul un préfet actif peut supprimer un paiement.';
  end if;
  if nullif(trim(p_reason), '') is null then
    raise exception 'Le motif de suppression est obligatoire.';
  end if;

  perform set_config('app.audit_reason', trim(p_reason), true);

  delete from public.payments
  where id = p_payment_id
  returning id into deleted_id;

  if not found then
    raise exception 'Paiement introuvable.';
  end if;

  return jsonb_build_object('deleted_payment_id', deleted_id, 'reason', trim(p_reason));
end;
$$;

-- ---------------------------------------------------------------------------
-- 4. Tickets : visibilité limitée au propriétaire, préfet et administrateur.
-- ---------------------------------------------------------------------------
drop policy if exists tickets_read_authenticated on public.tickets;
create policy tickets_read_by_role
on public.tickets for select to authenticated
using (
  public.current_app_role() in ('ADMINISTRATEUR', 'PREFET')
  or exists (
    select 1 from public.payments p
    where p.id = tickets.payment_id
      and p.cashier_id = public.current_profile_id()
      and public.current_app_role() = 'CAISSIER'
  )
);

drop policy if exists tickets_insert_cashier on public.tickets;

-- ---------------------------------------------------------------------------
-- 5. Décisions : une RPC applique la décision et prépare l'inscription suivante.
-- La date de proclamation est fixée au 2 juillet de l'année de fin scolaire.
-- ---------------------------------------------------------------------------
create or replace function public.apply_student_year_decision(
  p_enrollment_id uuid,
  p_decision text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  actor_id uuid;
  source_enrollment public.student_enrollments%rowtype;
  source_year public.school_years%rowtype;
  next_year public.school_years%rowtype;
  next_class_id smallint;
  next_category_id smallint;
  next_enrollment_id uuid;
  class_code text;
  category_code text;
begin
  actor_id := public.current_profile_id();

  if actor_id is null or public.current_app_role() <> 'ADMINISTRATEUR' then
    raise exception 'Seul l’administrateur actif peut valider les décisions de passage.';
  end if;

  if p_decision not in ('PROMU', 'REDOUBLE', 'SORTANT', 'FIN_CYCLE') then
    raise exception 'Décision non reconnue.';
  end if;

  select * into source_enrollment
  from public.student_enrollments
  where id = p_enrollment_id
  for update;

  if not found then
    raise exception 'Inscription introuvable.';
  end if;
  if source_enrollment.decision <> 'EN_ATTENTE' then
    raise exception 'La décision de cet élève a déjà été validée.';
  end if;

  select * into source_year
  from public.school_years
  where id = source_enrollment.school_year_id;

  if current_date < make_date(extract(year from source_year.end_date)::integer, 7, 2) then
    raise exception 'La validation des décisions est disponible à partir du 2 juillet suivant la fin de l’année scolaire.';
  end if;

  select cl.code, cat.code
    into class_code, category_code
  from public.classes cl
  join public.categories cat on cat.id = cl.category_id
  where cl.id = source_enrollment.class_id;

  if p_decision = 'FIN_CYCLE'
     and not (category_code = 'HUMANITE' and class_code = 'SEC4') then
    raise exception 'FIN_CYCLE est réservé aux élèves de quatrième humanité.';
  end if;

  if p_decision = 'PROMU'
     and category_code = 'HUMANITE' and class_code = 'SEC4' then
    raise exception 'Un élève de quatrième humanité doit recevoir FIN_CYCLE, SORTANT ou REDOUBLE.';
  end if;

  update public.student_enrollments
  set decision = p_decision
  where id = p_enrollment_id;

  if p_decision in ('PROMU', 'REDOUBLE') then
    select * into next_year
    from public.school_years
    where start_date > source_year.start_date
    order by start_date
    limit 1;

    if next_year.id is null then
      raise exception 'Créez d’abord l’année scolaire suivante et sa grille tarifaire.';
    end if;

    if p_decision = 'REDOUBLE' then
      next_class_id := source_enrollment.class_id;
      next_category_id := source_enrollment.category_id;
    else
      -- La progression traverse aussi les frontières entre catégories :
      -- MAT3 -> PRI1 et PRI8 -> SEC1.
      select cl.id, cl.category_id
        into next_class_id, next_category_id
      from public.classes cl
      join public.categories cat on cat.id = cl.category_id
      where (
        case cat.code
          when 'MATERNELLE' then 1
          when 'PRIMAIRE' then 2
          when 'HUMANITE' then 3
          else 99
        end,
        cl.level_order
      ) > (
        case category_code
          when 'MATERNELLE' then 1
          when 'PRIMAIRE' then 2
          when 'HUMANITE' then 3
          else 99
        end,
        (select level_order from public.classes where id = source_enrollment.class_id)
      )
      order by
        case cat.code
          when 'MATERNELLE' then 1
          when 'PRIMAIRE' then 2
          when 'HUMANITE' then 3
          else 99
        end,
        cl.level_order
      limit 1;

      if next_class_id is null then
        raise exception 'Aucune classe supérieure n’est définie pour cette classe.';
      end if;
    end if;

    insert into public.student_enrollments
      (student_id, school_year_id, category_id, class_id, option_id)
    values
      (source_enrollment.student_id, next_year.id, next_category_id,
       next_class_id, source_enrollment.option_id)
    returning id into next_enrollment_id;
  end if;

  insert into public.audit_logs
    (actor_profile_id, action, table_name, record_id, old_data, new_data, reason)
  values
    (actor_id, 'DECISION_' || p_decision, 'student_enrollments',
     source_enrollment.id::text, to_jsonb(source_enrollment),
     (select to_jsonb(e) from public.student_enrollments e where e.id = source_enrollment.id),
     'Validation de la décision annuelle');

  return jsonb_build_object(
    'enrollment_id', source_enrollment.id,
    'decision', p_decision,
    'next_enrollment_id', next_enrollment_id
  );
end;
$$;

-- ---------------------------------------------------------------------------
-- 6. Politiques RLS et privilèges : limiter les écritures aux RPC ou au serveur.
-- ---------------------------------------------------------------------------
drop policy if exists students_update_prefet_or_cashier on public.students;
create policy students_update_prefet_only
on public.students for update to authenticated
using (public.current_app_role() = 'PREFET')
with check (public.current_app_role() = 'PREFET');

drop policy if exists enrollments_insert_cashier_or_prefet on public.student_enrollments;
create policy enrollments_insert_prefet_only
on public.student_enrollments for insert to authenticated
with check (public.current_app_role() = 'PREFET');

drop policy if exists enrollments_update_admin_decisions on public.student_enrollments;
create policy enrollments_update_admin_decisions
on public.student_enrollments for update to authenticated
using (public.current_app_role() = 'ADMINISTRATEUR')
with check (public.current_app_role() = 'ADMINISTRATEUR');

drop policy if exists audit_read_admin_or_prefet on public.audit_logs;
create policy audit_read_admin_or_prefet
on public.audit_logs for select to authenticated
using (public.current_app_role() in ('ADMINISTRATEUR', 'PREFET'));

-- Retirer les DML directs sur les paiements, tickets, profils, tarifs et décisions.
revoke insert, update, delete on public.payments from authenticated;
revoke insert, update, delete on public.tickets from authenticated;
revoke insert, update, delete on public.profiles from authenticated;
revoke insert, update, delete on public.fee_tariffs from authenticated;
revoke insert, update, delete on public.fee_tariff_templates from authenticated;
revoke update on public.student_enrollments from authenticated;

-- Les inscriptions initiales sont créées par le préfet. La validation des décisions passe par RPC.
grant insert on public.student_enrollments to authenticated;

-- Les fonctions RPC sont explicitement accessibles aux utilisateurs authentifiés.
revoke all on function public.register_school_payment(uuid, uuid, numeric, text, text) from public;
revoke all on function public.correct_own_school_payment(uuid, numeric, timestamptz, text, text) from public;
revoke all on function public.delete_school_payment(uuid, text) from public;
revoke all on function public.apply_student_year_decision(uuid, text) from public;

grant execute on function public.register_school_payment(uuid, uuid, numeric, text, text) to authenticated;
grant execute on function public.correct_own_school_payment(uuid, numeric, timestamptz, text, text) to authenticated;
grant execute on function public.delete_school_payment(uuid, text) to authenticated;
grant execute on function public.apply_student_year_decision(uuid, text) to authenticated;

-- Les numéros de tickets sont générés uniquement par la fonction d'enregistrement.
revoke all on sequence public.ticket_number_seq from public, anon, authenticated;

commit;

-- RESTE À FAIRE AVANT PRODUCTION :
-- 1) Ajouter les fonctions serveur sécurisées de création/désactivation des comptes Auth + profils.
-- 2) Définir les procédures d'administration des années scolaires, jours fériés et tarifs.
-- 3) Ajouter les écrans/API d'archives en lecture seule et les tests de permissions.
-- 4) Définir un identifiant secondaire pour distinguer les élèves homonymes.
-- 5) Tester concurrence, paiements simultanés, RLS et RPC avec trois comptes de test.
-- 6) Vérifier la disponibilité PostgreSQL (Supabase) et tester toute la migration sur une copie.
