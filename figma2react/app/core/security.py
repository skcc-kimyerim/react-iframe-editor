import jwt
from core.cache.key_cache import KeyCache
from core.config import get_setting
from core.exception.error_codes import ErrorCode
from core.exception.exceptions import ServiceException
from core.log.logging import get_logging
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

settings = get_setting()
logger = get_logging()

SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = "HS256"
key_cache = KeyCache(settings.KEY_API_URL)

# auto_error=False 로 설정해두면, 토큰이 없더라도 FastAPI가 자동 401을 발생시키지 않음
security = HTTPBearer(auto_error=False)


async def get_token_from_header(request: Request) -> str:
    credentials: HTTPAuthorizationCredentials = await security(request)
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


async def verify_sso_jwt_token(token: str) -> dict:
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        algorithm = header.get("alg")

        if not kid:
            raise ValueError("Missing kid in JWT header")

        public_key = await key_cache.get_public_key(kid)

        payload = jwt.decode(token, public_key, algorithms=[algorithm])

        if not payload.get("empno") or not payload.get("company_cd"):
            raise ServiceException(
                error_code=ErrorCode.NOT_DEFINED,
                message="empno or company_cd in JWT payload is required",
            )

        return payload

    except jwt.ExpiredSignatureError:
        logger.error("Token has expired")
        raise ServiceException(
            error_code=ErrorCode.TOKEN_EXPIRED,
        )
    except jwt.PyJWTError:
        logger.error("Invalid token")
        raise ServiceException(
            error_code=ErrorCode.INVALID_AUTH,
        )
    except ValueError:
        raise ServiceException(
            error_code=ErrorCode.INVALID_AUTH,
        )
    except Exception as e:
        logger.exception(f"Token verification failed: {e}")
        raise ServiceException(
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


def verify_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.error("Token has expired")
        raise ServiceException(
            error_code=ErrorCode.TOKEN_EXPIRED,
        )
    except jwt.PyJWTError:
        logger.error("Invalid token")
        raise ServiceException(
            error_code=ErrorCode.INVALID_AUTH,
        )


# def _create_user_info_from_payload(token_payload: dict) -> UserInfo:
#     """Create UserInfo object from token payload"""
#     return UserInfo(
#         user_id=token_payload["user_id"],
#         email=token_payload["email"],
#         username=token_payload["username"],
#         company_code=token_payload["company_code"],
#         department=token_payload["department"],
#         cmmn_user_id=token_payload["cmmn_user_id"],
#     )


# async def get_user_info_from_token(
#     credentials: HTTPAuthorizationCredentials = Security(security),
# ) -> Optional[UserInfo]:
#     """
#     - LOCAL 환경인 경우: 토큰이 없어도 OK, 있으면 ai-chat 에서 발급한 JWT 검증
#     - 그 외 환경: 토큰이 없으면 401, 있으면 A.Biz SSO JWT 검증
#     """
#     user_info: UserInfo = None

#     if settings.ENVIRONMENT == "LOCAL":
#         if not credentials or not credentials.credentials:
#             # return None
#             user_info = UserInfo(
#                 user_id="10861",
#                 email="10861@skcc.com",
#                 username="김지환",
#                 department="AI혁신팀",
#                 company_code="SKCC",
#                 cmmn_user_id="SKCC.10861",
#             )
#             async for db in get_async_db_by_schema_name(user_info.company_code):
#                 await get_or_create_user_with_transaction(db, user_info)
#         else:
#             token_payload = verify_access_token(credentials.credentials)
#             user_info = _create_user_info_from_payload(token_payload)
#     else:
#         if not credentials or not credentials.credentials:
#             raise ServiceException(
#                 status_code=401,
#                 error_code=ErrorCode.NO_TOKEN,
#                 detail="Authentication required",
#             )
#         else:
#             if credentials.credentials.startswith("EVAL-"):
#                 access_token = credentials.credentials.split("EVAL-")[1]
#                 token_payload = verify_access_token(access_token)
#                 user_info = _create_user_info_from_payload(token_payload)
#             else:
#                 token_payload = await verify_sso_jwt_token(credentials.credentials)
#                 user_id = token_payload.get("empno")
#                 company_code = token_payload.get("company_cd")
#                 cmmn_user_id = token_payload.get("user_id")

#                 async for db in get_async_db_by_schema_name(company_code):
#                     user_info: UserInfo = await get_or_fetch_user(
#                         db, company_code, user_id
#                     )
#                 user_info.cmmn_user_id = cmmn_user_id
#     user_info.company_code = user_info.company_code.upper()
#     user_info.email = transform_company_email(user_info.company_code, user_info.email)
#     user_info_ctx.set(user_info)
#     return user_info


# def create_access_token(user_info: UserInfo, iat: float) -> str:
#     exp = iat + 60 * 60 * 24
#     payload = {
#         "service": "ai-chat",
#         "exp": exp,
#         "iat": iat,
#         "user_id": user_info.user_id,
#         "email": user_info.email,
#         "username": user_info.username,
#         "company_code": user_info.company_code,
#         "department": user_info.department,
#         "cmmn_user_id": f"{user_info.company_code.upper()}.{user_info.user_id}",
#     }
#     token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
#     return token
