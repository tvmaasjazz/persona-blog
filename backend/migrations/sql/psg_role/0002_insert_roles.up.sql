INSERT INTO psg_role (code, created_by_id, updated_by_id)
SELECT role_code, (SELECT id FROM psg_user WHERE is_system_user), (SELECT id FROM psg_user WHERE is_system_user)
FROM unnest(ARRAY['ADMIN', 'CREATOR', 'READER', 'SYSTEM']::psg_role_type[]) AS role_code;
