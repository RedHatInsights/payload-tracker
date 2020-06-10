import logging
import settings

logger = logging.getLogger(settings.APP_NAME)


class Cache:

    def __init__(self, items):
        self.cache = self._create_cache(items)

    def _create_cache(self, items):
        if type(items) is dict:
            return items
        else:
            logger.error(f'Could not initialize cache with type {type(items)}')
            raise TypeError

    def set_value(self, key, value):
        self.cache[key].update(value)

    def get_value(self, key):
        return self.cache[key]

    def __iter__(self):
        for key in self.cache:
            yield self.cache[key]


cache = Cache({'services': {}, 'sources': {}})
