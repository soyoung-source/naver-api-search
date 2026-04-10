import streamlit as st  # 스트림릿 라이브러리 임포트
import pandas as pd  # 판다스 라이브러리 임포트
import plotly.express as px  # Plotly Express 임포트 (데이터 시각화용)
import plotly.graph_objects as go  # Plotly Graph Objects 임포트
import os  # 운영체제 라이브러리 임포트
import requests  # HTTP 요청용 라이브러리 임포트
import json  # JSON 처리용 라이브러리 임포트
from datetime import datetime, timedelta  # 날짜 및 시간 처리용 임포트
from dotenv import load_dotenv  # 환경 변수 로드용 라이브러리 임포트
import re  # 정규표현식 라이브러리 임포트
from collections import Counter  # 빈도수 계산용 라이브러리 임포트

# 1. 페이지 설정 및 스타일
st.set_page_config(page_title="네이버 API 실시간 분석 대시보드", layout="wide", page_icon="⚡")  # 페이지 제목, 레이아웃, 아이콘 설정

# 커스텀 CSS 설정
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }  /* 메인 배경색 설정 */
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }  /* 메트릭 박스 스타일 */
    h1, h2, h3 { color: #1e1e1e; font-family: 'Pretendard', sans-serif; }  /* 제목 폰트 및 색상 설정 */
    </style>
""", unsafe_allow_html=True)  # HTML 커스텀 스타일 적용

# 2. 프로필 및 환경 설정
load_dotenv()  # .env 파일에서 환경 변수 로드 (로컬 개발용)

# 네이버 API 인증 정보 로드 (Streamlit Secrets 우선, 그 다음 환경 변수 확인)
if "NAVER_CLIENT_ID" in st.secrets:
    NAVER_CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]  # 스트림릿 클라우드의 Secrets에서 ID 가져오기
    NAVER_CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]  # 스트림릿 클라우드의 Secrets에서 시크릿 가져오기
else:
    NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")  # 로컬 환경 변수에서 ID 가져오기
    NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")  # 로컬 환경 변수에서 시크릿 가져오기

# 3. 네이버 API 데이터 수집 함수 (실시간 처리용)
def get_header():  # API 요청 헤더 생성 함수
    return {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,  # 헤더에 클라이언트 ID 포함
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,  # 헤더에 클라이언트 시크릿 포함
        "Content-Type": "application/json"  # 콘텐츠 타입을 JSON으로 설정
    }

@st.cache_data(ttl=3600)  # 1시간 동안 결과 캐싱 설정
def fetch_datalab_trend(keywords, start_date, end_date):  # 데이터랩 트렌드 수집 함수
    url = "https://openapi.naver.com/v1/datalab/search"  # 데이터랩 API 엔드포인트 URL
    keyword_groups = [{"groupName": kw, "keywords": [kw]} for kw in keywords]  # 키워드별 그룹 구성
    body = {
        "startDate": start_date.strftime('%Y-%m-%d'),  # 시작 날짜 설정
        "endDate": end_date.strftime('%Y-%m-%d'),  # 종료 날짜 설정
        "timeUnit": "date",  # 시간 단위 설정 (일간)
        "keywordGroups": keyword_groups  # 키워드 그룹 설정
    }
    response = requests.post(url, headers=get_header(), data=json.dumps(body))  # API 요청 전송
    if response.status_code == 200:  # 요청 성공 시
        res_json = response.json()  # 응답 데이터를 JSON으로 변환
        all_data = []  # 데이터 저장용 리스트 초기화
        for result in res_json['results']:  # 각 결과 그룹 순회
            group_name = result['title']  # 그룹 이름 추출
            for entry in result['data']:  # 날짜별 데이터 순회
                all_data.append({"date": entry['period'], "keyword": group_name, "ratio": entry['ratio']})  # 데이터 추가
        df = pd.DataFrame(all_data)  # 데이터프레임으로 변환
        if not df.empty:  # 데이터가 존재할 경우
            df['date'] = pd.to_datetime(df['date'])  # 날짜 컬럼을 시계열로 변환
        return df  # 결과 데이터프레임 반환
    return pd.DataFrame()  # 요청 실패 시 빈 데이터프레임 반환

@st.cache_data(ttl=3600)  # 1시간 동안 결과 캐싱 설정
def fetch_search_data(category, keywords, display=100):  # 검색 API 데이터 수집 함수
    all_results = []  # 전체 결과 저장용 리스트 초기화
    for kw in keywords:  # 각 키워드별로 반복
        base_url = f"https://openapi.naver.com/v1/search/{category}.json"  # 검색 카테고리별 URL 생성
        params = {"query": kw, "display": display, "start": 1, "sort": "sim"}  # 요청 파라미터 설정
        response = requests.get(base_url, headers=get_header(), params=params)  # API 요청 전송
        if response.status_code == 200:  # 요청 성공 시
            items = response.json().get('items', [])  # 검색된 아이템 목록 추출
            df_temp = pd.DataFrame(items)  # 임시 데이터프레임 생성
            if not df_temp.empty:  # 데이터가 존재할 경우
                df_temp['search_keyword'] = kw  # 검색 키워드 태그 추가
                df_temp['category_api'] = category  # API 카테고리 정보 추가
                all_results.append(df_temp)  # 결과 리스트에 추가
    if all_results:  # 결과가 하나라도 존재할 경우
        return pd.concat(all_results, ignore_index=True)  # 데이터프레임 병합 후 반환
    return pd.DataFrame()  # 결과가 없을 시 빈 데이터프레임 반환

# 4. 사이드바 구성
st.sidebar.title("🔍 실시간 분석 설정")  # 사이드바 제목 설정
raw_keywords = st.sidebar.text_input("분석 주제어 (쉼표로 구분)", "핫팩, 선풍기")  # 키워드 입력 필드
target_keywords = [k.strip() for k in raw_keywords.split(",") if k.strip()]  # 입력된 키워드 정제 및 리스트화

# 기간 설정
today = datetime.now()  # 오늘 날짜 가져오기
one_year_ago = today - timedelta(days=365)  # 1년 전 날짜 계산
date_range = st.sidebar.date_input("Trend 분석 기간", [one_year_ago, today], max_value=today)  # 날짜 선택기 추가

if len(date_range) == 2:  # 날짜 범위가 선택된 경우
    start_dt, end_dt = date_range  # 시작 및 종료 날짜 할당
else:  # 범위 선택이 완료되지 않은 경우
    start_dt, end_dt = one_year_ago, today  # 기본값(최근 1년) 할당

# 수집 안내
st.sidebar.info("키워드나 기간을 변경하면 데이터가 자동으로 실시간 업데이트됩니다.")  # 실시간 업데이트 안내 문구 표시

if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:  # API 키 존재 여부 확인
    st.error("API 키가 설정되지 않았습니다. .env 파일을 확인해 주세요.")  # 오류 메시지 출력
    st.stop()  # 앱 실행 중단

# 5. 데이터 수집 및 캐싱 (실시간 자동 업데이트)
@st.cache_data(ttl=3600)  # 1시간 동안 결과 캐싱 설정
def get_all_realtime_data(keywords, start_date, end_date):  # 전체 데이터 수집 통합 함수
    """
    키워드나 기간이 변경되면 자동으로 호출되어 네이버 API에서 데이터를 가져옵니다.
    """
    return {
        "trend": fetch_datalab_trend(keywords, start_date, end_date),  # 트렌드 데이터 수집
        "shop": fetch_search_data("shop", keywords),  # 쇼핑 데이터 수집
        "blog": fetch_search_data("blog", keywords),  # 블로그 데이터 수집
        "cafe": fetch_search_data("cafearticle", keywords),  # 카페 게시글 수집
        "news": fetch_search_data("news", keywords),  # 뉴스 데이터 수집
        "fetched_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # 데이터 수집 시점 기록
    }

# 데이터 수집 실행
if target_keywords:  # 분석 키워드가 입력된 경우
    with st.spinner(f"'{', '.join(target_keywords)}' 데이터를 네이버 API에서 실시간 수집 중입니다..."):  # 로딩 스피너 표시
        data_all = get_all_realtime_data(tuple(target_keywords), start_dt, end_dt)  # 실시간 데이터 수집 통합 실행
else:  # 키워드가 없는 경우
    st.warning("분석할 키워드를 입력해 주세요.")  # 경고 메시지 표시
    st.stop()  # 앱 실행 중단

# 6. 메인 레이아웃 (Tabs)
st.title("⚡ 네이버 API 실시간 통합 분석 대시보드")  # 대시보드 메인 제목 설정
st.info(f"데이터 기준 시점: {data_all['fetched_at']}")  # 데이터 수집 기준 시점 명시

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📌 프로파일링", "📈 검색 트렌드", "🛒 쇼핑 분석", "🗣️ 소셜 여론", "💾 데이터 탐색"])  # 5개의 탭 구성

# -----------------
# Tab 1: 데이터 프로파일링
# -----------------
with tab1:  # 첫 번째 탭 영역 시작
    st.header("📊 실시간 수집 데이터 요약")  # 탭 제목 설정
    cols = st.columns(5)  # 5개의 열 레이아웃 생성
    labels = ["트렌드", "쇼핑", "블로그", "카페", "뉴스"]  # 데이터셋 라벨 정의
    keys = ["trend", "shop", "blog", "cafe", "news"]  # 데이터셋 키값 정의
    
    for i, key in enumerate(keys):  # 각 데이터셋별 메트릭 표시 루프
        df = data_all[key]  # 해당 데이터셋 할당
        with cols[i]:  # 각 컬럼 섹션 시작
            st.metric(label=f"{labels[i]} 건수", value=f"{len(df):,}건")  # 데이터 수량 메트릭 표시
            if not df.empty:  # 데이터가 있는 경우
                st.write(f"**결측치:** {df.isnull().sum().sum()}")  # 결측치 개수 표시
                if 'keyword' in df.columns:  # 'keyword' 컬럼 존재 시
                    st.write(df['keyword'].value_counts())  # 키워드별 빈도 표시
                elif 'search_keyword' in df.columns:  # 'search_keyword' 컬럼 존재 시
                    st.write(df['search_keyword'].value_counts())  # 검색 키워드별 빈도 표시

# -----------------
# Tab 2: 검색 트렌드
# -----------------
with tab2:  # 두 번째 탭 영역 시작
    st.header("📈 네이버 데이터랩 트렌드 (실시간)")  # 탭 제목 설정
    df_trend = data_all['trend']  # 트렌드 데이터 할당
    if not df_trend.empty:  # 트렌드 데이터가 존재할 경우
        fig_line = px.line(df_trend, x='date', y='ratio', color='keyword', 
                           title="기간별 검색량 추이", labels={'ratio': '검색 점유율', 'date': '날짜'},
                           template="plotly_white")  # 선형 시계열 그래프 생성
        st.plotly_chart(fig_line, use_container_width=True)  # 그래프 대시보드 출력
        
        df_trend['month'] = df_trend['date'].dt.strftime('%Y-%m')  # 월별 분석용 컬럼 생성
        monthly_avg = df_trend.groupby(['month', 'keyword'])['ratio'].mean().reset_index()  # 월별 평균 검색량 집계
        fig_bar = px.bar(monthly_avg, x='month', y='ratio', color='keyword', barmode='group',
                         title="월별 평균 검색량 비교", template="plotly_white")  # 월별 비교 바 차트 생성
        st.plotly_chart(fig_bar, use_container_width=True)  # 그래프 대시보드 출력
    else:  # 데이터가 없을 경우
        st.warning("수집된 트렌드 데이터가 없습니다.")  # 안내 메시지 출력

# -----------------
# Tab 3: 쇼핑 분석
# -----------------
with tab3:  # 세 번째 탭 영역 시작
    st.header("🛒 쇼핑 실시간 분석")  # 탭 제목 설정
    df_shop = data_all['shop']  # 쇼핑 데이터 할당
    if not df_shop.empty:  # 데이터가 존재할 경우
        # 결측치 처리 (Plotly Treemap 에러 방지)
        df_shop_viz = df_shop.copy()  # 시각화용 데이터 복사
        for col in ['brand', 'category3', 'mallName']:  # 결측치 정제가 필요한 컬럼 순회
            if col in df_shop_viz.columns:  # 컬럼이 존재하는 경우
                df_shop_viz[col] = df_shop_viz[col].fillna("미지정").replace('', "미지정")  # 빈값 채우기
        df_shop_viz['lprice'] = pd.to_numeric(df_shop_viz['lprice'], errors='coerce').fillna(0)  # 가격 데이터를 수치형으로 변환
        
        col_s1, col_s2 = st.columns(2)  # 2분할 레이아웃 생성
        with col_s1:  # 왼쪽 영역
            st.subheader("브랜드/카테고리 트리맵")  # 소제목 설정
            fig_tree = px.treemap(df_shop_viz, path=['search_keyword', 'brand', 'category3'], 
                                  values='lprice', title="키워드별 브랜드/카테고리 (가중치: 가격)",
                                  template="plotly_white")  # 상품군 및 브랜드 트리맵 시각화
            st.plotly_chart(fig_tree, use_container_width=True)  # 그래프 대시보드 출력
            
        with col_s2:  # 오른쪽 영역
            st.subheader("가격대 분포")  # 소제목 설정
            fig_hist = px.histogram(df_shop_viz, x="lprice", color="search_keyword", 
                                    marginal="box", title="최저가 분포 비교", labels={'lprice': '원'},
                                    template="plotly_white")  # 최저가 분포 히스토그램 및 박스플롯 생성
            st.plotly_chart(fig_hist, use_container_width=True)  # 그래프 대시보드 출력
            
        st.subheader("추천 상품")  # 분석 키워드별 추천 상품 영역
        for kw in target_keywords:  # 입력된 검색어별 반복
            st.markdown(f"#### 🏷️ {kw}")  # 키워드별 헤더 출력
            kw_shop = df_shop[df_shop['search_keyword'] == kw].head(5)  # 상위 5개 상품 추출
            if not kw_shop.empty:  # 상품 데이터가 있는 경우
                cols_card = st.columns(len(kw_shop))  # 상품별 카드 레이아웃 생성
                for idx, row in enumerate(kw_shop.itertuples()):  # 개별 상품 루프
                    with cols_card[idx]:  # 카드 컬럼 할당
                        if hasattr(row, 'image') and row.image: st.image(row.image, width=150)  # 상품 이미지 출력
                        st.markdown(f"**{row.title[:30]}...**")  # 상품 제목 일부 출력
                        st.markdown(f"💰 {int(row.lprice):,}원")  # 상품 가격 출력
                        st.markdown(f"[상세보기]({row.link})")  # 네이버 쇼핑 링크 연결
    else:  # 데이터가 없을 경우
        st.warning("수집된 쇼핑 데이터가 없습니다.")  # 안내 메시지 출력

# -----------------
# Tab 4: 소셜 여론
# -----------------
with tab4:  # 네 번째 탭 영역 시작
    st.header("🗣️ 소셜 & 뉴스 반응 (실시간)")  # 탭 제목 설정
    
    def simple_word_freq(df, text_col):  # 간단한 텍스트 빈도 분석 함수
        if df.empty: return []  # 데이터 부재 시 빈 리스트 반환
        texts = df[text_col].dropna().astype(str).tolist()  # 텍스트 컬럼 리스트화
        words = []  # 단어 저장용 리스트 초기화
        for t in texts:  # 각 문장별 반복
            clean_text = re.sub(r'<[^>]*>', '', t)  # HTML 태그 제거
            clean_text = re.sub(r'[^가-힣a-zA-Z\s]', '', clean_text)  # 한글/영문/공백 제외 특수문자 제거
            words.extend([w for w in clean_text.split() if len(w) > 1])  # 2글자 이상 단어 추출
        return Counter(words).most_common(30)  # 상위 30개 빈도수 단어 반환

    s_tabs = st.tabs(["블로그", "카페", "뉴스"])  # 소통 채널별 세부 탭 생성
    s_keys = ["blog", "cafe", "news"]  # 채널별 데이터 키 정의
    s_cols = ["title", "title", "title"]  # 분석할 컬럼명 정의 (주로 제목)
    
    for i, tab in enumerate(s_tabs):  # 채널별 탭 처리 루프
        with tab:  # 채널별 개별 탭 영역 시작
            df_soc = data_all[s_keys[i]]  # 해당 채널 데이터 호출
            if not df_soc.empty:  # 데이터가 존재할 경우
                freq = simple_word_freq(df_soc, s_cols[i])  # 빈도 분석 수행
                df_freq = pd.DataFrame(freq, columns=['단어', '빈도'])  # 결과를 데이터프레임으로 구축
                fig_soc = px.bar(df_freq, x='빈도', y='단어', orientation='h', title=f"{labels[i+2]} 핵심 키워드 Top 30", 
                                 template="plotly_white", color='빈도')  # 가로형 빈도 바 차트 시각화
                st.plotly_chart(fig_soc, use_container_width=True)  # 그래프 대시보드 출력
                st.dataframe(df_soc[['title', 'link']].head(10), use_container_width=True)  # 상위 게시글 리스트 표시
            else:  # 데이터가 없을 경우
                st.info("데이터가 없습니다.")  # 안내 메시지 출력

# -----------------
# Tab 5: 데이터 탐색
# -----------------
with tab5:  # 다섯 번째 탭 영역 시작
    st.header("💾 수집 데이터 탐색")  # 탭 제목 설정
    target_ch = st.selectbox("조회할 데이터셋 선택", labels)  # 조회 대상 데이터셋 선택 박스
    df_view = data_all[keys[labels.index(target_ch)]]  # 선택된 데이터셋 로드
    if not df_view.empty:  # 데이터셋이 존재하는 경우
        st.write(f"총 {len(df_view):,}건의 데이터가 로드되었습니다.")  # 전체 건수 출력
        st.dataframe(df_view, use_container_width=True)  # 전체 데이터프레임 그리드 출력
        csv = df_view.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')  # CSV 다운로드용 인코딩 처리
        st.download_button(label="📥 데이터 다운로드 (CSV)", data=csv, file_name=f"naver_realtime_{target_ch}.csv", mime='text/csv')  # 다운로드 버튼 생성
    else:  # 데이터가 없을 경우
        st.info("데이터가 없습니다.")  # 안내 메시지 출력
