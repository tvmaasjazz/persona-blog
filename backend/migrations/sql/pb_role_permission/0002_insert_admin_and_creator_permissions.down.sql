DELETE FROM pb_role_permission
USING pb_role
WHERE pb_role_permission.role_id = pb_role.id
    AND pb_role.code IN ('ADMIN', 'CREATOR');
