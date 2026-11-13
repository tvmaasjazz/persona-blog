INSERT INTO psg_permission (code, created_by_id, updated_by_id)
SELECT permission_code, (SELECT id FROM psg_user WHERE is_system_user), (SELECT id FROM psg_user WHERE is_system_user)
FROM unnest(
    ARRAY['USER_READ', 'CREDIT_READ', 'CREDIT_WRITE']::psg_permission_type[]
) AS permission_code;
