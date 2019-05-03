from insights_connexion.db.gino import db


class Payload(db.Model):
    """
    {   'id': UUID
        ‘service’: ‘The services name processing the payload’,
        ‘payload_id’: ‘The ID of the payload’,
        ‘inventory_id’: “The ID of the entity in term of the inventory’,
        ‘system_id’: ‘The ID of the entity in terms of the actual system’,
        ‘status’: ‘received|processing|success|failure’,
        ‘status_msg’: ‘Information relating to the above status, should more verbiage be needed (in the event of an error)’,
        ‘date’: ‘Timestamp for the message relating to the ‘status’ above’,
        'created_at': DB timestamp
    }
    """

    __tablename__ = 'payloads'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    service = db.Column(db.Unicode)
    payload_id = db.Column(db.Unicode)
    inventory_id = db.Column(db.Unicode)
    system_id = db.Column(db.Unicode)
    status = db.Column(db.Unicode)
    status_msg = db.Column(db.Unicode)
    date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def dump(self):
        return {k: v for k, v in self.__values__.items() if v is not None}
