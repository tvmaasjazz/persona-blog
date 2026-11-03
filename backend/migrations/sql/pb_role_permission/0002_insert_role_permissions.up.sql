-- ADMIN and CREATOR hold every permission; READER reads personas and blog posts
INSERT INTO pb_role_permission (role_id, permission_id, created_by_id, updated_by_id)
SELECT pb_role.id, pb_permission.id, (SELECT id FROM pb_user WHERE is_system_user), (SELECT id FROM pb_user WHERE is_system_user)
FROM pb_role
CROSS JOIN pb_permission
WHERE pb_role.code IN ('ADMIN', 'CREATOR')
    OR (pb_role.code = 'READER' AND pb_permission.code IN ('PERSONA_READ', 'BLOG_POST_READ'));
