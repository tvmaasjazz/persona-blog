-- Clears the backfilled roles so the seeded pb_role rows can be deleted.
UPDATE pb_user
SET role_id = NULL,
    updated_at = now() AT TIME ZONE 'utc';
