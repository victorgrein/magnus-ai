import aiohttp
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import asyncio

from src.services.push_notification_auth_service import push_notification_auth

logger = logging.getLogger(__name__)


class PushNotificationService:
    def __init__(self):
        self.session = aiohttp.ClientSession()

    async def send_notification(
        self,
        url: str,
        task_id: str,
        state: str,
        message: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        use_jwt_auth: bool = True,
    ) -> bool:
        """
        Send a push notification to the specified URL.
        Implements exponential backoff retry.

        Args:
            url: URL to send the notification
            task_id: Task ID
            state: Task state
            message: Optional message
            headers: Optional HTTP headers
            max_retries: Maximum number of retries
            retry_delay: Initial delay between retries
            use_jwt_auth: Whether to use JWT authentication

        Returns:
            True if the notification was sent successfully, False otherwise
        """
        payload = {
            "taskId": task_id,
            "state": state,
            "timestamp": datetime.now().isoformat(),
            "message": message,
        }

        # First URL verification
        if use_jwt_auth:
            is_url_valid = await push_notification_auth.verify_push_notification_url(
                url
            )
            if not is_url_valid:
                logger.warning(f"Invalid push notification URL: {url}")
                return False

        for attempt in range(max_retries):
            try:
                if use_jwt_auth:
                    # Use JWT authentication
                    success = await push_notification_auth.send_push_notification(
                        url, payload
                    )
                    if success:
                        return True
                else:
                    # Legacy method without JWT authentication
                    async with self.session.post(
                        url, json=payload, headers=headers or {}, timeout=10
                    ) as response:
                        if response.status in (200, 201, 202, 204):
                            logger.info(f"Push notification sent to URL: {url}")
                            return True
                        else:
                            logger.warning(
                                f"Failed to send push notification with status {response.status}. "
                                f"Attempt {attempt + 1}/{max_retries}"
                            )
            except Exception as e:
                logger.error(
                    f"Error sending push notification: {str(e)}. "
                    f"Attempt {attempt + 1}/{max_retries}"
                )

            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (2**attempt))

        return False

    async def close(self):
        """Close the HTTP session"""
        await self.session.close()


# Global instance of the push notification service
push_notification_service = PushNotificationService()
