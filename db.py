import config
from gino import Gino
db = Gino()


async def init_db():
    await db.set_bind('postgresql://{}:{}@{}:{}/{}'.format(config.db_user,
                                                           config.db_password,
                                                           config.db_host,
                                                           config.db_port,
                                                           config.db_name))


async def disconnect():
    db.pop_bind().close()


class Payload(db.Model):
    __tablename__ = 'payloads'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    service = db.Column(db.Unicode)
    source = db.Column(db.Unicode)
    account = db.Column(db.Unicode)
    request_id = db.Column(db.Unicode)
    inventory_id = db.Column(db.Unicode)
    system_id = db.Column(db.Unicode)
    status = db.Column(db.Unicode)
    status_msg = db.Column(db.Unicode)
    date = db.Column(db.DateTime(timezone=True), server_default="timezone('utc'::text, now())")
    created_at = db.Column(db.DateTime(timezone=True), server_default="timezone('utc'::text, now())")

    def dump(self):
        return {k: v for k, v in self.__values__.items() if v is not None}
