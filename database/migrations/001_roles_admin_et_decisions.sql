-- GESTION BÉATRICE
-- Migration 001 : rôle ADMINISTRATEUR et décisions de fin d'année
-- PRÉREQUIS : le schéma initial doit avoir été corrigé, installé et testé.
-- Cette migration n'a PAS été exécutée sur Supabase.
-- À appliquer uniquement après sauvegarde et validation du schéma de base.

begin;

-- 1. Ajouter le troisième rôle applicatif.
alter table public.profiles
    drop constraint if exists profiles_role_check;

alter table public.profiles
    add constraint profiles_role_check
    check (role in ('ADMINISTRATEUR', 'PREFET', 'CAISSIER'));

-- 2. Ajouter la décision de fin de cycle pour les élèves de 4e humanité.
alter table public.student_enrollments
    drop constraint if exists student_enrollments_decision_check;

alter table public.student_enrollments
    add constraint student_enrollments_decision_check
    check (decision in ('EN_ATTENTE', 'PROMU', 'REDOUBLE', 'SORTANT', 'FIN_CYCLE'));

-- 3. Recréer les règles de lecture des profils : chacun voit son profil,
-- l'administrateur voit tous les profils pour administrer les comptes,
-- le préfet peut consulter les profils dans le cadre de sa supervision.
drop policy if exists profiles_read_self_or_prefet on public.profiles;
create policy profiles_read_self_or_admin_or_prefet
on public.profiles for select to authenticated
using (
    auth_user_id = auth.uid()
    or public.current_app_role() in ('ADMINISTRATEUR', 'PREFET')
);

-- 4. Seul l'administrateur peut modifier les décisions de passage.
drop policy if exists enrollments_update_prefet_only on public.student_enrollments;
drop policy if exists enrollments_update_admin_decisions on public.student_enrollments;
create policy enrollments_update_admin_decisions
on public.student_enrollments for update to authenticated
using (public.current_app_role() = 'ADMINISTRATEUR')
with check (public.current_app_role() = 'ADMINISTRATEUR');

-- Le trigger empêche l'administrateur de modifier les autres informations
-- d'une inscription lorsqu'il valide la décision de fin d'année.
create or replace function public.guard_enrollment_decision_changes()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    actor_role text;
    target_class_code text;
    target_category_code text;
begin
    actor_role := public.current_app_role();

    if actor_role <> 'ADMINISTRATEUR' or public.current_profile_id() is null then
        raise exception 'Seul un administrateur actif peut valider les décisions de passage.';
    end if;

    if new.decision is not distinct from old.decision then
        raise exception 'Cette opération est réservée à la validation d'une décision de passage.';
    end if;

    if new.student_id is distinct from old.student_id
       or new.school_year_id is distinct from old.school_year_id
       or new.category_id is distinct from old.category_id
       or new.class_id is distinct from old.class_id
       or new.option_id is distinct from old.option_id
       or new.created_at is distinct from old.created_at
       or new.decision_validated_by is distinct from old.decision_validated_by
       or new.decision_validated_at is distinct from old.decision_validated_at then
        raise exception 'La validation ne peut modifier que la décision ; l'auteur et la date sont attribués automatiquement.';
    end if;

    if new.decision = 'EN_ATTENTE' then
        raise exception 'Une décision validée ne peut pas être remise à EN_ATTENTE par cette opération.';
    end if;

    if new.decision = 'FIN_CYCLE' then
        select cl.code, cat.code
          into target_class_code, target_category_code
        from public.classes cl
        join public.categories cat on cat.id = cl.category_id
        where cl.id = old.class_id;

        if target_category_code <> 'HUMANITE' or target_class_code <> 'SEC4' then
            raise exception 'La décision FIN_CYCLE est réservée aux élèves de quatrième humanité.';
        end if;
    end if;

    if old.decision <> 'EN_ATTENTE' then
        raise exception 'Une décision déjà validée ne peut pas être remplacée directement. Une procédure de correction tracée sera nécessaire.';
    end if;

    new.decision_validated_by := public.current_profile_id();
    new.decision_validated_at := now();
    return new;
end;
$$;

drop trigger if exists enrollments_guard_decision_changes on public.student_enrollments;
create trigger enrollments_guard_decision_changes
before update on public.student_enrollments
for each row
execute function public.guard_enrollment_decision_changes();

-- 5. L'administrateur et le préfet peuvent consulter tous les paiements.
drop policy if exists payments_read_own_cashier_or_prefet on public.payments;
create policy payments_read_by_role
on public.payments for select to authenticated
using (
    public.current_app_role() in ('ADMINISTRATEUR', 'PREFET')
    or (public.current_app_role() = 'CAISSIER'
        and cashier_id = public.current_profile_id())
);

-- 6. L'administrateur peut consulter les journaux d'activité.
drop policy if exists audit_read_prefet on public.audit_logs;
create policy audit_read_admin_or_prefet
on public.audit_logs for select to authenticated
using (public.current_app_role() in ('ADMINISTRATEUR', 'PREFET'));

commit;

-- À compléter dans une étape distincte :
-- * création sécurisée des comptes Auth et des profils ;
-- * gestion des permissions de modification des tarifs annuels ;
-- * RPC transactionnelle pour la validation en lot ou individuelle et
--   la création des inscriptions de l'année suivante ;
-- * journalisation des décisions de passage ;
-- * tests RLS avec un compte de chacun des trois rôles.
