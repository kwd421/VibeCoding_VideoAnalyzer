from dataclasses import dataclass


@dataclass(frozen=True)
class BackendOption:
    mode: str
    label: str
    backend: str
    description: str


BACKEND_OPTIONS = (
    BackendOption("auto", "자동 선택 (auto)", "auto", "사용 가능한 백엔드를 자동으로 선택합니다."),
    BackendOption("cuda", "NVIDIA CUDA", "cuda", "CUDA 가능한 환경에서 faster-whisper를 사용합니다."),
    BackendOption("mps", "Apple Metal (MPS)", "mps", "transformers Whisper를 Apple GPU(Metal)로 실행합니다."),
    BackendOption("coreml", "Apple Core ML (실험)", "coreml", "whisper.cpp/Core ML 실험용 슬롯입니다."),
    BackendOption("cpu_25", "CPU (25%)", "cpu", "CPU 코어 25% 정도를 사용합니다."),
    BackendOption("cpu_50", "CPU (50%)", "cpu", "CPU 코어 50% 정도를 사용합니다."),
    BackendOption("cpu_75", "CPU (75%)", "cpu", "CPU 코어 75% 정도를 사용합니다."),
    BackendOption("cpu", "CPU (100%)", "cpu", "필요한 경우 CPU를 최대한 사용합니다."),
)

BACKEND_LABELS = [option.label for option in BACKEND_OPTIONS]
LABEL_TO_MODE = {option.label: option.mode for option in BACKEND_OPTIONS}
MODE_TO_OPTION = {option.mode: option for option in BACKEND_OPTIONS}


def mode_from_label(label: str) -> str:
    return LABEL_TO_MODE.get(label, "cpu_50")


def option_from_mode(mode: str) -> BackendOption:
    return MODE_TO_OPTION.get(mode, MODE_TO_OPTION["cpu_50"])


def backend_kind(mode: str) -> str:
    return option_from_mode(mode).backend


def uses_cpu_threads(mode: str) -> bool:
    return backend_kind(mode) in {"auto", "cpu", "cuda"}

