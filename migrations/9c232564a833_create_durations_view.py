"""Create Durations View

Revision ID: 9c232564a833
Revises: 1f8a919555e1
Create Date: 2020-05-11 10:56:57.529269

"""
from alembic.operations import Operations, MigrateOperation
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9c232564a833'
down_revision = '1f8a919555e1'
branch_labels = None
depends_on = None


class ReplaceableObject(object):
    def __init__(self, name, sqltext):
        self.name = name
        self.sqltext = sqltext


class ReversibleOp(MigrateOperation):
    def __init__(self, target):
        self.target = target

    @classmethod
    def invoke_for_target(cls, operations, target):
        op = cls(target)
        return operations.invoke(op)

    def reverse(self):
        raise NotImplementedError()

    @classmethod
    def _get_object_from_version(cls, operations, ident):
        version, objname = ident.split(".")

        module = operations.get_context().script.get_revision(version).module
        obj = getattr(module, objname)
        return obj

    @classmethod
    def replace(cls, operations, target, replaces=None, replace_with=None):

        if replaces:
            old_obj = cls._get_object_from_version(operations, replaces)
            drop_old = cls(old_obj).reverse()
            create_new = cls(target)
        elif replace_with:
            old_obj = cls._get_object_from_version(operations, replace_with)
            drop_old = cls(target).reverse()
            create_new = cls(old_obj)
        else:
            raise TypeError("replaces or replace_with is required")

        operations.invoke(drop_old)
        operations.invoke(create_new)


@Operations.register_operation("create_view", "invoke_for_target")
@Operations.register_operation("replace_view", "replace")
class CreateViewOp(ReversibleOp):
    def reverse(self):
        return DropViewOp(self.target)


@Operations.register_operation("drop_view", "invoke_for_target")
class DropViewOp(ReversibleOp):
    def reverse(self):
        return CreateViewOp(self.target)


@Operations.implementation_for(CreateViewOp)
def create_view(operations, operation):
    operations.execute("CREATE VIEW %s AS %s" % (
        operation.target.name,
        operation.target.sqltext
    ))


@Operations.implementation_for(DropViewOp)
def drop_view(operations, operation):
    operations.execute("DROP VIEW %s" % operation.target.name)


durations_view = ReplaceableObject(
    'durations',
    '''
    SELECT a.request_id, a.service, max(a.date) - min(b.date) as duration, min(a.date) as start, max(b.date) as end
    FROM payloads AS a
    CROSS JOIN payloads AS b
    WHERE a.service = b.service AND a.request_id = b.request_id
    GROUP BY a.service, a.request_id;
    '''
)


def upgrade(): op.create_view(durations_view)


def downgrade(): op.drop_view(durations_view)
