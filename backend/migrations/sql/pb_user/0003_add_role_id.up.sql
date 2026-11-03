ALTER TABLE pb_user ADD COLUMN role_id BIGINT REFERENCES pb_role (id);
