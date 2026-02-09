-- Analytics view for constraint effectiveness
CREATE VIEW cover_letter_effectiveness AS
SELECT 
    cover_letter_constraint_type,
    cover_letter_strategy_used,
    COUNT(*) as total,
    SUM(CASE WHEN outcome IN ('phone_screen', 'technical', 'final', 'offer_accepted') THEN 1 ELSE 0 END) as progressed,
    ROUND(100.0 * SUM(CASE WHEN outcome IN ('phone_screen', 'technical', 'final', 'offer_accepted') THEN 1 ELSE 0 END) / COUNT(*), 1) as progress_rate
FROM applications
WHERE applied = 1
GROUP BY cover_letter_constraint_type, cover_letter_strategy_used;

INSERT INTO schema_version (version) VALUES (3);