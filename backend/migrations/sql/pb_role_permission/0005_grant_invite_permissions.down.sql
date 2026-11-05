DELETE FROM pb_role_permission
USING pb_role, pb_permission
WHERE pb_role_permission.role_id = pb_role.id
    AND pb_role_permission.permission_id = pb_permission.id
    AND pb_role.code = 'ADMIN'
    AND pb_permission.code IN ('INVITE_READ', 'INVITE_WRITE');
