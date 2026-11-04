"""The audit log is append-only at the database level: UPDATE and DELETE are refused for every role,
including the application's own (MTS §6 Governance, §9 Audit)."""

from django.db import migrations

FORWARD = """
CREATE FUNCTION audit_log_is_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_auditlog is append-only (% refused)', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_no_update_or_delete
    BEFORE UPDATE OR DELETE ON audit_auditlog
    FOR EACH ROW EXECUTE FUNCTION audit_log_is_append_only();
"""

BACKWARD = """
DROP TRIGGER IF EXISTS audit_log_no_update_or_delete ON audit_auditlog;
DROP FUNCTION IF EXISTS audit_log_is_append_only();
"""


class Migration(migrations.Migration):
    dependencies = [("audit", "0001_initial")]
    operations = [migrations.RunSQL(FORWARD, BACKWARD)]
