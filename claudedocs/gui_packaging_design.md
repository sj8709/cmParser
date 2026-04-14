# GUI + 배포 설계 — `chaekmu-parser`

> 용도: 비개발자에게 "이런 게 있다"로 파일 전달 배포. 업로드 → 변환 → 다운로드 단순 UX.
> 작성: 2026-04-14

## 1. 결정

| 항목 | 선택 | 기각안 |
|---|---|---|
| UI 프레임워크 | **customtkinter** (tkinter 위 현대적 래퍼) | Streamlit(브라우저 개입), PyQt(과투자), PyWebview(HTML 개발 필요), 기본 tkinter(외관 낡음) |
| 패키징 | **PyInstaller `--onedir`** | `--onefile`(시작 5~15초 지연), Nuitka(빌드 복잡) |
| 아이콘 | 1차 생략 (Python 기본), 이후 무료 아이콘 교체 가능 구조 | — |
| 번들 크기 목표 | **100~120MB** | — |

**설계 원칙**: UI는 얇은 래퍼. 핵심 파이프라인(`chaekmu_parser`)은 순수 Python 라이브러리 유지. tkinter/PyInstaller는 나중에 Streamlit/exe/웹 등 어떤 배포 경로로 바뀌어도 재활용 가능하도록 import 계층 분리.

## 2. 파일 구조

```
src/
├─ chaekmu_parser/          # 기존 core (UI 무관)
└─ chaekmu_parser_gui/      # 신규 — UI 전용
    ├─ __init__.py
    ├─ __main__.py          # `python -m chaekmu_parser_gui` 엔트리
    ├─ app.py               # MainWindow 클래스
    ├─ workers.py           # 파이프라인 백그라운드 실행(threading)
    └─ assets/
        └─ icon.ico
build/
└─ gui.spec                 # PyInstaller 스펙
scripts/
└─ build_exe.ps1            # 빌드 자동화
```

## 3. UI 설계 (tkinter)

### 레이아웃

```
┌───────────────────────────────────────────┐
│  📋 책무기술서 파서 v0.1.0               │
├───────────────────────────────────────────┤
│                                           │
│  📄 입력 DOCX:                            │
│  [경로 입력란............] [찾아보기...]  │
│                                           │
│  💾 저장 위치:                            │
│  [기본: ~/Desktop........] [변경...]      │
│                                           │
│  ┌─────────────────────────┐              │
│  │    ▶  변환 실행          │              │
│  └─────────────────────────┘              │
│                                           │
│  ───── 진행 상황 ─────────────────────    │
│  ✓ 추출 완료 (27 테이블)                  │
│  ✓ 정규화 완료 (임원 9명)                 │
│  ⚠ 리뷰 필요 2건 (클릭하여 상세 확인)     │
│  ✓ XLSX 저장: IBK_output_20260414.xlsx    │
│                                           │
│  [ 결과 폴더 열기 ]  [ 다른 파일 처리 ]   │
└───────────────────────────────────────────┘
```

### 위젯 구성

| 위젯 | 역할 |
|---|---|
| `Entry` + `Button` | 입력 DOCX 경로 + 파일 대화상자 (filedialog.askopenfilename) |
| `Entry` + `Button` | 출력 폴더 경로 + 디렉터리 대화상자 (filedialog.askdirectory) |
| `Button` | 변환 실행 (실행 중 비활성화) |
| `ttk.Progressbar` | 진행률 (indeterminate) |
| `scrolledtext.ScrolledText` | 로그/결과 (읽기 전용, 색상 태그로 ✓⚠❌ 구분) |
| `Button` (2개) | 결과 폴더 열기 (`os.startfile`), 초기화 |

### 상태 전이

```
IDLE
 ├─ [파일 선택] → VALID (입력 경로 있음)
 └─ VALID
     ├─ [변환 실행] → RUNNING
     └─ RUNNING
         ├─ 성공 → DONE (폴더 열기 활성화)
         └─ 실패 → ERROR (상세 메시지 + 로그 저장 버튼)
```

### 오류 처리

- 모든 예외는 **친화적 메시지**로 번역 (traceback 직노출 금지)
- 상세 로그는 `%LOCALAPPDATA%\chaekmu-parser\logs\YYYY-MM-DD.log`에 자동 기록
- UI에 `[로그 파일 열기]` 버튼 제공해서 사용자가 개발자에게 전달 가능

## 4. 백그라운드 실행 (반응성 확보)

- tkinter 메인루프는 단일 스레드. 파이프라인이 수 초 걸릴 수 있으므로 **`threading.Thread`로 분리**
- 워커 스레드 → 메인 스레드 통신은 **`queue.Queue`**로 (UI 업데이트는 항상 메인 스레드에서)
- `root.after(100, poll_queue)`로 폴링

```python
# workers.py 개요
def run_pipeline(input_path, output_dir, status_queue):
    try:
        status_queue.put(("info", "📄 DOCX 로딩..."))
        raw = DocxExtractor().extract(input_path)
        status_queue.put(("ok", f"✓ 추출 완료 ({len(raw.tables)} 테이블)"))
        parsed = normalize(raw)
        status_queue.put(("ok", f"✓ 정규화 완료 (임원 {len(parsed.executives)}명)"))
        # ... UNKNOWN 경고, XLSX 쓰기, 완료 등
    except Exception as e:
        status_queue.put(("error", f"❌ {type(e).__name__}: {e}"))
        logger.exception("pipeline failed")
```

## 5. PyInstaller 번들 설정

### `build/gui.spec`

