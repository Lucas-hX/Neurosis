-- Local operator query, not an HTTP endpoint. Incomplete/dropped telemetry must
-- be reported alongside results. These are request clusters, not identities.
WITH events AS (
 SELECT r.created_at,r.cluster,r.request_id,r.status,event
 FROM research.requests r
 CROSS JOIN LATERAL jsonb_array_elements(r.events) event
 WHERE r.status BETWEEN 200 AND 299
), references_after_read AS (
 SELECT DISTINCT w.request_id,w.cluster,w.event->>'source_id' AS source_id,
                 w.event->>'target_id' AS target_id
 FROM events w
 WHERE w.event->>'type'='REFERENCE_CREATED'
 AND EXISTS (
   SELECT 1 FROM events r
   WHERE r.cluster=w.cluster AND r.created_at<w.created_at
     AND r.event->>'type'='ENGRAM_VIEW'
     AND r.event->>'engram_id'=w.event->>'target_id'
 )
)
SELECT count(DISTINCT request_id) AS writes_referencing_previously_read_memory,
       count(*) AS previously_read_references,
       count(DISTINCT cluster) AS observed_daily_clusters
FROM references_after_read;
