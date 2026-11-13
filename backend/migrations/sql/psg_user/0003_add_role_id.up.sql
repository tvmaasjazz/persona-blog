ALTER TABLE psg_user ADD COLUMN role_id BIGINT REFERENCES psg_role (id);
