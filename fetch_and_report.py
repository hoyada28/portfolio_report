#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""매일 아침 포트폴리오 시세 + 종목별 최신 뉴스(24h, 종목당 3개)를 Gmail로 발송."""

import os
import html
import smtplib
import datetime as dt
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime

import feedparser
from deep_translator import GoogleTranslator
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

# (이름, 코드, 시장구분, 뉴스검색어, 언어)  market: KR_STOCK | KR_ETF | US ; loc: ko | en
HOLDINGS = [
    ("삼성전자", "005930", "KR_STOCK", "삼성전자", "ko"),
    ("SK하이닉스", "000660", "KR_STOCK", "SK하이닉스", "ko"),
    ("삼성전기", "009150", "KR_STOCK", "삼성전기", "ko"),
    ("에코프로", "086520", "KR_STOCK", "에코프로", "ko"),
    ("삼성중공업", "010140", "KR_STOCK", "삼성중공업", "ko"),
    ("삼성SDI", "006400", "KR_STOCK", "삼성SDI", "ko"),
    ("우리기술", "032820", "KR_STOCK", "우리기술 주식", "ko"),
    ("레인보우로보틱스", "277810", "KR_STOCK", "레인보우로보틱스", "ko"),
    ("SOL AI반도체TOP2플러스", "0167A0", "KR_ETF", "SOL AI반도체", "ko"),
    ("TIGER LG그룹플러스", "138530", "KR_ETF", "TIGER LG그룹", "ko"),
    ("QQQ", "QQQ", "US", "Invesco QQQ ETF", "en"),
    ("테슬라", "TSLA", "US", "Tesla stock", "en"),
    ("아이온큐 IonQ", "IONQ", "US", "IonQ", "en"),
    ("TSMC", "TSM", "US", "TSMC", "en"),
    ("엔비디아", "NVDA", "US", "Nvidia", "en"),
    ("인텔", "INTC", "US", "Intel stock", "en"),
    ("마이크론", "MU", "US", "Micron", "en"),
    ("샌디스크 SanDisk", "SNDK", "US", "SanDisk", "en"),
]

WATCHLIST = [
    ("삼양식품", "003230", "KR_STOCK", "삼양식품", "ko"),
    ("LIG디펜스앤에어로스페이스", "079550", "KR_STOCK", "LIG디펜스앤에어로스페이스", "ko"),
    ("한화에어로스페이스", "012450", "KR_STOCK", "한화에어로스페이스", "ko"),
    ("LG전자", "066570", "KR_STOCK", "LG전자", "ko"),
    ("LG이노텍", "011070", "KR_STOCK", "LG이노텍", "ko"),
    ("두산로보틱스", "454910", "KR_STOCK", "두산로보틱스", "ko"),
    ("현대자동차", "005380", "KR_STOCK", "현대자동차", "ko"),
]


def _kr_range(days_back=12):
    today = dt.datetime.now(KST)
    return (today - dt.timedelta(days=days_back)).strftime("%Y%m%d"), today.strftime("%Y%m%d")


def get_kr_price(code, is_etf=False):
    from pykrx import stock
    start, end = _kr_range()
    df = None
    try:
        df = stock.get_etf_ohlcv_by_date(start, end, code) if is_etf else stock.get_market_ohlcv(start, end, code)
    except Exception:
        df = None
    if df is None or len(df) == 0:
        try:
            df = stock.get_market_ohlcv(start, end, code)
        except Exception:
            df = None
    if df is None or len(df) == 0 or "종가" not in df.columns:
        return None, None, None
    closes = df["종가"].dropna()
    closes = closes[closes > 0]
    if len(closes) == 0:
        return None, None, None
    price = float(closes.iloc[-1])
    pct = None
    if len(closes) >= 2:
        prev = float(closes.iloc[-2])
        if prev:
            pct = (price - prev) / prev * 100.0
    return price, pct, closes.index[-1].strftime("%Y-%m-%d")


def get_us_price(ticker):
    import yfinance as yf
    t = yf.Ticker(ticker)
    price = prev = None
    asof = dt.datetime.now(KST).strftime("%Y-%m-%d")
    try:
        fi = t.fast_info
        price = fi.get("last_price")
        prev = fi.get("previous_close")
    except Exception:
        pass
    if not price:
        try:
            h = t.history(period="5d")
            if len(h):
                price = float(h["Close"].iloc[-1])
                if len(h) >= 2:
                    prev = float(h["Close"].iloc[-2])
                asof = h.index[-1].strftime("%Y-%m-%d")
        except Exception:
            pass
    if not price:
        return None, None, None
    pct = ((float(price) - float(prev)) / float(prev) * 100.0) if prev else None
    return float(price), pct, asof


