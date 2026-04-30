#!/usr/bin/env python3
"""
경쟁사 뉴스 자동 수집 스크립트 v2 (Phase 1+2)
- 네이버 검색 API로 30개 경쟁사 최신 뉴스 수집
- 감성 분석 (긍정/부정/중립) 자동 분류
- KPI 계산 (오늘/이번주/긍정·부정 비율/Top3 활발 업체)
- 한글 매체명 매핑
- template.html을 사용해 index.html 생성
"""
import os
import sys
import json
import re
import requests
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from collections import Counter

CLIENT_ID = os.environ.get('NAVER_CLIENT_ID')
CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET')

if not CLIENT_ID or not CLIENT_SECRET:
    print("ERROR: NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET 환경변수가 필요합니다.", file=sys.stderr)
    sys.exit(1)

KST = timezone(timedelta(hours=9))

COMPANIES = {
    "POS / 테이블오더 / 키오스크": [
        {"name": "티오더", "query": "티오더 테이블오더", "desc": "태블릿 기반 테이블오더 1위. 누적 35만대 설치.", "tags": ["테이블오더","태블릿","AI"], "type": "direct"},
        {"name": "페이히어", "query": "페이히어 POS", "desc": "모바일 POS 기반 소상공인 매장관리 솔루션.", "tags": ["모바일POS","SaaS"], "type": "direct"},
        {"name": "하나시스", "query": "하나시스 키오스크", "desc": "POS·키오스크 전문기업. HW+SW 통합.", "tags": ["POS","키오스크","프랜차이즈"], "type": "direct"},
        {"name": "포스뱅크", "query": "포스뱅크 POS", "desc": "POS·키오스크 하드웨어 제조. 글로벌 수출.", "tags": ["POS하드웨어","키오스크","수출"], "type": "indirect"},
        {"name": "오케이포스", "query": "오케이포스 POS", "desc": "POS·키오스크·VAN 사업 겸영.", "tags": ["POS","키오스크","VAN"], "type": "indirect"},
        {"name": "캐치테이블", "query": "캐치테이블 예약", "desc": "레스토랑 예약·웨이팅 플랫폼.", "tags": ["예약","웨이팅","외식"], "type": "indirect"},
        {"name": "메뉴잇", "query": "메뉴잇 모바일오더", "desc": "QR 기반 모바일 오더 서비스.", "tags": ["QR오더","비대면"], "type": "indirect"},
        {"name": "한국전자금융", "query": "한국전자금융 키오스크", "desc": "코스닥 상장 키오스크 전문. 무인결제·식권·주차.", "tags": ["키오스크","무인결제","코스닥"], "type": "kiosk"},
        {"name": "씨아이테크", "query": "씨아이테크 키오스크", "desc": "키오스크·DID 전문 상장기업.", "tags": ["키오스크","DID","공공"], "type": "kiosk"},
        {"name": "니스인프라", "query": "NICE인프라 키오스크", "desc": "NICE그룹 키오스크 제조. 대형 고객사 다수.", "tags": ["키오스크","NICE그룹"], "type": "kiosk"},
        {"name": "성신이노텍", "query": "성신이노텍 키오스크", "desc": "키오스크 전문 제조. 무인주문·결제·발권.", "tags": ["키오스크제조","무인주문"], "type": "kiosk"},
        {"name": "푸른기술", "query": "푸른기술 키오스크", "desc": "식권·세금환급 키오스크. 한국전자금융 협업.", "tags": ["식권키오스크","세금환급"], "type": "kiosk"},
    ],
    "결제 (PG / VAN)": [
        {"name": "토스플레이스", "query": "토스플레이스", "desc": "토스 오프라인 결제 단말기. 가맹점 30만+.", "tags": ["결제단말기","토스"], "type": "direct"},
        {"name": "한국신용데이터(KCD)", "query": "한국신용데이터 캐시노트", "desc": "캐시노트 운영. 200만 사업장.", "tags": ["캐시노트","소상공인금융"], "type": "direct"},
        {"name": "KG이니시스", "query": "KG이니시스", "desc": "국내 1위 PG사.", "tags": ["PG","온오프라인"], "type": "eco"},
        {"name": "NHN한국사이버결제(KCP)", "query": "NHN한국사이버결제", "desc": "NHN 계열 PG사.", "tags": ["PG","NHN"], "type": "eco"},
        {"name": "헥토파이낸셜", "query": "헥토파이낸셜", "desc": "PG·VAN 통합. 간편결제·송금.", "tags": ["PG","VAN"], "type": "eco"},
        {"name": "KICC", "query": "한국정보통신 KICC", "desc": "VAN·PG 겸업. 오프라인 결제 핵심.", "tags": ["VAN","PG"], "type": "eco"},
        {"name": "KPN", "query": "한국결제네트웍스", "desc": "VAN사. 소상공인 결제 단말기.", "tags": ["VAN","단말기"], "type": "eco"},
        {"name": "나이스페이먼츠", "query": "나이스페이먼츠", "desc": "나이스그룹 PG사.", "tags": ["PG","나이스"], "type": "eco"},
        {"name": "토스페이먼츠", "query": "토스페이먼츠", "desc": "토스 온라인 PG. 개발자 친화적.", "tags": ["PG","API"], "type": "eco"},
    ],
    "멤버십 / 브랜드앱": [
        {"name": "발트루스트", "query": "발트루스트 Valtrust", "desc": "매장 멤버십·브랜드앱 솔루션. CRM.", "tags": ["멤버십","브랜드앱","CRM"], "type": "direct"},
        {"name": "도도포인트", "query": "도도포인트 스포카", "desc": "태블릿 포인트 적립. 고객관리.", "tags": ["포인트적립","고객관리"], "type": "indirect"},
        {"name": "채널톡", "query": "채널톡 채널코퍼레이션", "desc": "AI 고객 메신저. 통합 CRM.", "tags": ["메신저","CRM","AI"], "type": "indirect"},
        {"name": "리뷰노트", "query": "리뷰노트 크리마", "desc": "리뷰 관리·마케팅 자동화.", "tags": ["리뷰","마케팅"], "type": "indirect"},
    ],
    "빅테크 / 플랫폼": [
        {"name": "네이버", "query": "네이버페이 스마트주문", "desc": "네이버페이·스마트주문·예약.", "tags": ["네이버페이","스마트주문"], "type": "bigtech"},
        {"name": "카카오", "query": "카카오페이 톡주문", "desc": "카카오페이·톡주문·선물하기.", "tags": ["카카오페이","톡주문"], "type": "bigtech"},
        {"name": "토스", "query": "토스페이 비바리퍼블리카", "desc": "결제 생태계. 토스페이·플레이스.", "tags": ["토스페이","슈퍼앱"], "type": "bigtech"},
        {"name": "배달의민족", "query": "배달의민족 우아한형제들", "desc": "배달앱 1위. 배민오더 확장.", "tags": ["배달","매장주문"], "type": "bigtech"},
        {"name": "당근", "query": "당근 동네가게 당근페이", "desc": "로컬 플랫폼. 동네가게·당근페이.", "tags": ["로컬커머스","당근페이"], "type": "bigtech"},
    ],
}

