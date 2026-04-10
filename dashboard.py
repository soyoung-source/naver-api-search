import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import re
from naver_api import NaverApiClient

# 페이지 설정
st.set_page_config(page_title="네이버 실시간 데이터 분석 대시보드", layout="wide")

# API 클라이언트 초기화
api_client = NaverApiClient()

# 텍스트 전처리 및 빈도 분석 함수
def get_word_freq(df, text_col='title', top_n=30):
    if df is None or df.empty or text_col not in df.columns:
        return pd.DataFrame(columns=['word', 'count'])
    
    all_text = " ".join(df[text_col].astype(str).tolist())
    # HTML 태그 제거 및 특수문자 제거
    clean_text = re.sub(r'<[^>]+>', '', all_text)
    clean_text = re.sub(r'[^\w\s]', '', clean_text)
    
    words = clean_text.split()
    # 1글자 단어 제외 및 불용어 처리 (간단히)
    words = [w for w in words if len(w) > 1]
    
    freq = pd.Series(words).value_counts().reset_index()
    freq.columns = ['word', 'count']
    return freq.head(top_n)

# 사이드바 구성
st.sidebar.title("🔍 분석 설정")

with st.sidebar.expander("API 및 키워드 설정", expanded=True):
    keywords_input = st.text_input("검색어 입력 (콤마로 구분)", value="선풍기, 핫팩")
    keywords = [kw.strip() for kw in keywords_input.split(",") if kw.strip()]
    
    # 쇼핑 카테고리 설정 (예시 ID)
    cat_options = {
        "전체": None,
        "디지털/가전": "50000003",
        "생활/건강": "50000008",
        "스포츠/레저": "50000007",
        "패션의류": "50000000",
        "화장품/미용": "50000002"
    }
    selected_cat_name = st.selectbox("쇼핑 인사이트 카테고리", options=list(cat_options.keys()), index=1)
    category_id = cat_options[selected_cat_name]

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("시작일", value=datetime.now() - timedelta(days=365))
    with col2:
        end_date = st.date_input("종료일", value=datetime.now())

# 데이터 로드 버튼
load_btn = st.sidebar.button("🚀 실시간 데이터 수집 및 분석", use_container_width=True)

# 데이터 캐싱
@st.cache_data(show_spinner="네이버 API에서 데이터를 가져오는 중...")
def fetch_all_data(kws, start, end, cat_id):
    if not kws: return None
    
    s_date = start.strftime("%Y-%m-%d")
    e_date = end.strftime("%Y-%m-%d")
    
    results = {}
    
    # 1. 검색어 트렌드
    results['trend'] = api_client.get_search_trend(kws, s_date, e_date)
    
    # 2. 쇼핑 트렌드 (카테고리 ID가 있는 경우)
    if cat_id:
        results['shop_trend'] = api_client.get_shopping_trend(cat_id, kws, s_date, e_date)
    
    # 3. 검색 결과 (대표 키워드 첫번째 기준 또는 각 키워드 통합)
    # 여기서는 각 키워드당 100건씩 수집하여 통합
    blog_list, cafe_list, news_list, shop_list = [], [], [], []
    for kw in kws:
        blog_list.append(api_client.search_items("blog", kw))
        cafe_list.append(api_client.search_items("cafearticle", kw))
        news_list.append(api_client.search_items("news", kw))
        shop_list.append(api_client.search_items("shop", kw))
        
    results['blog'] = pd.concat(blog_list, ignore_index=True) if any(x is not None for x in blog_list) else None
    results['cafe'] = pd.concat(cafe_list, ignore_index=True) if any(x is not None for x in cafe_list) else None
    results['news'] = pd.concat(news_list, ignore_index=True) if any(x is not None for x in news_list) else None
    results['shop'] = pd.concat(shop_list, ignore_index=True) if any(x is not None for x in shop_list) else None
    
    return results

