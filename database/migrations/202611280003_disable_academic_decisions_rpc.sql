-- Désactive l'ancienne RPC de décisions académiques sans supprimer les données historiques.
begin;
revoke all on function public.validate_student_decision(uuid, text, uuid) from public, anon, authenticated;
commit;
