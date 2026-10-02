-- Additive pilot state; independent of the existing publication schema version.
BEGIN;
CREATE TABLE IF NOT EXISTS controller.pilot_state (
  id integer PRIMARY KEY CHECK (id=1), revision bigint NOT NULL,
  value jsonb NOT NULL CHECK (jsonb_typeof(value)='object')
);
REVOKE ALL ON controller.pilot_state FROM PUBLIC, gatewayai_controller;
CREATE OR REPLACE FUNCTION controller.pilot_read() RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog AS $$
 SELECT coalesce((SELECT jsonb_build_object('revision',revision,'value',value)
 FROM controller.pilot_state WHERE id=1),'{"revision":0,"value":{}}'::jsonb)
$$;
CREATE OR REPLACE FUNCTION controller.pilot_cas(expected bigint, candidate jsonb)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE changed integer;
BEGIN
 IF jsonb_typeof(candidate) <> 'object' OR octet_length(candidate::text)>2000000 THEN
   RAISE EXCEPTION 'Invalid pilot state';
 END IF;
 IF expected=0 THEN
   INSERT INTO controller.pilot_state VALUES(1,1,candidate) ON CONFLICT DO NOTHING;
 ELSE
   UPDATE controller.pilot_state SET revision=revision+1,value=candidate
   WHERE id=1 AND revision=expected;
 END IF;
 GET DIAGNOSTICS changed=ROW_COUNT;
 RETURN changed=1;
END $$;
REVOKE ALL ON FUNCTION controller.pilot_read(),controller.pilot_cas(bigint,jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION controller.pilot_read(),controller.pilot_cas(bigint,jsonb) TO gatewayai_controller;
COMMIT;