# 한글 매체명 매핑 (도메인 → 한글명)
SOURCE_NAMES = {
    'chosun.com': '조선비즈', 'biz.chosun.com': '조선비즈',
    'mt.co.kr': '머니투데이', 'etnews.com': '전자신문',
    'mk.co.kr': '매일경제', 'hankyung.com': '한국경제',
    'newsis.com': '뉴시스', 'yna.co.kr': '연합뉴스', 'yonhapnews.co.kr': '연합뉴스',
    'zdnet.co.kr': 'ZDNet Korea', 'thebell.co.kr': '더벨',
    'ebn.co.kr': 'EBN', 'venturesquare.net': '벤처스퀘어',
    'aitimes.com': 'AI타임스', 'fntimes.com': '한국금융신문',
    'ajunews.com': '아주경제', 'bloter.net': '블로터',
    'dt.co.kr': '디지털타임스', 'edaily.co.kr': '이데일리',
    'sedaily.com': '서울경제', 'etoday.co.kr': '이투데이',
    'fnnews.com': '파이낸셜뉴스', 'wowtale.net': '와우테일',
    'sbsbiz.co.kr': 'SBS Biz', 'koit.co.kr': '정보통신신문',
    'sentv.co.kr': '센텐스TV', 'startupn.kr': '스타트업N',
    'platum.kr': '플래텀', 'asiae.co.kr': '아시아경제',
    'newdaily.co.kr': '뉴데일리', 'munhwa.com': '문화일보',
    'hani.co.kr': '한겨레', 'donga.com': '동아일보',
    'joongang.co.kr': '중앙일보', 'kmib.co.kr': '국민일보',
    'segye.com': '세계일보', 'seoul.co.kr': '서울신문',
    'ohmynews.com': '오마이뉴스', 'kbs.co.kr': 'KBS',
    'mbc.co.kr': 'MBC', 'sbs.co.kr': 'SBS',
    'ytn.co.kr': 'YTN', 'mbn.co.kr': 'MBN',
    'jtbc.joins.com': 'JTBC', 'naver.com': '네이버',
    'daum.net': '다음', 'dailian.co.kr': '데일리안',
    'newspim.com': '뉴스핌', 'topdaily.kr': '토픽데일리',
    'finance-scope.com': 'Finance Scope',
    'businesspost.co.kr': '비즈니스포스트',
    'inicis.com': '이니시스 블로그',
    'asiaa.co.kr': '아시아에이', 'newstap.co.kr': '뉴스탭',
    'sommeliertimes.com': '소믈리에타임즈',
    'theindigo.co.kr': '더인디고',
    'thelec.kr': '디일렉', 'kgnews.co.kr': '경기신문',
    'inews24.com': '아이뉴스24', 'metroseoul.co.kr': '메트로신문',
    'apnews.kr': 'AP신문', 'getnews.co.kr': 'getnews',
    'moneys.co.kr': '머니S', 'businesskorea.co.kr': 'BusinessKorea',
    'mediapen.com': '미디어펜', 'g-enews.com': '글로벌이코노믹',
    'asiatime.co.kr': '아시아타임즈', 'asiatoday.co.kr': '아시아투데이',
    'ddaily.co.kr': '디지털데일리', 'enewstoday.co.kr': '이뉴스투데이',
    'getnews.co.kr': 'GetNews', 'newsworker.co.kr': '뉴스워커',
    'epnc.co.kr': 'EP&C', 'ekoreanews.co.kr': 'eKoreaNews',
    'sportsworldi.com': '스포츠월드', 'sportsseoul.com': '스포츠서울',
    'sportskhan.news': '스포츠경향', 'sports.khan.co.kr': '스포츠경향',
    'kpinews.kr': 'KPI뉴스', 'reportera.co.kr': '리포터라',
    'pressian.com': '프레시안', 'koreatimes.co.kr': '코리아타임스',
    'koreaherald.com': '코리아헤럴드',
}

