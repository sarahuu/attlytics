from agent.instance_lock import InstanceLock


def test_acquire_release_and_reacquire(tmp_path):
    lock = InstanceLock(tmp_path / "agent.lock")

    assert lock.acquire() is True
    lock.release()

    assert lock.acquire() is True
    lock.release()


def test_second_lock_cannot_acquire_while_locked(tmp_path):
    first = InstanceLock(tmp_path / "agent.lock")
    second = InstanceLock(tmp_path / "agent.lock")

    assert first.acquire() is True
    assert second.acquire() is False

    first.release()
    assert second.acquire() is True
    second.release()
