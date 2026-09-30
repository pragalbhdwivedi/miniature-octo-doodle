-- Apply once, in a dedicated controller database, as its NOLOGIN owner.
BEGIN;
CREATE SCHEMA controller;
REVOKE ALL ON SCHEMA controller FROM PUBLIC;
CREATE TABLE controller.schema_version (version integer PRIMARY KEY CHECK (version = 1));
INSERT INTO controller.schema_version VALUES (1);
CREATE TABLE controller.runs (
  run_id text PRIMARY KEY CHECK (run_id ~ '^[a-f0-9]{32}$'),
  project text NOT NULL,
  task_id text NOT NULL,
  source_sha text NOT NULL CHECK (source_sha ~ '^[a-f0-9]{40}$'),
  request_sha256 text NOT NULL UNIQUE CHECK (request_sha256 ~ '^[a-f0-9]{64}$'),
  request jsonb NOT NULL,
  state text NOT NULL CHECK (state IN ('dispatching','review_required','failed','uncertain')),
  result jsonb,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE (project, task_id, source_sha)
);
-- One active/ambiguous attempt on this worker host, across all projects.
CREATE UNIQUE INDEX one_active_dispatch ON controller.runs ((1))
  WHERE state IN ('dispatching','uncertain');
CREATE UNIQUE INDEX outstanding_task ON controller.runs (project,task_id)
  WHERE state IN ('dispatching','uncertain','review_required');
CREATE TABLE controller.events (
  sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id text NOT NULL REFERENCES controller.runs(run_id),
  state text NOT NULL,
  detail jsonb NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE FUNCTION controller.claim(req jsonb, digest text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, controller AS $$
DECLARE row controller.runs;
BEGIN
  INSERT INTO controller.runs(run_id,project,task_id,source_sha,request_sha256,request,state)
    VALUES(req->>'run_id', req->'plan'->>'project', req->'plan'->>'task_id',
           req->'plan'->>'source_sha', digest, req, 'dispatching') RETURNING * INTO row;
  INSERT INTO controller.events(run_id,state,detail)
    VALUES(row.run_id, row.state, jsonb_build_object('request_sha256',digest));
  RETURN to_jsonb(row);
END $$;
CREATE FUNCTION controller.finish(id text, next_state text, evidence jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, controller AS $$
DECLARE row controller.runs;
BEGIN
  IF next_state NOT IN ('review_required','failed','uncertain') THEN
    RAISE EXCEPTION 'Invalid transition';
  END IF;
  SELECT * INTO STRICT row FROM controller.runs WHERE run_id=id FOR UPDATE;
  IF row.state NOT IN ('dispatching','uncertain') THEN
    RAISE EXCEPTION 'Terminal run cannot transition or retry';
  END IF;
  UPDATE controller.runs SET state=next_state,result=evidence,updated_at=clock_timestamp()
    WHERE run_id=id RETURNING * INTO row;
  INSERT INTO controller.events(run_id,state,detail) VALUES(id,next_state,evidence);
  RETURN to_jsonb(row);
END $$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA controller FROM PUBLIC;
GRANT USAGE ON SCHEMA controller TO gatewayai_controller;
GRANT SELECT ON ALL TABLES IN SCHEMA controller TO gatewayai_controller;
GRANT EXECUTE ON FUNCTION controller.claim(jsonb,text), controller.finish(text,text,jsonb)
  TO gatewayai_controller;
COMMIT;
