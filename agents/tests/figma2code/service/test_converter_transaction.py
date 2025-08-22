import pytest
from core.db.database_transaction import transactional
from core.bind.repository import Repository


class DummyRepository(Repository):
    def __init__(self) -> None:
        # 실제 세션 없이도 동작하도록 속성만 유지
        self.did_commit = False
        self.did_rollback = False
        self.did_close = False
        self.events: list[str] = []

    async def commit(self) -> None:
        self.did_commit = True
        self.events.append("commit")

    async def rollback(self) -> None:
        self.did_rollback = True
        self.events.append("rollback")

    async def close(self) -> None:
        self.did_close = True
        self.events.append("close")


class TransactionalService:
    def __init__(self) -> None:
        # Repository 타입 속성만 transactional 데코레이터가 감지하여 커밋/롤백/클로즈 호출
        self.repo_a = DummyRepository()
        self.repo_b = DummyRepository()

    @transactional
    async def do_success(self) -> str:
        # 비즈니스 로직이 정상 완료되는 경우
        return "ok"

    @transactional
    async def do_fail(self) -> None:
        # 중간에 실패하는 경우
        raise Exception("의도적인 실패!")


class TestTransactionalDecorator:
    async def test_successful_transaction_commits_and_closes(self) -> None:
        service = TransactionalService()

        result = await service.do_success()

        assert result == "ok"
        # 두 레포 모두 commit/close 호출, rollback 미호출
        for repo in (service.repo_a, service.repo_b):
            assert repo.did_commit is True
            assert repo.did_close is True
            assert repo.did_rollback is False

    async def test_exception_rolls_back_and_closes(self) -> None:
        service = TransactionalService()

        with pytest.raises(Exception, match="의도적인 실패!"):
            await service.do_fail()

        # 두 레포 모두 rollback/close 호출, commit 미호출
        for repo in (service.repo_a, service.repo_b):
            assert repo.did_rollback is True
            assert repo.did_close is True
            assert repo.did_commit is False

    async def test_multiple_operations_each_wraps_transaction(self) -> None:
        service = TransactionalService()

        # 첫 호출
        await service.do_success()
        # 두 번째 호출 (각 호출마다 트랜잭션 묶임)
        await service.do_success()

        # 각 호출마다 commit/close가 누적되어야 함
        assert service.repo_a.events.count("commit") >= 2
        assert service.repo_a.events.count("close") >= 2
        assert service.repo_b.events.count("commit") >= 2
        assert service.repo_b.events.count("close") >= 2
