import pytest


@pytest.fixture(autouse=True)
def task_bus(monkeypatch):
    """Tests never touch a broker. The list records which tasks the code tried to start."""
    calls: list[tuple] = []

    def fake_send(name, *args, **kwargs):
        calls.append((name, args, kwargs))
        return True

    monkeypatch.setattr("core.tasks_bus.send_task_by_name", fake_send)
    return calls