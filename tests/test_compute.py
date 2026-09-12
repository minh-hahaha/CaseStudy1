"""Compute-shim tests. Proves src/ is importable with neither `spaces` nor torch."""

from src import compute


def test_gpu_is_a_pass_through_when_spaces_is_absent():
    # Arrange: `spaces` is not installed in CI or on a dev Mac.
    assert compute._spaces_module() is None

    # Act
    @compute.gpu(duration=30)
    def double(x):
        return x * 2

    # Assert: behavior and identity are untouched.
    assert double(21) == 42


def test_is_zero_gpu_is_false_without_spaces():
    assert compute.is_zero_gpu() is False


def test_get_device_reports_cuda_on_zero_gpu_without_importing_torch(monkeypatch):
    # Arrange: stand in for the `spaces` module the Space would provide.
    monkeypatch.setattr(compute, "_spaces_module", lambda: object())

    # Act / Assert
    assert compute.get_device() == "cuda"


def test_gpu_delegates_to_spaces_when_available(monkeypatch):
    # Arrange
    recorded = {}

    class FakeSpaces:
        @staticmethod
        def GPU(duration):
            recorded["duration"] = duration
            return lambda fn: fn

    monkeypatch.setattr(compute, "_spaces_module", lambda: FakeSpaces)

    # Act
    compute.gpu(duration=90)(lambda: None)

    # Assert
    assert recorded["duration"] == 90


def test_is_on_space_follows_the_space_id_env_var(monkeypatch):
    monkeypatch.delenv("SPACE_ID", raising=False)
    assert compute.is_on_space() is False

    monkeypatch.setenv("SPACE_ID", "minh-hahaha/CaseStudy1")
    assert compute.is_on_space() is True
