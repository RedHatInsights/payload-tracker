def dump(cols, res):
    return [{k.key: v for k, v in zip(cols, row) if v is not None} for row in res]
