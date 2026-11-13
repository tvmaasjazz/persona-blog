INSERT INTO psg_permission (code, created_by_id, updated_by_id)
SELECT 'USER_WRITE', (SELECT id FROM psg_user WHERE is_system_user), (SELECT id FROM psg_user WHERE is_system_user);
