UPDATE pb_user
SET role_id = (
        SELECT id FROM pb_role
        WHERE code = CASE WHEN pb_user.is_system_user THEN 'SYSTEM' ELSE 'CREATOR' END::pb_role_type
    ),
    updated_at = now() AT TIME ZONE 'utc'
WHERE role_id IS NULL;
