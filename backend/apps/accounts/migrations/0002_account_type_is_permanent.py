"""An account's type (customer or staff) is fixed at creation (MTS §6 Identity, A-22). Enforced in the database
so that no code path, migration or manual query can turn a customer into staff or back."""

from django.db import migrations

FORWARD = """
CREATE FUNCTION accounts_account_type_is_permanent() RETURNS trigger AS $$
BEGIN
    IF NEW.account_type <> OLD.account_type THEN
        RAISE EXCEPTION 'accounts_account.account_type cannot change';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER accounts_account_type_permanent
    BEFORE UPDATE OF account_type ON accounts_account
    FOR EACH ROW EXECUTE FUNCTION accounts_account_type_is_permanent();
"""

BACKWARD = """
DROP TRIGGER IF EXISTS accounts_account_type_permanent ON accounts_account;
DROP FUNCTION IF EXISTS accounts_account_type_is_permanent();
"""


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [migrations.RunSQL(FORWARD, BACKWARD)]
