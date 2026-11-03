INSERT INTO pb_permission (code, created_by_id, updated_by_id)
SELECT permission_code, (SELECT id FROM pb_user WHERE is_system_user), (SELECT id FROM pb_user WHERE is_system_user)
FROM unnest(
    ARRAY[
        'PERSONA_READ', 'PERSONA_WRITE', 'BLOG_POST_READ', 'BLOG_POST_WRITE',
        'GENERATE_TEXT_RUN_READ', 'GENERATE_TEXT_RUN_WRITE'
    ]::pb_permission_type[]
) AS permission_code;
