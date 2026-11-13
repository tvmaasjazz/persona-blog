DELETE FROM psg_role_permission
USING psg_role, psg_permission
WHERE psg_role_permission.role_id = psg_role.id
    AND psg_role_permission.permission_id = psg_permission.id
    AND psg_role.code = 'ADMIN'
    AND psg_permission.code = 'USER_WRITE';
