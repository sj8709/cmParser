"""
포맷별 추출기 공통 인터페이스.

신규 포맷 추가 시 본 인터페이스만 구현하면 core(classifier/normalizer/validator) 변경 없음.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from chaekmu_parser.models import RawDocument


class BaseExtractor(ABC):

    @property
    @abstractmethod
    def format_name(self) -> str:
        """포맷 식별자 ('docx', 'hwp', 'pdf')."""

    @abstractmethod
    def can_handle(self, file_path: Path) -> bool:
        """파일 확장자/시그니처 기반 처리 가능 여부."""

    @abstractmethod
    def extract(self, file_path: Path) -> RawDocument:
        """
        원본 파일 -> RawDocument.

        규칙:
          - 모든 테이블의 셀 텍스트 + bold 속성 + 중첩 테이블을 원본 그대로 보존
          - 테이블 유형 분류는 하지 않음 (classifier 담당)
          - 가공/정규화 금지 (normalizer 담당)
        """