def fetch_news(query, loc, max_items=3, within_hours=24):
    if loc == "en":
        url = "https://news.google.com/rss/search?q=" + query + "+when:1d&hl=en-US&gl=US&ceid=US:en"
    else:
        url = "https://news.google.com/rss/search?q=" + query + "+when:1d&hl=ko&gl=KR&ceid=KR:ko"
    try:
        feed = feedparser.parse(url)
    except Exception:
        return []
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=within_hours)
    items = []
    for e in feed.entries:
        pub = None
        if getattr(e, "published", None):
            try:
                pub = parsedate_to_datetime(e.published)
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=dt.timezone.utc)
            except Exception:
                pub = None
        if pub is not None and pub < cutoff:
            continue
        title = html.unescape(getattr(e, "title", "") or "")
        link = getattr(e, "link", "") or ""
        source = ""
        if getattr(e, "source", None) and getattr(e.source, "title", None):
            source = e.source.title
        title_ko = title
        if loc == "en" and title:
            try:
                title_ko = GoogleTranslator(source="auto", target="ko").translate(title)
            except Exception:
                title_ko = title
        items.append({
            "title_ko": title_ko,
            "title_orig": title if loc == "en" else "",
            "link": link,
            "source": source,
            "pub": pub.astimezone(KST).strftime("%m-%d %H:%M") if pub else "",
        })
        if len(items) >= max_items:
            break
    return items


def _fmt_price(p, ccy):
    if p is None:
        return "조회실패"
    return (format(p, ",.0f") + " 원") if ccy == "KRW" else ("$" + format(p, ",.2f"))


def _fmt_pct(pct):
    if pct is None:
        return "-"
    color = "#d32f2f" if pct > 0 else ("#1976d2" if pct < 0 else "#666")
    sign = "+" if pct > 0 else ""
    return "<span style='color:" + color + "'>" + sign + format(pct, ".2f") + "%</span>"


def build_section(rows, label):
    price_rows = []
    news_blocks = []
    for name, code, market, q, loc in rows:
        if market == "US":
            price, pct, asof = get_us_price(code)
            ccy = "USD"
        else:
            price, pct, asof = get_kr_price(code, is_etf=(market == "KR_ETF"))
            ccy = "KRW"
        c = "padding:7px 10px;border-bottom:1px solid #eee;"
        price_rows.append(
            "<tr>"
            + "<td style='" + c + "font-weight:600'>" + html.escape(name) + "</td>"
            + "<td style='" + c + "color:#999'>" + code + "</td>"
            + "<td style='" + c + "text-align:right'>" + _fmt_price(price, ccy) + "</td>"
            + "<td style='" + c + "text-align:right'>" + _fmt_pct(pct) + "</td>"
            + "<td style='" + c + "color:#999;text-align:right;font-size:12px'>" + (asof or "-") + "</td>"
            + "</tr>"
        )
        news = fetch_news(q, loc)
        if not news:
            li = "<li style='color:#999'>최근 24시간 내 뉴스 없음</li>"
        else:
            li = ""
            for n in news:
                meta = " · ".join([x for x in [n["source"], n["pub"]] if x])
                orig = ""
                if n["title_orig"]:
                    orig = "<div style='color:#aaa;font-size:12px'>" + html.escape(n["title_orig"]) + "</div>"
                li += (
                    "<li style='margin-bottom:9px'>"
                    + "<a href='" + html.escape(n["link"]) + "' style='color:#1a0dab;text-decoration:none'>"
                    + html.escape(n["title_ko"]) + "</a>" + orig
                    + "<div style='color:#999;font-size:12px'>" + html.escape(meta) + "</div></li>"
                )
        news_blocks.append(
            "<div style='margin:14px 0;padding:12px 14px;background:#fafbfc;border-radius:8px'>"
            + "<div style='font-weight:600;margin-bottom:6px'>" + html.escape(name)
            + " <span style='color:#aaa;font-weight:400;font-size:12px'>" + code + "</span></div>"
            + "<ul style='margin:0;padding-left:18px'>" + li + "</ul></div>"
        )
    th = "padding:7px 10px;"
    price_table = (
        "<h2 style='font-size:17px;margin:22px 0 8px;border-left:4px solid #2d6cdf;padding-left:8px'>" + label + " · 시세</h2>"
        + "<table style='border-collapse:collapse;width:100%;font-size:14px'>"
        + "<tr style='background:#f0f3f8;color:#555'>"
        + "<th style='" + th + "text-align:left'>종목</th>"
        + "<th style='" + th + "text-align:left'>코드</th>"
        + "<th style='" + th + "text-align:right'>현재가</th>"
        + "<th style='" + th + "text-align:right'>등락률</th>"
        + "<th style='" + th + "text-align:right'>기준일</th></tr>"
        + "".join(price_rows) + "</table>"
    )
    news_section = (
        "<h2 style='font-size:17px;margin:26px 0 8px;border-left:4px solid #2d6cdf;padding-left:8px'>"
        + label + " · 종목별 뉴스 (24시간, 최대 3개)</h2>" + "".join(news_blocks)
    )
    return price_table + news_section


