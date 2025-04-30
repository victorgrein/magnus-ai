"""
Push Notification Authentication Service.

This service implements JWT authentication for A2A push notifications,
allowing agents to send authenticated notifications and clients to verify
the authenticity of received notifications.
"""

from jwcrypto import jwk
import uuid
import time
import json
import hashlib
import httpx
import logging
import jwt
from jwt import PyJWK, PyJWKClient
from fastapi import Request
from starlette.responses import JSONResponse
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)
AUTH_HEADER_PREFIX = "Bearer "


class PushNotificationAuth:
    """
    Base class for push notification authentication.

    Contains common methods used by both the sender and the receiver
    of push notifications.
    """

    def _calculate_request_body_sha256(self, data: Dict[str, Any]) -> str:
        """
        Calculates the SHA256 hash of the request body.

        This logic needs to be the same for the agent that signs the payload
        and for the client that verifies it.

        Args:
            data: Request body data

        Returns:
            SHA256 hash as a hexadecimal string
        """
        body_str = json.dumps(
            data,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        )
        return hashlib.sha256(body_str.encode()).hexdigest()


class PushNotificationSenderAuth(PushNotificationAuth):
    """
    Authentication for the push notification sender.

    This class is used by the A2A server to authenticate notifications
    sent to callback URLs of clients.
    """

    def __init__(self):
        """
        Initialize the push notification sender authentication service.
        """
        self.public_keys = []
        self.private_key_jwk = None

    @staticmethod
    async def verify_push_notification_url(url: str) -> bool:
        """
        Verifies if a push notification URL is valid and responds correctly.

        Sends a validation token and verifies if the response contains the same token.

        Args:
            url: URL to be verified

        Returns:
            True if the URL is verified successfully, False otherwise
        """
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                validation_token = str(uuid.uuid4())
                response = await client.get(
                    url, params={"validationToken": validation_token}
                )
                response.raise_for_status()
                is_verified = response.text == validation_token

                logger.info(f"Push notification URL verified: {url} => {is_verified}")
                return is_verified
            except Exception as e:
                logger.warning(f"Error verifying push notification URL {url}: {e}")

        return False

    def generate_jwk(self):
        """
        Generates a new JWK pair for signing.

        The key pair is used to sign push notifications.
        The public key is available via the JWKS endpoint.
        """
        key = jwk.JWK.generate(kty="RSA", size=2048, kid=str(uuid.uuid4()), use="sig")
        self.public_keys.append(key.export_public(as_dict=True))
        self.private_key_jwk = PyJWK.from_json(key.export_private())

    def handle_jwks_endpoint(self, _request: Request) -> JSONResponse:
        """
        Handles the JWKS endpoint to allow clients to obtain the public keys.

        Args:
            _request: HTTP request

        Returns:
            JSON response with the public keys
        """
        return JSONResponse({"keys": self.public_keys})

    def _generate_jwt(self, data: Dict[str, Any]) -> str:
        """
        Generates a JWT token by signing the SHA256 hash of the payload and the timestamp.

        The payload is signed with the private key to ensure integrity.
        The timestamp (iat) prevents replay attacks.

        Args:
            data: Payload data

        Returns:
            Signed JWT token
        """
        iat = int(time.time())

        return jwt.encode(
            {
                "iat": iat,
                "request_body_sha256": self._calculate_request_body_sha256(data),
            },
            key=self.private_key_jwk.key,
            headers={"kid": self.private_key_jwk.key_id},
            algorithm="RS256",
        )

    async def send_push_notification(self, url: str, data: Dict[str, Any]) -> bool:
        """
        Sends an authenticated push notification to the specified URL.

        Args:
            url: URL to send the notification
            data: Notification data

        Returns:
            True if the notification was sent successfully, False otherwise
        """
        if not self.private_key_jwk:
            logger.error(
                "Attempt to send push notification without generating JWK keys"
            )
            return False

        try:
            jwt_token = self._generate_jwt(data)
            headers = {"Authorization": f"Bearer {jwt_token}"}

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=data, headers=headers)
                response.raise_for_status()
                logger.info(f"Push notification sent to URL: {url}")
                return True
        except Exception as e:
            logger.warning(f"Error sending push notification to URL {url}: {e}")
            return False


class PushNotificationReceiverAuth(PushNotificationAuth):
    """
    Authentication for the push notification receiver.

    This class is used by clients to verify the authenticity
    of notifications received from the A2A server.
    """

    def __init__(self):
        """
        Initialize the push notification receiver authentication service.
        """
        self.jwks_client = None

    async def load_jwks(self, jwks_url: str):
        """
        Loads the public JWKS keys from a URL.

        Args:
            jwks_url: URL of the JWKS endpoint
        """
        self.jwks_client = PyJWKClient(jwks_url)

    async def verify_push_notification(self, request: Request) -> bool:
        """
        Verifies the authenticity of a push notification.

        Args:
            request: HTTP request containing the notification

        Returns:
            True if the notification is authentic, False otherwise

        Raises:
            ValueError: If the token is invalid or expired
        """
        if not self.jwks_client:
            logger.error("Attempt to verify notification without loading JWKS keys")
            return False

        # Verify authentication header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith(AUTH_HEADER_PREFIX):
            logger.warning("Invalid authorization header")
            return False

        try:
            # Extract and verify token
            token = auth_header[len(AUTH_HEADER_PREFIX) :]
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)

            # Decode token
            decode_token = jwt.decode(
                token,
                signing_key.key,
                options={"require": ["iat", "request_body_sha256"]},
                algorithms=["RS256"],
            )

            # Verify request body integrity
            body_data = await request.json()
            actual_body_sha256 = self._calculate_request_body_sha256(body_data)
            if actual_body_sha256 != decode_token["request_body_sha256"]:
                # The payload signature does not match the hash in the signed token
                logger.warning("Request body hash does not match the token")
                raise ValueError("Invalid request body")

            # Verify token age (maximum 5 minutes)
            if time.time() - decode_token["iat"] > 60 * 5:
                # Do not allow notifications older than 5 minutes
                # This prevents replay attacks
                logger.warning("Token expired")
                raise ValueError("Token expired")

            return True

        except Exception as e:
            logger.error(f"Error verifying push notification: {e}")
            return False


# Global instance of the push notification sender authentication service
push_notification_auth = PushNotificationSenderAuth()

# Generate JWK keys on initialization
push_notification_auth.generate_jwk()
