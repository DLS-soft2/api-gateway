import jwt


class JwksService:
    def __init__(self, issuer_url: str):
        self._jwks_url = issuer_url.rstrip("/") + "/protocol/openid-connect/certs"
        self._jwks_client = jwt.PyJWKClient(self._jwks_url, cache_keys=True)

    def get_signing_key(self, token: str) -> jwt.PyJWK:
        try:
            return self._jwks_client.get_signing_key_from_jwt(token)
        except jwt.PyJWKClientError:
            self._jwks_client.fetch_data()
            return self._jwks_client.get_signing_key_from_jwt(token)
