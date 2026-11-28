-- Révocation complémentaire pour empêcher tout appel de l'ancienne RPC via service_role.
revoke all on function public.validate_student_decision(uuid, text, uuid) from service_role;
