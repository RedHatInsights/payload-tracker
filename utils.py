def dump(cols, res):
    return [{k.key: v for k, v in zip(cols, row) if v is not None} for row in res]

# define class which uses tuple as key in key/value store
class Triple():

    def __init__(self, a, b, c):
        self.key = (a, b)
        self.value = c

    def __repr__(self):
        return f'{self.key}: {self.value}'

# define a functional list of Triple objects
class TripleSet():

    def __init__(self, initialVal=None):
        self.data = [initialVal] if initialVal and type(initialVal) is Triple else []

    def keys(self):
        return [item.key for item in self.data]

    def values(self):
        return [item.value for item in self.data]

    def append(self, value):
        if type(value) is Triple:
            self.data.append(value)

    def __repr__(self):
        return repr(self.data)
