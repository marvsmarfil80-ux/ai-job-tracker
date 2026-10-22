INSERT INTO sources (name, badge, max_runs_per_day) VALUES
    ('weworkremotely', 'We Work Remotely', NULL),
    ('remoteok', 'RemoteOK', NULL),
    ('remotive', 'Remotive', 4)
ON CONFLICT (name) DO NOTHING;

INSERT INTO settings (key, value) VALUES
    ('daily_score_cap', '300'::jsonb),
    ('apply_threshold', '70'::jsonb),
    ('maybe_threshold', '40'::jsonb),
    ('min_score', '40'::jsonb)
ON CONFLICT (key) DO NOTHING;

INSERT INTO profile DEFAULT VALUES
ON CONFLICT DO NOTHING;

INSERT INTO allowed_senders (sender, kind) VALUES
    ('jobs-noreply@linkedin.com', 'job_alert')
ON CONFLICT (sender, kind) DO NOTHING;