# 감성 분석 키워드
POSITIVE_KEYWORDS = [
    '흑자', '영업이익', '신기록', '1위', '투자유치', '투자 유치', '유니콘',
    '진출', '확장', '성장', '호조', '호평', '우수', '수상', '협업', '제휴',
    '돌파', '달성', '체결', '런칭', '오픈', '출시', '신제품', '신규', '확대',
    '강화', '도약', '선정', '선두', '최대', '최고', '역대', '신용등급', '상장'
]
NEGATIVE_KEYWORDS = [
    '적자', '손실', '부진', '위기', '규제', '처벌', '과태료', '고소', '수사',
    '갈등', '논란', '패소', '하락', '폭락', '중단', '폐쇄', '사퇴', '해고',
    '탈취', '침해', '취소', '연기', '실패', '감소', '경고', '리콜', '비판',
    '항의', '시위', '제재', '적발', '의혹', '사고', '사망', '부도'
]

TYPE_KEYWORDS = {
    "실적": ["흑자", "매출", "영업이익", "분기 실적", "당기순이익", "성장세"],
    "투자": ["투자 유치", "투자유치", "시리즈", "유치한", "기업가치", "유니콘", "라운드"],
    "제휴": ["제휴", "협업", "MOU", "파트너십", "공동 개발"],
    "신규서비스": ["출시", "런칭", "오픈", "공개", "선보", "신제품", "신규"],
    "인사": ["임명", "선임", "사임", "신임 대표", "신임 CEO"],
    "규제": ["규제", "법안", "정책", "당국", "과태료", "처분"],
}

