# QR Order View

새 브랜치는 의존성 보안 점검에서 발견한 기존 Flask·Gunicorn 권고에 대응하여 Flask 3.1.3·Gunicorn 23.0.0으로 고정합니다. 로컬 Windows 검증은 Flask 개발 서버 기준입니다. Ubuntu GitHub Actions는 실제 Gunicorn 시작·주문·인증·CSRF 점검을 수행하도록 구성했으며 CI 실행 결과와 실제 Render 환경 검증은 별도 확인해야 합니다.

Flask·SQLite 기반 QR 주문 웹입니다. 고객은 기존 `/order?seat=1` 주소에서 음료를 고르고, 직원은 `/admin`에서 자리별 주문을 확인·입력·삭제합니다. 실제 운영 경험이 있는 개인 프로젝트이며 고객 외주 납품 실적과는 구분합니다.

## 현재 완료 범위

- 기존 로컬 템플릿·음료 사진·자리 지도·반응형 화면 분리 작업을 유지했습니다.
- 고객 QR 주소와 기존 14개 메뉴의 저장값, SQLite `orders(id, seat, drink, status)` 구조를 유지합니다.
- 관리자 4개 경로에 HTTP Basic 인증을 적용하고 비밀번호가 없으면 접근을 닫습니다.
- 관리자 변경 요청은 인증과 페이지의 CSRF 토큰이 모두 있어야 처리됩니다.
- 잘못된 입력과 SQLite 장애는 실패 응답을 반환하며 화면에 처리 확인 안내를 표시합니다.
- DB 경로를 작업 디렉터리와 무관하게 고정할 수 있고, 백업·검증·새 파일 복구 도구를 제공합니다.

이 브랜치의 기능은 별도 DB·가상 주문으로 검증했습니다. **운영 Render에는 아직 배포하지 않았습니다.** 기존 `REVIEW.md`·`evidence/revision*`는 과거 UI 검증 기록이며 이번 검증과 구분합니다.

## 설치와 로컬 실행

