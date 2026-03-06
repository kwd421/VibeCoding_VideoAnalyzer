from dataclasses import dataclass, field, asdict
from typing import List, Optional, Any

@dataclass
class AnalysisSettings:
    """Strongly typed options for the Transcription Engine."""
    device_mode: str = "auto"
    beam_size: int = 5
    use_denoise: bool = False
    use_dominant: bool = False
    language: Optional[str] = "ko"
    vad_threshold: float = 0.35
    min_silence_ms: int = 2000
    speech_pad_ms: int = 250
    use_word_timestamps: bool = True
    use_whisper_vad: bool = True
    use_silero_vad: bool = True
    use_whisperx_align: bool = False  # WhisperX forced alignment 사용 여부
    remove_punctuation: bool = False

@dataclass
class TranscriptWord:
    """Strongly typed word block data."""
    word: str
    s: float
    e: float

    # [시니어 헬퍼] 기존 딕셔너리 기반 코드의 안정적 하위 호환성을 위한 편의 메서드 임시 유지
    def __getitem__(self, key: Any) -> Any:
        if not isinstance(key, str): raise KeyError(key)
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)
        
    def __setitem__(self, key: str, value: Any):
        setattr(self, key, value)
        
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
        
    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

@dataclass
class TranscriptSegment:
    """Strongly typed subtitle segment data."""
    s: float
    e: float
    t: str
    words: List[TranscriptWord] = field(default_factory=list)

    # [시니어 헬퍼] 기존 딕셔너리 기반 코드의 안정적 하위 호환성을 위한 편의 메서드 임시 유지
    def __getitem__(self, key: Any) -> Any:
        if not isinstance(key, str): raise KeyError(key)
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)
        
    def __setitem__(self, key: str, value: Any):
        setattr(self, key, value)
        
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)
        
    def pop(self, key: str, default: Any = None) -> Any:
        if not hasattr(self, key):
            return default
        val = getattr(self, key)
        if key == 'words':
            self.words = []
        else:
            setattr(self, key, default)
        return val

    def to_dict(self):
        return asdict(self)
