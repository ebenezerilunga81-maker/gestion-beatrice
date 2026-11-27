alter table public.payments
  add column if not exists amount_usd numeric(14,2),
  add column if not exists exchange_rate numeric(14,4);

update public.payments
set amount_usd = amount_paid,
    exchange_rate = 1
where upper(btrim(currency)) = 'USD'
  and amount_usd is null;

create or replace function public.register_school_payment(
  p_enrollment_id uuid,
  p_fee_tariff_id uuid,
  p_cashier_id uuid,
  p_amount_paid numeric,
  p_currency character,
  p_notes text,
  p_payment_reference text,
  p_ticket_number text
)
returns table(payment_id uuid, ticket_id uuid)
language plpgsql
set search_path to 'public', 'pg_temp'
as $function$
declare
  v_payment_id uuid;
  v_ticket_id uuid;
  v_currency text;
  v_amount_usd numeric(14,2);
  v_exchange_rate numeric(14,4);
  v_due_usd numeric(14,2);
  v_already_paid numeric(14,2);
  v_enrollment public.student_enrollments%rowtype;
  v_tariff public.fee_tariffs%rowtype;
  v_cashier public.profiles%rowtype;
begin
  v_currency := upper(btrim(p_currency));

  if v_currency = 'USD' then
    v_exchange_rate := 1;
    v_amount_usd := round(p_amount_paid, 2);
  elsif v_currency = 'CDF' then
    v_exchange_rate := 2300;
    v_amount_usd := round(p_amount_paid / 2300, 2);
  else
    raise exception 'Unsupported payment currency: %', p_currency;
  end if;

  if p_amount_paid is null or p_amount_paid <= 0 or v_amount_usd <= 0 then
    raise exception 'Payment amount must be positive';
  end if;
  if nullif(btrim(p_payment_reference), '') is null
     or nullif(btrim(p_ticket_number), '') is null then
    raise exception 'Payment reference and ticket number are required';
  end if;

  select * into v_cashier
  from public.profiles
  where id = p_cashier_id and role = 'CAISSIER' and is_active = true;
  if not found then
    raise exception 'An active cashier account is required';
  end if;

  select * into v_enrollment
  from public.student_enrollments
  where id = p_enrollment_id
  for update;
  if not found then
    raise exception 'Student enrollment not found';
  end if;

  select * into v_tariff
  from public.fee_tariffs
  where id = p_fee_tariff_id and is_active = true;
  if not found
     or v_tariff.school_year_id <> v_enrollment.school_year_id
     or v_tariff.category_id <> v_enrollment.category_id
     or v_tariff.class_id <> v_enrollment.class_id then
    raise exception 'Fee tariff does not apply to this enrollment';
  end if;

  perform pg_advisory_xact_lock(hashtextextended(
    p_enrollment_id::text || ':' || p_fee_tariff_id::text, 0
  ));

  if upper(btrim(v_tariff.currency)) = 'USD' then
    v_due_usd := round(v_tariff.amount, 2);
  elsif upper(btrim(v_tariff.currency)) = 'CDF' then
    v_due_usd := round(v_tariff.amount / 2300, 2);
  else
    raise exception 'Unsupported tariff currency: %', v_tariff.currency;
  end if;

  select coalesce(sum(
    case
      when p.amount_usd is not null then p.amount_usd
      when upper(btrim(p.currency)) = 'USD' then p.amount_paid
      else 0
    end
  ), 0)
  into v_already_paid
  from public.payments p
  where p.enrollment_id = p_enrollment_id
    and p.fee_tariff_id = p_fee_tariff_id
    and p.status = 'VALIDE';

  if v_already_paid + v_amount_usd > v_due_usd then
    raise exception 'Payment exceeds the remaining balance of % USD',
      greatest(v_due_usd - v_already_paid, 0);
  end if;

  insert into public.payments(
    enrollment_id, fee_tariff_id, cashier_id, amount_paid, currency,
    amount_usd, exchange_rate, payment_reference, notes, status
  ) values (
    p_enrollment_id, p_fee_tariff_id, p_cashier_id, p_amount_paid, v_currency,
    v_amount_usd, v_exchange_rate, btrim(p_payment_reference), p_notes, 'VALIDE'
  ) returning id into v_payment_id;

  insert into public.tickets(payment_id, ticket_number)
  values (v_payment_id, btrim(p_ticket_number))
  returning id into v_ticket_id;

  payment_id := v_payment_id;
  ticket_id := v_ticket_id;
  return next;
end;
$function$;

revoke all on function public.register_school_payment(uuid, uuid, uuid, numeric, character, text, text, text)
  from public, anon, authenticated;
grant execute on function public.register_school_payment(uuid, uuid, uuid, numeric, character, text, text, text)
  to service_role;
