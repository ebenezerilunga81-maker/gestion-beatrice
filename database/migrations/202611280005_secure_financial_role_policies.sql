-- Renforce les droits de lecture financière et retire les écritures directes
-- sur les anciennes fiches nominatives. Les opérations serveur continuent
-- d'utiliser service_role ; aucune donnée historique n'est supprimée.
begin;

drop policy if exists payments_read_own_or_supervision on public.payments;
create policy payments_read_own_or_supervision
on public.payments
for select
to authenticated
using (
    (select public.current_app_role()) = any (
        array['ADMINISTRATEUR', 'PREFET', 'PROMOTEUR']::text[]
    )
    or (
        (select public.current_app_role()) = 'CAISSIER'
        and cashier_id = (select public.current_profile_id())
    )
);

drop policy if exists tickets_read_own_or_supervision on public.tickets;
create policy tickets_read_own_or_supervision
on public.tickets
for select
to authenticated
using (
    exists (
        select 1
        from public.payments p
        where p.id = tickets.payment_id
          and (
              (select public.current_app_role()) = any (
                  array['ADMINISTRATEUR', 'PREFET', 'PROMOTEUR']::text[]
              )
              or (
                  (select public.current_app_role()) = 'CAISSIER'
                  and p.cashier_id = (select public.current_profile_id())
              )
          )
    )
);

-- Les fiches élèves ne sont plus créées ni modifiées directement par les
-- profils applicatifs. Les anciennes lignes restent conservées et consultables
-- via les endpoints historiques tant que la migration fonctionnelle n'est pas achevée.
-- Noms réellement utilisés par le schéma initial.
drop policy if exists "students_insert_cashier" on public.students;
drop policy if exists "students_update_prefet_or_cashier" on public.students;
-- Compatibilité avec d'éventuels anciens noms de politiques.
drop policy if exists students_insert_staff on public.students;
drop policy if exists students_update_admin_prefet on public.students;
revoke insert, update, delete on table public.students from anon, authenticated, public;

commit;