def build_html():
    now = dt.datetime.now(KST)
    ts = now.strftime("%Y년 %m월 %d일 %H:%M")
    font = "-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo','Malgun Gothic',Arial,sans-serif"
    notice = ("한국 증시는 09:00 개장이라 08:00 리포트의 한국 종목은 전일 종가일 수 있습니다. "
              "뉴스는 Google 뉴스 노출순위와 최신순으로 자동 선별되며, 영문 제목은 자동 번역되었습니다.")
    hold_kr = [r for r in HOLDINGS if r[2] != "US"]
    hold_us = [r for r in HOLDINGS if r[2] == "US"]
    watch_kr = [r for r in WATCHLIST if r[2] != "US"]
    watch_us = [r for r in WATCHLIST if r[2] == "US"]
    body = ""
    if hold_kr:
        body += build_section(hold_kr, "보유 종목 · 한국")
    if hold_us:
        body += build_section(hold_us, "보유 종목 · 미국")
    if watch_kr:
        body += build_section(watch_kr, "관심 종목 · 한국")
    if watch_us:
        body += build_section(watch_us, "관심 종목 · 미국")
    p = []
    p.append("<!DOCTYPE html>")
    p.append("<html lang='ko'><head><meta charset='utf-8'>")
    p.append("<meta name='viewport' content='width=device-width, initial-scale=1'>")
    p.append("<title>데일리 포트폴리오 리포트</title></head>")
    p.append("<body style='margin:0;padding:0;background:#f0f2f5;font-family:" + font + ";'>")
    p.append("<div style='max-width:720px;margin:0 auto;padding:24px 16px;'>")
    p.append("<div style='background:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,0.08);'>")
    p.append("<div style='background:#1f3a5f;color:#ffffff;padding:22px 24px;'>")
    p.append("<div style='font-size:21px;font-weight:700;'>데일리 포트폴리오 리포트</div>")
    p.append("<div style='font-size:13px;opacity:0.85;margin-top:4px;'>" + ts + " KST 기준</div>")
    p.append("</div>")
    p.append("<div style='padding:12px 24px;background:#fff8e1;border-bottom:1px solid #eee;color:#8a6d00;font-size:12px;line-height:1.5;'>")
    p.append(notice)
    p.append("</div>")
    p.append("<div style='padding:8px 24px 24px;'>")
    p.append(body)
    p.append("</div>")
    p.append("<div style='background:#fafafa;border-top:1px solid #eee;padding:14px 24px;color:#aaa;font-size:11px;'>자동 생성 · GitHub Actions · 무료 자동 버전</div>")
    p.append("</div></div></body></html>")
    return "".join(p)


def send_email(html_body):
    user = os.environ["GMAIL_USER"]
    pw = os.environ["GMAIL_APP_PASSWORD"]
    to = os.environ.get("MAIL_TO") or user
    today = dt.datetime.now(KST).strftime("%Y-%m-%d")
    msg = MIMEText(html_body, "html", "utf-8")
    msg["Subject"] = "[포트폴리오] " + today + " 시세·뉴스 리포트"
    msg["From"] = user
    msg["To"] = to
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, pw)
        s.sendmail(user, [a.strip() for a in to.split(",")], msg.as_string())
    print("메일 발송 완료 ->", to)


def main():
    send_email(build_html())


if __name__ == "__main__":
    main()