```python
# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ["../src/chaekmu_parser_gui/__main__.py"],
    pathex=["../src"],
    binaries=[],
    datas=[
        ("../templates/chaekmu_template.xlsx", "templates"),
    ],
    hiddenimports=["pyhwp", "olefile"],  # pyhwp는 hidden import 필요
    excludes=[
        "pdfplumber", "pdfminer", "pillow", "cryptography",  # Phase 3 PDF 전까지 제외
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="chaekmu-parser",
    console=False,  # GUI only, 콘솔 창 숨김
    icon="../src/chaekmu_parser_gui/assets/icon.ico",
)
coll = COLLECT(exe, a.binaries, a.datas, name="chaekmu-parser")
```

### 번들 크기 최적화

| 조치 | 절감 효과 |
|---|---|
| `pdfplumber`/`cryptography`/`pillow` 제외 | ~40MB (Phase 3 전까지) |
| UPX 압축 (`--upx-dir`) | ~20-30% 추가 |
| `excludes`에 `matplotlib`, `numpy` 추가 확인 | 의존성 트리 검토 |

목표: **80~90MB 폴더 zip**.

### 배포 산출물

```
chaekmu-parser-v0.1.0-win64.zip
├─ chaekmu-parser.exe        # 엔트리
├─ _internal/                # 파이썬 런타임 + 의존성
│   ├─ python313.dll
│   ├─ base_library.zip
│   └─ ...
├─ templates/
│   └─ chaekmu_template.xlsx
└─ 읽어보세요.txt              # 실행 안내 (SmartScreen 경고 포함)
```

## 6. 배포 시 주의 (비개발자 전달용)

### Windows SmartScreen 대응

미서명 exe는 첫 실행 시 "Windows의 PC 보호" 경고가 나옴. 읽어보세요.txt에 다음 안내 필수:

```
📋 실행 방법
1. zip 파일을 C:\chaekmu-parser 같은 경로에 압축 해제
2. chaekmu-parser.exe 더블클릭
3. "Windows의 PC 보호" 경고가 나오면:
   "자세히" 클릭 → "실행" 버튼 클릭

❓ 문의: [개발자 연락처]
🐞 오류 발생 시: 화면의 "[로그 파일 열기]" 버튼으로 로그 첨부 전달
```

장기적으로 사용이 늘어나면 **코드 서명 인증서** 도입 고려 (연 $200~500, 경고 사라짐).

### 설치 불필요 포터블

- `_internal/` 폴더가 같이 있어야 동작. 사용자가 `.exe`만 다른 곳에 복사하면 깨짐
- 메시지: "zip 전체를 한 폴더에 풀어야 합니다"

## 7. 빌드 스크립트

### `scripts/build_exe.ps1`

```powershell
$ErrorActionPreference = "Stop"
cd $PSScriptRoot/..

# 가상환경 활성화
.\.venv\Scripts\Activate.ps1

# 기존 빌드 제거
Remove-Item -Recurse -Force dist, build/chaekmu-parser -ErrorAction SilentlyContinue

# PyInstaller 실행
pyinstaller build/gui.spec --clean --noconfirm

# 사용자용 안내서 복사
Copy-Item "docs/읽어보세요.txt" "dist/chaekmu-parser/"

# zip 패키징
$version = "0.1.0"
Compress-Archive -Path "dist/chaekmu-parser/*" `
    -DestinationPath "dist/chaekmu-parser-v${version}-win64.zip" -Force

Write-Host "✓ Done: dist/chaekmu-parser-v${version}-win64.zip"
```

실행: `pwsh scripts/build_exe.ps1`

## 8. 개발 범위 추산

| 작업 | 예상 시간 |
|---|---|
| tkinter UI 기본 레이아웃 + 이벤트 | 2시간 |
| 백그라운드 워커 + 큐 통신 + 진행률 | 1.5시간 |
| 로그 파일 + 오류 처리 + 친화적 메시지 | 1시간 |
| 리뷰 필요 케이스 표시 (UNKNOWN 건 카운트) | 0.5시간 |
| PyInstaller spec + 빌드 스크립트 + 테스트 빌드 | 2시간 |
| 번들 크기 최적화 + SmartScreen 안내 문서 | 1시간 |
| 아이콘 (icon.ico) + 읽어보세요.txt | 0.5시간 |
| **합계** | **~8~9시간 (1~1.5일)** |

## 9. 향후 확장

이 설계는 다음 진화에 손댈 곳 없음:

- **다중 파일 처리**: UI에 `Listbox` 추가 + 반복 실행. core 수정 없음
- **HWP 지원**(Phase 2): extractor dispatch가 확장자 기반이라 자동 대응
- **진짜 사내 서비스화**: Streamlit으로 UI 교체해도 `chaekmu_parser` 라이브러리 그대로
- **코드 서명 도입**: spec 파일에 서명 hook 추가

## 10. 현 Phase와 관계

- Phase 2(HWP) 진행과 **독립적**: Phase 2 완료 전에 GUI 먼저 배포해도 DOCX만 사용 가능
- Phase 2 완료되면 자동으로 HWP 지원됨 (UI 변경 불필요)
- Phase 3(PDF) 추가 시 PyInstaller spec의 `excludes`에서 `pdfplumber` 제거만 하면 됨

## 11. 확정 사항 (2026-04-14)

- [x] UI 프레임워크 → **customtkinter** (첫인상·현대적 외관 우선, +30MB 허용)
- [x] 처리 모드 → **단일 파일**
- [x] 출력 파일명 → `<input_stem>_output_<YYYYMMDD>.xlsx`
- [x] 아이콘 → 1차 생략 (Python 기본), 이후 무료 아이콘(Flaticon/Icons8 등)으로 교체
- [x] 코드 서명 → 당분간 불필요 (수동 안내 `읽어보세요.txt`로 대응), 사용 규모 커지면 재검토

구현 착수 승인 완료.
