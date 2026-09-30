-- Operator-only approval state. Telegram transport has no direct database access.
BEGIN;
DO $$ BEGIN
 IF (SELECT version FROM controller.schema_version) <> 2 THEN RAISE EXCEPTION 'Expected schema 2'; END IF;
END $$;
ALTER TABLE controller.schema_version DROP CONSTRAINT schema_version_version_check;
UPDATE controller.schema_version SET version=3;
ALTER TABLE controller.schema_version ADD CHECK (version=3);
CREATE TABLE controller.approvals (
 approval_id text PRIMARY KEY CHECK (approval_id ~ '^[a-f0-9]{32}$'),
 run_id text NOT NULL REFERENCES controller.runs(run_id),
 action text NOT NULL CHECK (action='publish_draft'),
 payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[a-f0-9]{64}$'),
 state text NOT NULL CHECK (state IN ('pending','approved','rejected','consumed')),
 telegram_user_id bigint NOT NULL CHECK (telegram_user_id>0),
 telegram_chat_id bigint NOT NULL CHECK (telegram_chat_id>0),
 telegram_update_id bigint UNIQUE,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 expires_at timestamptz NOT NULL,
 decided_at timestamptz,
 UNIQUE(run_id,action)
);
CREATE FUNCTION controller.approval_request(id text, run text, digest text,
                                            telegram_user bigint, telegram_chat bigint,
                                            lifetime_seconds integer) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,controller AS $$
DECLARE row controller.approvals;
BEGIN
 PERFORM pg_advisory_xact_lock(742007);
 IF id !~ '^[a-f0-9]{32}$' OR digest !~ '^[a-f0-9]{64}$'
    OR telegram_user<=0 OR telegram_chat<=0 OR lifetime_seconds NOT BETWEEN 60 AND 3600
    OR NOT EXISTS(SELECT 1 FROM controller.pipelines WHERE run_id=run AND state='approved') THEN
  RAISE EXCEPTION 'Approval request denied'; END IF;
 INSERT INTO controller.approvals(approval_id,run_id,action,payload_sha256,state,
                                  telegram_user_id,telegram_chat_id,expires_at)
 VALUES(id,run,'publish_draft',digest,'pending',telegram_user,telegram_chat,
        clock_timestamp()+make_interval(secs=>lifetime_seconds)) RETURNING * INTO row;
 INSERT INTO controller.events(run_id,state,detail)
 VALUES(run,'approval:pending',jsonb_build_object('approval_id',id,'payload_sha256',digest));
 RETURN to_jsonb(row);
END $$;
CREATE FUNCTION controller.approval_decide(id text, digest text, decision text,
                                           telegram_user bigint, telegram_chat bigint,
                                           telegram_update bigint) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,controller AS $$
DECLARE row controller.approvals;
BEGIN
 SELECT * INTO STRICT row FROM controller.approvals WHERE approval_id=id FOR UPDATE;
 IF row.state<>'pending' OR row.expires_at<=clock_timestamp() OR row.payload_sha256<>digest
    OR row.telegram_user_id<>telegram_user OR row.telegram_chat_id<>telegram_chat
    OR telegram_update<0 OR decision NOT IN ('approved','rejected') THEN
  RAISE EXCEPTION 'Approval decision denied'; END IF;
 UPDATE controller.approvals SET state=decision,telegram_update_id=telegram_update,
       decided_at=clock_timestamp() WHERE approval_id=id RETURNING * INTO row;
 INSERT INTO controller.events(run_id,state,detail)
 VALUES(row.run_id,'approval:'||decision,
        jsonb_build_object('approval_id',id,'payload_sha256',digest,'telegram_update_id',telegram_update));
 RETURN to_jsonb(row);
END $$;
CREATE FUNCTION controller.approval_consume(id text, run text, digest text, receipt jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,controller AS $$
DECLARE row controller.approvals;
BEGIN
 PERFORM pg_advisory_xact_lock(742007);
 SELECT * INTO STRICT row FROM controller.approvals WHERE approval_id=id FOR UPDATE;
 IF row.run_id<>run OR row.action<>'publish_draft' OR row.payload_sha256<>digest
    OR row.state<>'approved' OR row.expires_at<=clock_timestamp()
    OR NOT EXISTS(SELECT 1 FROM controller.pipelines WHERE run_id=run AND state='approved') THEN
  RAISE EXCEPTION 'Approval consumption denied'; END IF;
 UPDATE controller.approvals SET state='consumed' WHERE approval_id=id RETURNING * INTO row;
 UPDATE controller.pipelines SET state='publishing',evidence=receipt WHERE run_id=run;
 INSERT INTO controller.events(run_id,state,detail)
 VALUES(run,'approval:consumed',jsonb_build_object('approval_id',id,'payload_sha256',digest));
 INSERT INTO controller.events(run_id,state,detail) VALUES(run,'pipeline:publishing',receipt);
 RETURN to_jsonb(row);
END $$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA controller FROM PUBLIC;
GRANT SELECT ON controller.approvals TO gatewayai_controller;
GRANT EXECUTE ON FUNCTION controller.approval_request(text,text,text,bigint,bigint,integer),
 controller.approval_decide(text,text,text,bigint,bigint,bigint),
 controller.approval_consume(text,text,text,jsonb) TO gatewayai_controller;
COMMIT;
