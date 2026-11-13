DELETE FROM psg_role_permission
USING psg_role
WHERE psg_role_permission.role_id = psg_role.id
    AND psg_role.code IN ('ADMIN', 'CREATOR', 'READER');
