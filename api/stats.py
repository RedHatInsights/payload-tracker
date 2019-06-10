import responses


async def search(*args, **kwargs):
    return responses.not_found()
