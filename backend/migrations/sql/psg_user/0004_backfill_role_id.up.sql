UPDATE psg_user
SET role_id = (
        SELECT id FROM psg_role
        WHERE code = CASE WHEN psg_user.is_system_user THEN 'SYSTEM' ELSE 'CREATOR' END::psg_role_type
    ),
    updated_at = now() AT TIME ZONE 'utc'
WHERE role_id IS NULL;
