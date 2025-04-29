import asyncio
from typing import AsyncGenerator, Optional
from fastapi import HTTPException


class SSEUtils:
    @staticmethod
    async def with_timeout(
        generator: AsyncGenerator, timeout: int = 30, retry_attempts: int = 3
    ) -> AsyncGenerator:
        """
        Adiciona timeout e retry a um gerador de eventos SSE.

        Args:
            generator: Gerador de eventos
            timeout: Tempo máximo de espera em segundos
            retry_attempts: Número de tentativas de reconexão

        Yields:
            Eventos do gerador
        """
        attempts = 0
        while attempts < retry_attempts:
            try:
                async for event in asyncio.wait_for(generator, timeout):
                    yield event
                break
            except asyncio.TimeoutError:
                attempts += 1
                if attempts >= retry_attempts:
                    raise HTTPException(
                        status_code=408, detail="Timeout após múltiplas tentativas"
                    )
                await asyncio.sleep(1)  # Espera antes de tentar novamente

    @staticmethod
    def format_error_event(error: Exception) -> str:
        """
        Formata um evento de erro SSE.

        Args:
            error: Exceção ocorrida

        Returns:
            String formatada do evento SSE
        """
        return f"event: error\ndata: {str(error)}\n\n"

    @staticmethod
    def validate_sse_headers(headers: dict) -> None:
        """
        Valida headers necessários para SSE.

        Args:
            headers: Dicionário de headers

        Raises:
            HTTPException se headers inválidos
        """
        required_headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }

        for header, value in required_headers.items():
            if headers.get(header) != value:
                raise HTTPException(
                    status_code=400, detail=f"Header {header} inválido ou ausente"
                )
