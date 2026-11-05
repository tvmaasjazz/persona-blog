INSERT INTO pb_permission (code, created_by_id, updated_by_id)
SELECT permission_code, (SELECT id FROM pb_user WHERE is_system_user), (SELECT id FROM pb_user WHERE is_system_user)
FROM unnest(
    ARRAY['INVITE_READ', 'INVITE_WRITE']::pb_permission_type[]
) AS permission_code;
