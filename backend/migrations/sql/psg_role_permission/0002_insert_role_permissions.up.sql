-- ADMIN and CREATOR hold every permission; READER reads personas and blog posts
INSERT INTO psg_role_permission (role_id, permission_id, created_by_id, updated_by_id)
SELECT psg_role.id, psg_permission.id, (SELECT id FROM psg_user WHERE is_system_user), (SELECT id FROM psg_user WHERE is_system_user)
FROM psg_role
CROSS JOIN psg_permission
WHERE psg_role.code IN ('ADMIN', 'CREATOR')
    OR (psg_role.code = 'READER' AND psg_permission.code IN ('PERSONA_READ', 'BLOG_POST_READ'));
