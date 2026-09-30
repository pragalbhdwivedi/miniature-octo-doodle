BEGIN;
DO $$ BEGIN
 IF (SELECT version FROM controller.schema_version) <> 1 THEN RAISE EXCEPTION 'Expected schema 1'; END IF;
END $$;
ALTER TABLE controller.schema_version DROP CONSTRAINT schema_version_version_check;
UPDATE controller.schema_version SET version=2;
ALTER TABLE controller.schema_version ADD CHECK (version=2);
ALTER TABLE controller.runs DROP CONSTRAINT runs_state_check;
ALTER TABLE controller.runs ADD CHECK (state IN ('dispatching','review_required','failed','uncertain','published'));
CREATE TABLE controller.pipelines (
 run_id text PRIMARY KEY REFERENCES controller.runs(run_id),
 spec jsonb NOT NULL, approval_sha256 text NOT NULL,
 ceiling bigint NOT NULL CHECK (ceiling BETWEEN 0 AND 1000000),
 debit bigint NOT NULL CHECK (debit >= 0 AND debit <= ceiling),
 state text NOT NULL CHECK (state IN ('reviewing','repairing','re_reviewing','approved','rejected','publishing','published','uncertain')),
 evidence jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE UNIQUE INDEX one_active_pipeline ON controller.pipelines ((1))
 WHERE state IN ('reviewing','repairing','re_reviewing','publishing','uncertain');
CREATE TABLE controller.pipeline_debits (
 run_id text NOT NULL REFERENCES controller.pipelines(run_id),
 stage text NOT NULL CHECK (stage IN ('review0','repair','review1')),
 debit bigint NOT NULL CHECK (debit > 0), body_sha256 text NOT NULL,
 PRIMARY KEY(run_id,stage)
);
CREATE FUNCTION controller.pipeline_begin(id text, spec jsonb, digest text, spent bigint) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,controller AS $$
DECLARE root controller.runs; row controller.pipelines;
BEGIN
 PERFORM pg_advisory_xact_lock(742007);
 SELECT * INTO STRICT root FROM controller.runs WHERE run_id=id FOR UPDATE;
 IF root.state <> 'review_required' OR root.result->>'artifact_sha256' <> spec->>'artifact_sha256'
    OR root.source_sha <> spec->>'source_sha' OR EXISTS(SELECT 1 FROM controller.runs WHERE state IN ('dispatching','uncertain')) THEN
   RAISE EXCEPTION 'Root not eligible'; END IF;
 INSERT INTO controller.pipelines(run_id,spec,approval_sha256,ceiling,debit,state)
 VALUES(id,spec,digest,(spec->>'budget_micro_usd')::bigint,spent,'reviewing') RETURNING * INTO row;
 INSERT INTO controller.events(run_id,state,detail) VALUES(id,'pipeline:reviewing',jsonb_build_object('approval_sha256',digest));
 RETURN to_jsonb(row);
END $$;
CREATE FUNCTION controller.pipeline_reserve(id text, stage text, amount bigint, body_hash text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,controller AS $$
DECLARE row controller.pipelines;
BEGIN
 SELECT * INTO STRICT row FROM controller.pipelines WHERE run_id=id FOR UPDATE;
 IF NOT ((row.state='reviewing' AND stage='review0') OR (row.state='repairing' AND stage='repair') OR
         (row.state='re_reviewing' AND stage='review1')) OR amount<=0 OR row.debit+amount>row.ceiling THEN
   RAISE EXCEPTION 'Stage or aggregate budget denied'; END IF;
 INSERT INTO controller.pipeline_debits VALUES(id,stage,amount,body_hash);
 UPDATE controller.pipelines SET debit=debit+amount WHERE run_id=id RETURNING * INTO row;
 INSERT INTO controller.events(run_id,state,detail) VALUES(id,'pipeline:reserved',jsonb_build_object('stage',stage,'debit',amount,'body_sha256',body_hash));
 RETURN to_jsonb(row);
END $$;
CREATE FUNCTION controller.pipeline_step(id text, expected text, next_state text, data jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,controller AS $$
DECLARE row controller.pipelines;
BEGIN
 PERFORM pg_advisory_xact_lock(742007);
 SELECT * INTO STRICT row FROM controller.pipelines WHERE run_id=id FOR UPDATE;
 IF row.state<>expected OR NOT (
   (expected='reviewing' AND next_state IN ('repairing','approved','rejected','uncertain')) OR
   (expected='repairing' AND next_state IN ('re_reviewing','uncertain')) OR
   (expected='re_reviewing' AND next_state IN ('approved','rejected','uncertain')) OR
   (expected='approved' AND next_state='publishing') OR
   (expected='publishing' AND next_state IN ('published','uncertain'))) THEN RAISE EXCEPTION 'Illegal pipeline transition'; END IF;
 IF next_state='publishing' AND EXISTS(SELECT 1 FROM controller.runs WHERE state IN ('dispatching','uncertain')) THEN
   RAISE EXCEPTION 'Worker active'; END IF;
 UPDATE controller.pipelines SET state=next_state,evidence=data WHERE run_id=id RETURNING * INTO row;
 INSERT INTO controller.events(run_id,state,detail) VALUES(id,'pipeline:'||next_state,data);
 IF next_state='published' THEN UPDATE controller.runs SET state='published',updated_at=clock_timestamp() WHERE run_id=id; END IF;
 RETURN to_jsonb(row);
END $$;
-- Serialize worker admission with pipeline admission without granting new table writes.
CREATE OR REPLACE FUNCTION controller.claim(req jsonb, digest text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,controller AS $$
DECLARE row controller.runs;
BEGIN
 PERFORM pg_advisory_xact_lock(742007);
 IF EXISTS(SELECT 1 FROM controller.pipelines WHERE state IN ('reviewing','repairing','re_reviewing','publishing','uncertain')) THEN
   RAISE EXCEPTION 'Pipeline active or ambiguous'; END IF;
 INSERT INTO controller.runs(run_id,project,task_id,source_sha,request_sha256,request,state)
 VALUES(req->>'run_id',req->'plan'->>'project',req->'plan'->>'task_id',req->'plan'->>'source_sha',digest,req,'dispatching') RETURNING * INTO row;
 INSERT INTO controller.events(run_id,state,detail) VALUES(row.run_id,row.state,jsonb_build_object('request_sha256',digest));
 RETURN to_jsonb(row);
END $$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA controller FROM PUBLIC;
GRANT SELECT ON controller.pipelines,controller.pipeline_debits TO gatewayai_controller;
GRANT EXECUTE ON FUNCTION controller.pipeline_begin(text,jsonb,text,bigint),
 controller.pipeline_reserve(text,text,bigint,text),controller.pipeline_step(text,text,text,jsonb) TO gatewayai_controller;
COMMIT;
