def dump(cols, res):
    return [{k.key: v for k, v in zip(cols, row) if v is not None} for row in res]


def get_date_specificity(date):
    for attr in ['microsecond', 'second', 'minute', 'hour', 'day']:
        if getattr(date, attr):
            return attr
