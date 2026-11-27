alter table public.payments
  add column if not exists amount_usd numeric(14,2),
  add column if not exists exchange_rate numeric(14,4);

-- Existing USD payments are exact and can be backfilled without changing their value.
-- Historical CDF payments are deliberately left NULL: their original exchange rate is unknown.
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

  if p_amount_paid <= 0 or v_amount_usd <= 0 then
    raise exception 'Payment amount must be positive';
  end if;

  insert into public.payments(
    enrollment_id, fee_tariff_id, cashier_id, amount_paid, currency,
    amount_usd, exchange_rate, payment_reference, notes, status
  ) values (
    p_enrollment_id, p_fee_tariff_id, p_cashier_id, p_amount_paid, v_currency,
    v_amount_usd, v_exchange_rate, p_payment_reference, p_notes, 'VALIDE'
  ) returning id into v_payment_id;

  insert into public.tickets(payment_id, ticket_number)
  values (v_payment_id, p_ticket_number)
  returning id into v_ticket_id;

  payment_id := v_payment_id;
  ticket_id := v_ticket_id;
  return next;
end;
$function$;
