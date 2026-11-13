-- Only ADMIN can set a user's role or suspend them
INSERT INTO psg_role_permission (role_id, permission_id, created_by_id, updated_by_id)
SELECT psg_role.id, psg_permission.id, (SELECT id FROM psg_user WHERE is_system_user), (SELECT id FROM psg_user WHERE is_system_user)
FROM psg_role
CROSS JOIN psg_permission
WHERE psg_role.code = 'ADMIN'
    AND psg_permission.code = 'USER_WRITE';