Python 3.10 이상과 [uv](https://docs.astral.sh/uv/)를 사용합니다. 프로젝트 디렉터리에서 실행하세요.

```powershell
uv venv .venv
uv pip install -r requirements.txt
$env:QR_ADMIN_USER = 'admin'
$env:QR_ADMIN_PASSWORD = '<직원 전용의 긴 무작위 비밀번호>'
$env:QR_DATABASE_PATH = Join-Path (Get-Location) 'app.db'
$env:FLASK_DEBUG = '0'
uv run python app.py
```

고객 시연: `http://127.0.0.1:5000/order?seat=1`

직원 시연: `http://127.0.0.1:5000/admin`에서 브라우저 인증 창에 설정한 계정·비밀번호를 입력합니다. 브라우저는 Basic 인증을 기억하므로 공용 기기에서는 사용 후 모든 브라우저 창을 닫고 전용 직원 프로필을 사용하세요.

`.env.example`는 항목 설명용입니다. 앱은 `.env`를 자동으로 읽지 않으며 환경변수를 직접 설정해야 합니다. 실제 비밀번호·DB·백업은 Git에 넣지 마세요. 공개 서비스의 관리자 접근은 HTTPS로만 사용합니다.

## 설정

| 환경변수 | 기본값 | 용도 |
|---|---|---|
| `QR_ADMIN_USER` | `admin` | 직원 계정. 빈 문자열이면 관리자 503 |
| `QR_ADMIN_PASSWORD` | 없음 | 필수. 없으면 관리자 503. 변경하면 이전 CSRF 토큰 무효 |
| `QR_DATABASE_PATH` | `app.py`와 같은 디렉터리의 `app.db` | 운영에서는 영속 저장소의 절대 경로 |
| `FLASK_DEBUG` | 꺼짐 | 로컬에서만 `1`로 디버그 실행 |

`QR_DATABASE_PATH`는 앱 시작 시 결정됩니다. 경로 변경 후에는 서버를 재시작하세요. 환경변수를 생략하면 기존 앱 폴더의 `app.db`를 계속 사용하며 새 스키마로 변환하지 않습니다. 설정한 경로의 부모 디렉터리는 미리 존재해야 합니다. 빈 DB 경로 값은 사용하지 마세요.

## API와 호환성

| 경로 | 메서드 | 입력과 결과 |
|---|---|---|
| `/order?seat=1` | GET | 주문 화면. 자리 기본값 `1` |
| `/order?seat=1` | POST | JSON `{"drink":"아메리카노(HOT)"}` → 주문 저장 |
| `/order-complete?seat=1` | GET | 기존 완료 화면 |
| `/admin` | GET | 직원 인증 후 전체 목록과 CSRF meta 태그 |
| `/master-order` | POST | 인증·CSRF + `{"seat":"2","drink":"캐모마일(HOT)"}` |
| `/delete-order` | POST | 인증·CSRF + 양의 정수 또는 숫자 문자열 `{"id":"1"}` |
| `/delete-all-orders` | POST | 인증·CSRF. 별도 JSON 본문 불필요 |

자리 지도는 기존 1~12번입니다. 기존 `A-7`처럼 문자열을 사용하는 QR도 호환되도록 자리는 비어 있지 않은 출력 가능한 1~32자로 제한하고 HTML에 표시할 때 escape 합니다. 지도 밖 기존 자리 기록도 직원 상세 목록에 표시합니다. 메뉴는 화면에 있는 기존 14개 값만 허용하며 임의 음료 문자열은 거부합니다.

직원 UI는 meta 태그의 토큰을 `X-CSRF-Token` 헤더에 자동으로 보냅니다. 외부 직원 API 도구도 인증된 `/admin`에서 토큰을 가져와 같은 헤더로 보내야 합니다. 비밀번호 교체 후 열린 페이지는 새로고침하세요.

오류 계약: 잘못된 자리·메뉴·JSON·ID는 400, 미인증은 401, 잘못된/누락 CSRF는 403, 관리자 설정 누락·SQLite 처리 실패는 503입니다. 요청 본문은 최대 8 KiB입니다. 저장 실패 응답을 받았거나 연결이 끊겼다면 재주문 전에 직원이 목록을 확인해야 합니다. 서버 성공 후 응답만 유실되는 경우를 자동으로 판별하는 기능은 아직 없습니다.

## Render 배포 재현과 데이터 보존

확인된 기존 설정은 배포 브랜치 `main`, Free 웹 인스턴스, 빌드 `pip install -r requirements.txt`, 시작 `gunicorn -w 1 -b 0.0.0.0:10000 app:app`, 커밋 시 자동 배포입니다. PR 프리뷰는 꺼져 있습니다. 새 코드와 이 설정의 운영 반영은 이번 작업에 포함하지 않았습니다.

Render Free 웹 서비스의 로컬 파일시스템은 영속 저장소가 아닙니다. **DB 경로를 절대 경로로 바꾸는 것만으로 Free 인스턴스의 주문 데이터가 영구 보존되지는 않습니다.** [Render Free 서비스 안내](https://render.com/docs/free), [영속 디스크 안내](https://render.com/docs/disks)를 확인하세요. Workspace의 Hobby 표기와 웹 인스턴스의 Free 유형은 별개입니다.

SQLite를 계속 쓸 경우 영속 디스크를 지원하는 웹 인스턴스에서 디스크를 `/var/data`에 연결하고 `QR_DATABASE_PATH=/var/data/app.db`를 설정해야 합니다. 이 경로는 선택 예시이며 기존 Free 설정에는 디스크가 없습니다. 별도 관리형 DB를 쓰는 선택은 저장 계층 변경과 추가 검증이 필요합니다.

운영 반영 순서:

1. 현재 살아 있는 DB의 추출·백업 수단을 먼저 확보하고 백업을 검증합니다. Free 서비스의 Shell/SSH 제한도 확인해야 하며, 이번 작업에서 운영 DB 추출은 수행하지 않았습니다.
2. 영속 디스크 또는 다른 영속 DB 구성을 확정합니다. 새 경로에서 빈 DB가 만들어졌다는 이유로 기존 주문을 복구했다고 판단하지 마세요.
3. 별도 환경에서 백업 복구, 고객 주문, 관리자 인증·입력·삭제, 재시작 후 저장 유지까지 검증합니다.
4. 환경변수·비밀번호를 Render 설정에 넣고 실제 배포 브랜치와 시작 명령을 기록합니다.
5. 작업 시간과 되돌리기 버전을 정한 뒤 운영 배포를 수행합니다. 이미 활성 주문이 있다면 사용자 확인과 백업을 먼저 마칩니다.

`Procfile.txt`를 자동으로 인식한다고 가정하지 않고 Render의 시작 명령을 명시합니다. 이 앱은 단일 인스턴스 SQLite 기준입니다. 여러 인스턴스를 독립 로컬 DB로 실행하면 주문이 갈라지므로 운영 형태를 변경할 때는 저장 계층을 다시 설계해야 합니다.

## 백업·검증·복구

실행 중인 SQLite의 단순 파일 복사 대신 온라인 백업 API를 사용합니다. `db_tools.py`는 앱을 import 하지 않고 지정한 파일만 다룹니다. 원본은 읽기 전용으로 열고 무결성과 주문 스키마를 확인합니다. 대상 파일이 이미 있으면 작업을 거부합니다.

```powershell
uv run db_tools.py backup 'C:\data\app.db' 'C:\backups\orders-20261003.db'
uv run db_tools.py verify 'C:\backups\orders-20261003.db'
```

Linux/Render 환경에서 실행할 수 있는 경우:

```bash
python db_tools.py backup /var/data/app.db /var/data/backups/orders-20261003.db
python db_tools.py verify /var/data/backups/orders-20261003.db
```

백업 폴더는 미리 만들고, 생성한 백업을 동일 인스턴스 밖의 접근 제한 저장소에도 보관하세요. 같은 디스크 안의 백업만으로는 디스크 장애를 복구할 수 없습니다. 현재 Free 운영 DB에 이 절차를 적용했다는 의미는 아닙니다.

복구는 서버를 멈춘 뒤 새 DB 파일로 생성합니다.

```powershell
uv run db_tools.py restore 'C:\backups\orders-20261003.db' 'C:\data\app-restored.db'
uv run db_tools.py verify 'C:\data\app-restored.db'
$env:QR_DATABASE_PATH = 'C:\data\app-restored.db'
uv run python app.py
```

기존 DB와 그 `-wal`·`-shm` 파일을 임의로 덮어쓰지 마세요. 새 파일로 복구한 다음 앱 설정을 새 경로로 바꾸고 목록·주문 등록을 확인합니다. 서버가 새 DB로 실행 중일 때 다시 복구하지 않습니다. 실패 시 서버를 멈추고 보존한 기존 DB 경로와 검증된 코드 버전으로 되돌립니다. 이전 코드에 관리자 보호가 없다면 접근을 제한한 상태에서 되돌리기를 수행하세요.

## 검증 실행

```powershell
uv run --with Flask==3.1.3 --with pytest python -m pytest tests -q
```

모든 Python 테스트는 앱 import 전에 임시 DB 경로와 테스트 전용 관리자 비밀번호를 지정합니다. 실제 `app.db`를 사용하지 않습니다. 테스트에는 기존 14개 메뉴, QR 자리 표시·escaping, 주문 입력·삭제, 인증·CSRF, 오류 처리, 작업 디렉터리 변경, 백업·복구가 포함됩니다.

새 브라우저 검증기는 직접 임시 DB와 로컬 서버를 만들고 종료 시 정리합니다. 운영 URL을 입력받지 않습니다. Playwright와 Microsoft Edge가 있는 환경에서:

```powershell
$env:QR_PLAYWRIGHT_MODULE = '<playwright 모듈의 절대 경로>'
uv run --with Flask==3.1.3 node tests/verify-completion.cjs '<검증 결과 폴더>'
```

고객 휴대폰 320·360·390·430px와 직원 태블릿 768×1024·820×1180·1024×768·1180×820, 실제 클릭 주문·마스터 입력·삭제·전체 삭제·실패 안내·중복 제출 잠금을 확인합니다. 광고 요청은 테스트 대역으로 처리하며 광고 사업자와 실제 연동한 검증은 아닙니다. 기존 `verify-*.cjs`는 당시 별도 서버를 대상으로 한 UI 실험 기록입니다. 현재 완료 검증은 임시 서버를 직접 소유하는 `verify-completion.cjs`를 사용합니다.

## 3분 시연 순서

1. 7번 QR 주문 화면에서 음료를 선택해 접수하고 완료 화면의 자리 번호를 확인합니다.
2. 직원 화면에서 7번 주문을 확인합니다.
3. 8번 마스터 주문을 입력하고 단건 삭제합니다.
4. 가상 주문만 있는 시연 DB에서 전체 삭제·빈 상태를 보여줍니다.
5. 백업 파일을 새 경로로 복구하여 주문 기록이 재현되는지 보여줍니다.

운영 주문을 사용한 삭제 시연은 하지 않습니다. 직원용 비밀번호와 실제 DB를 공개 영상·스크린샷·GitHub에 포함하지 마세요.

## 남은 운영 한계

Free 배포의 영속 저장·운영 DB 추출·재시작 복구는 아직 검증하지 않았습니다. 공유 Basic 계정에는 직원별 권한·감사 로그·로그인 시도 제한이 없습니다. 공개 고객 주문에는 악용 방지, 요청별 idempotency, 결제·재고·주문 상태 변경 기능이 없습니다. 이 항목들은 현재 핵심 흐름의 검증과 별도로 운영 요구에 따라 범위를 정해야 합니다. 음료 이미지 출처와 기존 광고 구성은 `static/drinks/LICENSES.html`, `templates/photo_credits.html`에서 확인합니다.
