INSERT INTO pb_role (code, created_by_id, updated_by_id)
SELECT role_code, (SELECT id FROM pb_user WHERE is_system_user), (SELECT id FROM pb_user WHERE is_system_user)
FROM unnest(ARRAY['ADMIN', 'CREATOR', 'READER', 'SYSTEM']::pb_role_type[]) AS role_code;
