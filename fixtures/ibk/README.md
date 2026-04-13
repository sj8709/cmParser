# IBK저축은행 fixture

Phase 1 E2E 회귀 테스트 기준 샘플.

## 필요 파일

| 파일 | 용도 | 출처 |
|---|---|---|
| `input.docx` | 원본 DOCX | IBK저축은행 책무기술서 통합본 |
| `expected.json` | 기대 출력 (통일 JSON) | 기존 Java 파서 결과를 덤프하여 고정 |
| `expected.xlsx` | 기대 XLSX (선택) | Java 파서 입력과 동일한지 확인용 |

## 수급 지침

1. `input.docx`를 여기에 복사 (커밋하지 않음 - `.gitignore` 설정됨)
2. 기존 ICR 파이프라인으로 해당 DOCX를 처리한 결과 JSON을 `expected.json`에 저장
3. `tests/test_ibk_e2e.py`가 이 fixture를 기준으로 회귀 검증

## 주의

- 원본 파일(.docx/.hwp/.pdf/.xlsx)은 저작권/기밀 이슈로 **커밋 금지**
- `expected.json`은 민감정보 포함 시 마스킹 후 커밋 (임원명 등)
