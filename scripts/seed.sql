INSERT INTO sources (name, badge, max_runs_per_day) VALUES
    ('weworkremotely', 'We Work Remotely', NULL),
    ('remoteok', 'RemoteOK', NULL),
    ('remotive', 'Remotive', 4)
ON CONFLICT (name) DO NOTHING;

INSERT INTO settings (key, value) VALUES
    ('daily_score_cap', '150'::jsonb),
    ('apply_threshold', '70'::jsonb),
    ('maybe_threshold', '40'::jsonb),
    ('min_score', '40'::jsonb)
ON CONFLICT (key) DO NOTHING;

INSERT INTO settings (key, value) VALUES
    ('scheduler_enabled', 'false'::jsonb),
    ('hunt_interval_hours', '6'::jsonb),
    ('score_interval_minutes', '30'::jsonb),
    ('score_batch_limit', '10'::jsonb)
ON CONFLICT (key) DO NOTHING;

INSERT INTO settings (key, value) VALUES
    ('title_exclude_regex', to_jsonb('senior|director|head of|principal|vice president|manager|architect|(?<![a-z])staff(?![a-z])|recruiter|sales|nurse|physician|(?<!non-)(?<!non )(?<!non)voice|call center|(?<![a-z])lead(?![a-z])'::text)),
    ('title_include_keywords', '["assistant", "data entry", "support", "admin", "junior", "entry", "automation"]'::jsonb)
ON CONFLICT (key) DO NOTHING;

INSERT INTO profile DEFAULT VALUES
ON CONFLICT DO NOTHING;

INSERT INTO allowed_senders (sender, kind) VALUES
    ('jobs-noreply@linkedin.com', 'job_alert')
ON CONFLICT (sender, kind) DO NOTHING;