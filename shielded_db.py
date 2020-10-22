import traceback
import logging
import asyncio
import settings
from gino import Gino
from asyncio import LifoQueue

logger = logging.getLogger(settings.APP_NAME)


class ShieldedDB(Gino):


    def __init__(self):
        self.queue = LifoQueue()
        self.loop = asyncio.get_event_loop()
        super().__init__()

    async def push(self, creatable, callback, retry_logic=None):
        '''
        This method is used to add values to the queue, which retries if failure occurs
        * creatable: should be of the form Payload(**payload)
        * callback: contains a function to complete the actions within the transaction
        '''
        if self.queue.full():
            await asyncio.sleep(0.1)
            await self.push(creatable, callback, retry_logic)
        else:
            try:
                await self.queue.put((creatable, callback, retry_logic))
            except:
                logger.error(f'Failed to insert into queue: {traceback.format_exc()}')
                logger.debug(f'Retrying addition to queue -- sleeping first...')
                await asyncio.sleep(0.1)
                await self.push(creatable, callback, retry_logic)

    async def pop(self):
        '''
        This method is used to pops a value from the queue
        '''
        try:
            return await self.queue.get()
        except:
            logger.error(f'Failed to pop from queue: {traceback.format_exc()}')

    async def has_connection(self, timeout=None):
        '''
        This method checks for database connection and is used before we start a transaction
        '''
        try:
            await self.bind.acquire(timeout=timeout)
        except:
            return False
        return True

    async def insert(self, head, callback):
        try:
            async with self.transaction():
                logger.error('In transaction...')
                created = await head.create()
                if asyncio.iscoroutinefunction(callback):
                    await callback(created)
                else:
                    callback(created)
            logger.error('Finished Transaction')
        except:
            logger.error(traceback.format_exc())
            raise

    async def _consume(self):
        while not self.queue.empty():
            if await self.has_connection():
                logger.error('Consuming...')
                try:
                    (head, callback, retry_logic) = await self.pop()
                    await self.insert(head, callback)
                except:
                    logger.error(f'Failed to insert payload: {traceback.format_exc()}')
                    if retry_logic:
                        if asyncio.iscoroutinefunction(retry_logic):
                            await retry_logic(**{'head': head, 'callback': callback})
                        else:
                            retry_logic(**{'head': head, 'callback': callback})
            else:
                await asyncio.sleep(1)

    async def consume(self):
        '''
        Use this method to initialize an insertion
        '''
        while True:
            await asyncio.sleep(1)
            if self.queue.empty():
                await asyncio.sleep(1)
            else:
                self.loop.create_task(self._consume())