if load_btn or 'data_loaded' in st.session_state:
    st.session_state['data_loaded'] = True
    data = fetch_all_data(keywords, start_date, end_date, category_id)
    
    if not data:
        st.error("데이터를 불러오지 못했습니다. 키워드나 API 설정을 확인하세요.")
    else:
        tab1, tab2, tab3, tab4 = st.tabs(["🚀 데이터 프로파일링", "📉 트렌드 분석", "🛒 쇼핑 분석", "💬 소셜/뉴스 분석"])
        
        # --- Tab 1: 데이터 프로파일링 ---
        with tab1:
            st.header("📊 수집 데이터 프로파일링 요약")
            cols = st.columns(len(data))
            for i, (name, df) in enumerate(data.items()):
                with cols[i % len(cols)]:
                    st.metric(f"{name.upper()}", f"{len(df) if df is not None else 0} 행")
            
            for name, df in data.items():
                if df is not None:
                    with st.expander(f"🔍 {name} 데이터 상세 요약"):
                        c1, c2 = st.columns(2)
                        with c1:
                            st.write("**Columns & Types**")
                            st.write(df.dtypes)
                        with c2:
                            st.write("**Null Counts**")
                            st.write(df.isnull().sum())
                        st.write("**Basic Stats**")
                        st.write(df.describe(include='all'))
                        st.dataframe(df.head(10))

        # --- Tab 2: 트렌드 분석 ---
        with tab2:
            st.header("📈 네이버 검색 및 쇼핑 트렌드")
            if data['trend'] is not None:
                fig_trend = px.line(data['trend'], x='date', y='ratio', color='keyword', 
                                    title="전체 검색 트렌드 (DataLab)", markers=True)
                st.plotly_chart(fig_trend, use_container_width=True)
            
            if data.get('shop_trend') is not None:
                fig_shop_trend = px.line(data['shop_trend'], x='date', y='ratio', color='keyword', 
                                         title=f"쇼핑 내 검색 클릭 트렌드 ({selected_cat_name})", markers=True)
                st.plotly_chart(fig_shop_trend, use_container_width=True)

        # --- Tab 3: 쇼핑 분석 ---
        with tab3:
            st.header("🛒 네이버 쇼핑 상품 분석")
            df_shop = data['shop']
            if df_shop is not None:
                # 데이터 정제 (가격 등)
                df_shop['lprice'] = pd.to_numeric(df_shop['lprice'], errors='coerce')
                
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("💡 카테고리 계층 구조 (Tree Map)")
                    # category1-4가 있는 경우 (API 응답 필드 확인 필요, 검색 API는 category1-4를 제공)
                    cat_cols = [c for c in ['category1', 'category2', 'category3', 'category4'] if c in df_shop.columns]
                    if cat_cols:
                        fig_tree = px.treemap(df_shop, path=cat_cols, title="상품 카테고리 분포")
                        st.plotly_chart(fig_tree, use_container_width=True)
                
                with c2:
                    st.subheader("📊 브랜드별 상품 수 (Top 15)")
                    brand_counts = df_shop['brand'].value_counts().head(15).reset_index()
                    brand_counts.columns = ['brand', 'count']
                    fig_brand = px.bar(brand_counts, x='brand', y='count', color='brand', title="상위 브랜드 분포")
                    st.plotly_chart(fig_brand, use_container_width=True)
                
                st.subheader("💰 가격대 분포")
                fig_hist = px.histogram(df_shop, x='lprice', color='query', nbins=50, 
                                        marginal="box", title="키워드별 가격 분포 히스토그램")
                st.plotly_chart(fig_hist, use_container_width=True)

        # --- Tab 4: 소셜/뉴스 분석 ---
        with tab4:
            st.header("💬 소셜 및 뉴스 텍스트 빈도 분석")
            choice = st.radio("플랫폼 선택", ["블로그", "카페", "뉴스"], horizontal=True)
            platform_map = {"블로그": "blog", "카페": "cafe", "뉴스": "news"}
            df_text = data[platform_map[choice]]
            
            if df_text is not None:
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.subheader(f"🔤 {choice} 상위 키워드 (Top 30)")
                    freq = get_word_freq(df_text)
                    fig_freq = px.bar(freq, x='count', y='word', orientation='h', color='count',
                                      color_continuous_scale='Viridis')
                    fig_freq.update_layout(yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig_freq, use_container_width=True)
                
                with c2:
                    st.subheader(f"📋 {choice} 데이터 목록")
                    # HTML 태그 제거 로직 포함하여 표시
                    df_display = df_text.copy()
                    df_display['title'] = df_display['title'].apply(lambda x: re.sub(r'<[^>]+>', '', str(x)))
                    st.dataframe(df_display[['title', 'link', 'query']], use_container_width=True)
else:
    st.info("검색어를 입력하고 '데이터 수집 시작' 버튼을 눌러주세요.")
    st.image("https://images.unsplash.com/photo-1460925895917-afdab827c52f?q=80&w=2426&auto=format&fit=crop", caption="Data Visualization Concept")