def classify_news(title, summary):
    text = (title + " " + summary).lower()
    for type_name, keywords in TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text:
                return type_name
    return "뉴스"

def analyze_sentiment(title, summary):
    text = title + " " + summary
    pos_count = sum(1 for kw in POSITIVE_KEYWORDS if kw in text)
    neg_count = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text)
    if pos_count > neg_count:
        return "positive"
    elif neg_count > pos_count:
        return "negative"
    return "neutral"

def clean_html_text(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = (text.replace('&quot;', '"')
                .replace('&amp;', '&')
                .replace('&lt;', '<')
                .replace('&gt;', '>')
                .replace('&apos;', "'")
                .replace('&#39;', "'")
                .replace('&nbsp;', ' '))
    return text.strip()

def fetch_news(query, display=8):
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET,
    }
    params = {"query": query, "display": display, "sort": "date"}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception as e:
        print(f"  ERROR fetching '{query}': {e}", file=sys.stderr)
        return []

def parse_pubdate(pubdate_str):
    try:
        dt = parsedate_to_datetime(pubdate_str)
        return dt.astimezone(KST).strftime("%Y-%m-%d")
    except Exception:
        return ""

def get_source_name(url):
    if not url:
        return ""
    m = re.match(r'https?://(?:www\.|m\.)?([^/]+)', url)
    if not m:
        return ""
    domain = m.group(1)
    if domain in SOURCE_NAMES:
        return SOURCE_NAMES[domain]
    parts = domain.split('.')
    if len(parts) > 2:
        main_domain = '.'.join(parts[-2:])
        if main_domain in SOURCE_NAMES:
            return SOURCE_NAMES[main_domain]
    return domain

def collect_all_news(days=14):
    cutoff = datetime.now(KST) - timedelta(days=days)
    news_data = {}
    for category, companies in COMPANIES.items():
        print(f"\n[{category}]")
        for c in companies:
            items = fetch_news(c['query'])
            filtered = []
            for item in items:
                pub_dt_str = item.get('pubDate', '')
                try:
                    pub_dt = parsedate_to_datetime(pub_dt_str)
                    if pub_dt < cutoff:
                        continue
                except Exception:
                    pass
                title = clean_html_text(item.get('title', ''))
                summary = clean_html_text(item.get('description', ''))
                url = item.get('originallink') or item.get('link', '')
                sentiment = analyze_sentiment(title, summary)
                filtered.append({
                    "title": title,
                    "summary": summary[:200],
                    "source": get_source_name(url),
                    "url": url,
                    "date": parse_pubdate(pub_dt_str),
                    "sentiment": sentiment,
                })
            news_data[c['name']] = filtered
            print(f"  {c['name']}: {len(filtered)}건")
    return news_data

