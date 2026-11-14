class ExternalSourceError(Exception):
    """Une source externe est injoignable ou a renvoyé une réponse inexploitable."""

    def __init__(self, source: str, message: str):
        super().__init__(f"{source} : {message}")
        self.source = source
        self.message = message
