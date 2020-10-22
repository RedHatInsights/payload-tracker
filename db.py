import config
from shielded_db import ShieldedDB
db = ShieldedDB()


async def init_db():
    await db.set_bind('asyncpg://{}:{}@{}:{}/{}'.format(config.db_user,
                                                           config.db_password,
                                                           config.db_host,
                                                           config.db_port,
                                                           config.db_name))


async def disconnect():
    db.pop_bind().close()


class Payload(db.Model):
    __tablename__ = 'payloads'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    request_id = db.Column(db.Unicode)
    account = db.Column(db.Unicode)
    inventory_id = db.Column(db.Unicode)
    system_id = db.Column(db.Unicode)
    created_at = db.Column(db.DateTime(timezone=True), server_default="timezone('utc'::text, now())")

    def dump(self):
        return {k: v for k, v in self.__values__.items() if v is not None}


class PayloadStatus(db.Model):
    __tablename__ = 'payload_statuses'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    payload_id = db.Column(db.Integer, db.ForeignKey('payloads.id', ondelete='CASCADE'))
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'))
    source_id = db.Column(db.Integer, db.ForeignKey('sources.id'))
    status_id = db.Column(db.Unicode, db.ForeignKey('statuses.id'))
    status_msg = db.Column(db.Unicode)
    date = db.Column(db.DateTime(timezone=True), server_default="timezone('utc'::text, now())")
    created_at = db.Column(db.DateTime(timezone=True), server_default="timezone('utc'::text, now())")

    def dump(self):
        return {k: v for k, v in self.__values__.items() if v is not None}


class Sources(db.Model):
    __tablename__ = 'sources'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Unicode, unique=True)

    def dump(self):
        return {k: v for k, v in self.__values__.items() if v is not None}


class Services(db.Model):
    __tablename__ = 'services'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Unicode, unique=True)

    def dump(self):
        return {k: v for k, v in self.__values__.items() if v is not None}


class Statuses(db.Model):
    __tablename__ = 'statuses'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Unicode, unique=True)

    def dump(self):
        return {k: v for k, v in self.__values__.items() if v is not None}


tables = {table.__tablename__: table for table in [Payload, PayloadStatus, Services, Sources, Statuses]}
