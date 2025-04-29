import aiohttp
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import asyncio

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
    ) -> bool:
        """
        Envia uma notificação push para a URL especificada.
        Implementa retry com backoff exponencial.
        """
        payload = {
            "taskId": task_id,
            "state": state,
            "timestamp": datetime.now().isoformat(),
            "message": message,
        }

        for attempt in range(max_retries):
            try:
                async with self.session.post(
                    url, json=payload, headers=headers or {}, timeout=10
                ) as response:
                    if response.status in (200, 201, 202, 204):
                        return True
                    else:
                        logger.warning(
                            f"Push notification failed with status {response.status}. "
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
        """Fecha a sessão HTTP"""
        await self.session.close()


# Instância global do serviço
push_notification_service = PushNotificationService()
