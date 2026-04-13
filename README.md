# 책무기술서 파서 (chaekmu-parser)

금융회사 책무기술서 파일(DOCX / HWP / PDF) -> 통일 JSON -> XLSX 템플릿 변환 파이프라인.

> 본 프로젝트는 ICR 시스템(C:/project/workspace/icr)의 `XlsxTemplateParserServiceImpl.java`와 연동되는 전처리 파이프라인입니다.

---

## 현재 단계

**Phase 1 (진행 중)**: DOCX 지원 — IBK저축은행 샘플 기준 E2E 검증 목표

| Phase | 범위 | 상태 |
|---|---|---|
| 1 | DOCX extractor + classifier + normalizer + xlsx_writer, IBK E2E | 진행 중 |
| 2 | HWP extractor (pyhwp) + variant handlers + 3단계 검증 레이어, 라이나 E2E | 예정 |
| 3 | 파일럿 회사 유입 시 add-on (PDF 포함) | 유입 시 |

---

## 설계 문서 (Desktop/ICR 관련 MD 하위)

- `책무기술서_파이프라인_분석.md` — 최종안 섹션 12/13
- `라벨분류_정규식_명세_v0.1.md` — 분류기/normalizer 규칙

---

## 프로젝트 구조

```
chaekmu-parser/
├── src/chaekmu_parser/
│   ├── models.py              # 통일 데이터 모델 (RawDocument / ParsedDocument)
│   ├── extractors/
│   │   ├── base.py            # 공통 인터페이스 (새 포맷은 여기만 구현)
│   │   ├── docx_extractor.py  # Phase 1
│   │   ├── hwp_extractor.py   # Phase 2
│   │   └── pdf_extractor.py   # Phase 3
│   ├── classifier.py          # 라벨 기반 테이블 유형 분류
│   ├── normalizer.py          # 구조 변이 흡수 -> 통일 JSON
│   ├── validator.py           # 3단계 정합성 검증 (Phase 2)
│   └── xlsx_writer.py         # 통일 JSON -> XLSX 템플릿
├── fixtures/                  # 회귀 테스트용 샘플 (실파일 gitignore)
│   ├── ibk/
│   └── laina/
└── tests/
```

---

## 개발 환경 설정

```powershell
# Windows PowerShell 기준
cd C:\project\workspace\chaekmu-parser
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

---

## 확장 규칙 (핵심)

1. **Core 불변**: `models.py`, `classifier.py`, `normalizer.py`의 인터페이스는 신규 회사 대응을 이유로 변경하지 않음
2. **포맷 추가**: `extractors/` 하위에 `BaseExtractor` 구현체 1개만 추가
3. **회사 변이 발견**: `normalizer.py`의 variant handler 체인에 케이스만 추가 + fixtures에 회귀 샘플 등록
4. **회귀 테스트 필수**: 신규 케이스 추가 시 기존 fixtures 모두 통과 확인
