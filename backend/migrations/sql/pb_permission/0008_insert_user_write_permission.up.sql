INSERT INTO pb_permission (code, created_by_id, updated_by_id)
SELECT 'USER_WRITE', (SELECT id FROM pb_user WHERE is_system_user), (SELECT id FROM pb_user WHERE is_system_user);
