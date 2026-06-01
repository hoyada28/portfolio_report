# 데일리 포트폴리오 리포트 (GitHub Actions)

매일 **한국시간 오전 8시**에 보유·관심 종목의 시세와 종목별 최신 뉴스(최근 24시간, 종목당 최대 3개)를
자동으로 모아 **Gmail로 발송**합니다. 무료(공개 저장소 기준)로 클라우드에서 실행됩니다.

- 가격: `pykrx`(한국) / `yfinance`(미국)
- 뉴스: Google 뉴스 RSS(노출순위+최신순) → 영문 제목은 Google 번역으로 한글화
- 발송: Gmail SMTP

---

## 설정 순서 (약 10분)

### 1. GitHub 저장소 만들기
1. GitHub 로그인 → **New repository** → 이름 예: `portfolio-report` → 생성
   (공개/비공개 모두 무료 한도 내. 공개면 분 제한 없음)
2. 이 폴더의 파일을 그대로 업로드(드래그&드롭 또는 git push):
   ```
   fetch_and_report.py
   requirements.txt
   .github/workflows/daily-report.yml
   ```
   > `.github/workflows/` 폴더 구조를 반드시 유지하세요.

### 2. Gmail 앱 비밀번호 발급
일반 비밀번호로는 안 되고, **앱 비밀번호**가 필요합니다.
1. Google 계정 → **보안** → **2단계 인증**을 먼저 켭니다(필수).
2. https://myaccount.google.com/apppasswords 접속
3. 앱 이름 아무거나(예: `portfolio`) 입력 → 생성 → **16자리 비밀번호** 복사
   (공백 없이 붙여서 사용)

### 3. GitHub 시크릿 등록
저장소 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**
아래 3개를 등록합니다:

| 이름 | 값 |
|---|---|
| `GMAIL_USER` | 발신용 Gmail 주소 (예: `you@gmail.com`) |
| `GMAIL_APP_PASSWORD` | 위에서 발급한 16자리 앱 비밀번호 |
| `MAIL_TO` | 받을 주소 (생략 시 `GMAIL_USER`로 발송) |

### 4. 동작 테스트
저장소 → **Actions** 탭 → `Daily Portfolio Report` → **Run workflow** 버튼으로 즉시 실행.
1~2분 뒤 메일이 오는지 확인하세요. 로그는 Actions 실행 화면에서 볼 수 있습니다.

이후에는 매일 오전 8시(KST)에 자동 실행됩니다.

---

## 자주 묻는 점

**비용** — 공개 저장소는 Actions 무료. 비공개도 무료 플랜 월 2,000분 제공이고 이 작업은 월 30~60분 수준이라 무료 한도 내입니다.

**한국 종목이 전일 종가로 나와요** — 한국 증시는 09:00 개장이라 08:00 리포트는 전일 종가가 정상입니다. 장중가를 원하면 `.github/workflows/daily-report.yml`의 cron을 `0 1 * * *`(=10:00 KST) 등으로 바꾸세요. (cron은 UTC 기준: KST−9시간)

**뉴스가 "없음"으로 나와요** — 해당 종목에 최근 24시간 내 기사가 없을 때입니다. 시간 범위를 늘리려면 `fetch_and_report.py`의 `within_hours` 값을 조정하세요.

**시세가 안 맞아요(조회실패)** — pykrx가 가끔 KRX 점검시간에 실패할 수 있습니다. 재실행하면 대부분 해결됩니다.

**뉴스 중요도** — 이 무료 버전은 Google 뉴스의 노출순위+최신순을 "중요도"로 사용합니다. 사람이/AI가 직접 검증하는 방식은 아닙니다. 더 정교한 선별을 원하면 Claude API 연동(별도 과금) 버전으로 업그레이드할 수 있습니다.

---

## 종목 수정 방법
`fetch_and_report.py` 상단의 `HOLDINGS` / `WATCHLIST` 리스트에서
`(이름, 코드, 시장구분, 뉴스검색어, 언어)` 형식으로 추가·삭제하면 됩니다.
- 시장구분: `KR_STOCK`(한국 주식) / `KR_ETF`(한국 ETF) / `US`(미국)
- 언어: `ko`(한글 뉴스) / `en`(영문→한글 번역)
