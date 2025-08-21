import asyncio
from typing import Dict

import httpx
from core.config import get_setting
from fastapi import HTTPException

settings = get_setting()


class KeyCache:
    """
    PEM 문자열과 kid를 매핑해 저장하는 캐시 객체
    """

    def __init__(self, key_api_url: str):
        self._cache: Dict[str, str] = {}
        self._lock = asyncio.Lock()
        self.key_api_url = key_api_url

    async def get_public_key(self, kid: str) -> str:
        """
        캐시에 kid가 있으면 PEM 반환
        없으면 refresh_key로 갱신 후 다시 캐시에서 찾아 반환
        캐시에도 없으면 400 오류
        """
        if kid in self._cache:
            return self._cache[kid]

        # 갱신 후 캐시에서 확인
        await self.__refresh_key(kid)

        # 갱신 후 캐시에서 확인
        if kid in self._cache:
            return self._cache[kid]

        # 여전히 없으면 잘못된 kid
        raise HTTPException(status_code=400, detail="Invalid kid")

    async def __refresh_key(self, kid: str) -> None:
        """
        API 호출로 키 갱신
        - 단일 잠금으로 동시 요청 방지
        - API 오류 시 기존 캐시 유지
        """
        async with self._lock:
            # 잠금 후 재확인
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    headers = {
                        "X-Request-Source": settings.APP_NAME,
                    }
                    resp = await client.get(f"{self.key_api_url}", headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
            except (httpx.HTTPError, ValueError):
                # API 호출 실패 시 기존 캐시 유지
                return

            # API 결과 유효성 검사
            if data:
                self._cache = {
                    key_info["kid"]: key_info["public_key"] for key_info in data
                }
                return
            # 유효하지 않은 kid는 캐시 업데이트하지 않음
            return


# 모듈 로드 시 싱글톤 인스턴스 생성
key_cache = KeyCache(key_api_url=f"{settings.CMMN_API_URI}/auth/keys/get-pub-keys")
