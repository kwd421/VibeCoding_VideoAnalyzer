import re
from typing import Optional

class TextSanitizer:
    """[시니어 최적화] AI 환각 현상(Hallucination) 필터링 및 안정성 검증기"""
    
    @staticmethod
    def clean_special_chars(text: str) -> str:
        """무의미한 텍스트 부호들을 제거하여 순수 텍스트 길이를 반환하기 위한 정제"""
        return text.replace("쩜", "").replace("점", "").replace(".", "").replace(",", "").replace(" ", "").replace("~", "").replace("!", "").replace("?", "")
        
    @staticmethod
    def is_valid_language(text: str, cleaned_text: str, selected_lang: Optional[str]) -> bool:
        """[CRITICAL] Strict Language Bounding: 지정된 언어 영역 이외의 문장은 폐기"""
        if len(cleaned_text) < 1 and len(text) > 0:
            return False
            
        if selected_lang == "ko" and re.search(r'[가-힣]', cleaned_text) is None:
            return False
            
        return True
        
    @staticmethod
    def is_youtube_outro_hallucination(text: str, cleaned_text: str) -> bool:
        """고질적인 유튜브 아웃트로 환각 현상 감지 및 차단"""
        outro_phrases = ["시청해주셔서 감사합니다", "다음 영상에서 만나요", "구독과 좋아요", "시청해 주셔서 감사합니다"]
        if any(h in text for h in outro_phrases):
            if len(cleaned_text) < 15:
                return True
        return False
        
    @staticmethod
    def is_looping_hallucination(cleaned_text: str) -> bool:
        """[핵심] 고비율 반복 문자 ('뀨오오오오' 등) 발견 시 True 반환"""
        if len(cleaned_text) > 4:
            unique_chars = len(set(cleaned_text))
            repeat_ratio = unique_chars / len(cleaned_text)
            
            # 글자 수가 7글자가 넘는데 종류가 3개 이하이거나, 전체 길이 대비 고유 문자 비율이 30% 이하라면 환각 간주
            if (unique_chars <= 3 and len(cleaned_text) >= 7) or (repeat_ratio <= 0.35 and len(cleaned_text) >= 9):
                return True
                
        return False