def compute_kpis(news_data):
    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    week_cutoff = (datetime.now(KST) - timedelta(days=7)).strftime("%Y-%m-%d")
    total_today = total_week = total_all = 0
    pos_count = neg_count = neutral_count = 0
    company_counts = Counter()
    for company, items in news_data.items():
        company_counts[company] = len(items)
        for item in items:
            total_all += 1
            s = item.get("sentiment")
            if s == "positive":
                pos_count += 1
            elif s == "negative":
                neg_count += 1
            else:
                neutral_count += 1
            d = item.get("date", "")
            if d == today_str:
                total_today += 1
            if d >= week_cutoff:
                total_week += 1
    top_companies = [{"name": n, "count": c} for n, c in company_counts.most_common(3) if c > 0]
    return {
        "total_all": total_all,
        "total_today": total_today,
        "total_week": total_week,
        "positive": pos_count,
        "negative": neg_count,
        "neutral": neutral_count,
        "top_companies": top_companies,
    }

def generate_highlights(news_data, max_items=6):
    all_news = []
    for company, items in news_data.items():
        if items:
            top = items[0]
            all_news.append({
                "company": company,
                "title": top["title"],
                "summary": top["summary"][:150],
                "type": classify_news(top["title"], top["summary"]),
                "url": top["url"],
                "source": top["source"],
                "sentiment": top["sentiment"],
                "_date": top["date"],
            })
    all_news.sort(key=lambda x: x.get("_date", ""), reverse=True)
    return [{k: v for k, v in n.items() if not k.startswith("_")} for n in all_news[:max_items]]

def generate_companies_meta():
    out = {}
    for category, companies in COMPANIES.items():
        out[category] = [{
            "name": c["name"],
            "desc": c["desc"],
            "tags": c["tags"],
            "type": c["type"],
        } for c in companies]
    return out

def render_html(news_data, highlights, kpis, last_updated, last_updated_iso):
    with open('template.html', 'r', encoding='utf-8') as f:
        template = f.read()
    template = template.replace('/*__NEWS_DATA__*/',
        'const NEWS_DATA = ' + json.dumps(news_data, ensure_ascii=False) + ';')
    template = template.replace('/*__HIGHLIGHTS__*/',
        'const HIGHLIGHTS = ' + json.dumps(highlights, ensure_ascii=False) + ';')
    template = template.replace('/*__KPIS__*/',
        'const KPIS = ' + json.dumps(kpis, ensure_ascii=False) + ';')
    template = template.replace('/*__LAST_UPDATED__*/',
        'const LAST_UPDATED = ' + json.dumps(last_updated, ensure_ascii=False) + ';')
    template = template.replace('/*__LAST_UPDATED_ISO__*/',
        'const LAST_UPDATED_ISO = ' + json.dumps(last_updated_iso, ensure_ascii=False) + ';')
    template = template.replace('/*__COMPANIES__*/',
        'const COMPANIES = ' + json.dumps(generate_companies_meta(), ensure_ascii=False) + ';')
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(template)
    print(f"\n[OK] index.html 생성 완료 ({last_updated})")

if __name__ == "__main__":
    print("=" * 60)
    print("경쟁사 뉴스 수집 시작 (v2 - Phase 1+2)")
    print("=" * 60)
    news_data = collect_all_news(days=14)
    highlights = generate_highlights(news_data)
    kpis = compute_kpis(news_data)
    now_kst = datetime.now(KST)
    last_updated = now_kst.strftime("%Y-%m-%d %H:%M KST")
    last_updated_iso = now_kst.isoformat()
    print(f"\n총: {kpis['total_all']}건 | 오늘: {kpis['total_today']} | 이번주: {kpis['total_week']}")
    print(f"감성: 긍정 {kpis['positive']} | 부정 {kpis['negative']} | 중립 {kpis['neutral']}")
    print(f"하이라이트: {len(highlights)}건")
    render_html(news_data, highlights, kpis, last_updated, last_updated_iso)
