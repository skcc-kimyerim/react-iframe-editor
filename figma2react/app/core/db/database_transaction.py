import functools
import inspect
from typing import Any, Callable, Type, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def transactional(func: F) -> F:
    """
    중첩 트랜잭션을 지원하는 트랜잭션 데코레이터
    """

    @functools.wraps(func)
    async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        from core.bind.repository import Repository

        # Repository 객체들을 한 번만 찾아서 캐시
        repositories = []
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if isinstance(attr, Repository):
                repositories.append(attr)

        try:
            if inspect.iscoroutinefunction(func):
                result = await func(self, *args, **kwargs)
            else:
                result = func(self, *args, **kwargs)

            # 캐시된 Repository들에 대해 commit 수행
            for repository in repositories:
                await repository.commit()

            return result
        except Exception as e:
            # 캐시된 Repository들에 대해 rollback 수행
            for repository in repositories:
                await repository.rollback()

            raise e
        finally:
            # 캐시된 Repository들에 대해 close 수행
            for repository in repositories:
                await repository.close()

    return wrapper


# 클래스 데코레이터로도 사용할 수 있는 버전
def transactional_class(cls: Type[Any]) -> Type[Any]:
    """
    클래스의 모든 public 메서드에 @transactional을 적용하는 데코레이터
    """
    for attr_name in dir(cls):
        attr = getattr(cls, attr_name)
        if (
            callable(attr)
            and not attr_name.startswith("_")
            and not attr_name.startswith("__")
        ):
            setattr(cls, attr_name, transactional(attr))
    return cls
