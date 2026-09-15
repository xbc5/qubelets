from qubelets.lib.common.http import HttpNotFoundError


class FakeHttp:
    """Serve canned JSON by URL; unknown URLs are 404. Exceptions are raised."""

    def __init__(self, responses: dict):
        self.responses = responses
        self.requested = []

    def get_json(self, url: str):
        self.requested.append(url)
        if url not in self.responses:
            raise HttpNotFoundError(url)
        response = self.responses[url]
        if isinstance(response, Exception):
            raise response
        return response
