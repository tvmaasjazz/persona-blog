-- Clears the backfilled roles so the seeded psg_role rows can be deleted.
UPDATE psg_user
SET role_id = NULL,
    updated_at = now() AT TIME ZONE 'utc';
