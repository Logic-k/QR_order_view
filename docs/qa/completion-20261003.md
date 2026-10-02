# QR 완료 검증 기록 · 2026-10-03

대상 브랜치: `codex/qr-completion-20261003`. 기준 HEAD: `e53f3087ab490d12104fbbd52e1ba8971d77e7cb`.

기존 로컬 HTML 분리·반응형 UI 작업을 보존하고 관리자 보호, 입력·저장 오류 처리, 데이터 경로·백업·복구를 보완했습니다. 과거 `REVIEW.md`와 구분되는 이번 실행 결과입니다.

## 실행 환경과 결과

Windows에서 uv의 CPython 3.12.13, Flask 3.1.3, pytest 9.1.1을 사용했습니다. 기본 시스템 Python의 다른 Flask 버전과 구분합니다. 브라우저는 Playwright로 실행한 Microsoft Edge이며 휴대폰·태블릿 크기를 에뮬레이션했습니다.

| 검증 | 이번 결과 | 범위 |
|---|---|---|
| Python 회귀 테스트 | **82 passed in 28.00s** | Flask HTTP + 실제 임시 SQLite + 백업 CLI |
| 브라우저 | **19개 흐름 통과, JS 오류 0** | 클릭·터치·주문·관리·삭제·실패 안내·반응형 |
| basedpyright | **0 errors, 0 warnings, 0 notes** | `app.py`, `db_tools.py` |
| pip-audit | **No known vulnerabilities found** | 최종 `requirements.txt`의 해결된 의존성 |
| 정적 확인 | 통과 | `git diff --check`, 검증기 Node 구문 검사 |

초기 의존성 감사에서 Flask 3.0.0·Gunicorn 21.2.0의 공개 권고를 확인했습니다. 최종 의존성은 Flask 3.1.3·Gunicorn 23.0.0입니다. Windows 실행은 Flask 개발 서버 기준이며 **실제 Gunicorn 실행 검증과 구분합니다.**

## 기능과 오류 검증

기존 14개 음료와 `/order?seat=` 자리 계약, `A-7` 문자열 자리, HTML escape, 1~12번 지도를 확인했습니다. 빈 자리·제어문자·32자 초과 자리, 비메뉴 음료, 잘못되거나 너무 깊은 JSON, 유효하지 않은 삭제 ID를 거부합니다. 지도 밖 자리와 비표준 기존 음료는 저장값을 보존하고 원문으로 표시합니다.

관리자 4개 경로의 미인증 401, 비밀번호 누락 503, 잘못된 비밀번호, Unicode 인증, 캐시 금지, CSRF 누락·변조 403, 비밀번호 변경 시 이전 토큰 무효를 확인했습니다.

브라우저 19개 결과: 관리자 무인증 거부·CSRF 거부·비정상 입력 거부, 휴대폰 320·360·390·430px, 고객 터치 주문·중복 제출 잠금, 직원 마스터 입력·단건 삭제, 태블릿 768×1024·820×1180·1024×768·1180×820, 고객 HTTP·연결 실패, 직원 전체 삭제·빈 상태·실패 안내, JavaScript 오류 없음입니다. 태블릿은 12개 자리와 가상 주문 15건을 표시합니다.

광고 요청은 테스트 대역으로 처리했습니다. 광고 사업자 실제 연동이나 모든 실물 휴대폰 브라우저의 성능을 검증했다는 뜻은 아닙니다.

## 데이터·백업·복구

작업 디렉터리를 바꾸어도 같은 설정 DB에 저장되는지 확인했습니다. SQLite 파일을 접근 불가능하게 만든 경우 성공 대신 503을 반환합니다.

가상 DB에서 온라인 백업을 만든 뒤 원본을 제거하고 새 DB로 복구하여 ID·자리·음료·상태가 동일한지 확인했습니다. 목적지 덮어쓰기 거부, 없는 원본에서 빈 DB를 만들지 않음, 손상된 백업 거부, 다른 스키마 거부도 확인했습니다. 운영 `app.db`와 실제 주문은 사용하지 않았습니다.

## 재현

```powershell
uv run --with Flask==3.1.3 --with pytest python -m pytest tests -q
uv run --with Flask==3.1.3 --with basedpyright basedpyright app.py db_tools.py
uvx pip-audit -r requirements.txt --progress-spinner off
$env:QR_PLAYWRIGHT_MODULE = '<playwright 모듈 절대 경로>'
uv run --with Flask==3.1.3 node tests/verify-completion.cjs '<결과 폴더>'
```

Python 테스트는 앱 import 전에 임시 DB·테스트 인증을 설정합니다. 브라우저 검증기는 자신이 만든 임시 DB·루프백 서버만 사용하고 종료 시 정리합니다. Windows 임시 폴더 정리 문제가 한 번 발견되어 자신이 시작한 서버 프로세스 트리 종료와 짧은 파일 정리 재시도를 적용했습니다.

## 미실행 표면과 운영 한계

Ubuntu GitHub Actions의 실제 Gunicorn 시작·주문·인증·CSRF·백업 복구는 워크플로로 구성했으나 이 로컬 기록 시점에는 실행 결과가 없습니다. 실제 Render 배포·운영 DB 추출·영속 디스크 이전·재시작 복구도 실행하지 않았습니다. 운영 배포본과 이번 소스의 상태는 다릅니다.

Render Free 웹 인스턴스의 로컬 SQLite에는 영속성 보장이 없습니다. 절대 경로 설정만으로 해결되지 않습니다. 영속 저장 구성과 검증된 기존 데이터 추출·복구 수단을 준비한 뒤 운영 반영해야 합니다. 자세한 절차와 다른 운영 한계는 README에 기록했습니다.
