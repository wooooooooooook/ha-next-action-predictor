import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import requests
import os
from dotenv import load_dotenv
import pytz

# .env 파일 로드
load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="Home Assistant Logbook Viewer",
    page_icon="📖",
    layout="wide"
)

def get_ha_headers():
    """Home Assistant API 헤더 생성"""
    token = os.getenv('HA_TOKEN')
    if not token:
        st.error("HA_TOKEN이 .env 파일에 설정되지 않았습니다.")
        st.stop()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

def get_time_range():
    """시간 범위 선택 옵션"""
    time_range = st.selectbox(
        "시간 범위 선택",
        [
            "최근 1시간",
            "최근 3시간",
            "최근 6시간",
            "최근 12시간",
            "최근 24시간",
            "최근 3일",
            "최근 7일",
            "사용자 지정"
        ]
    )
    
    if time_range == "사용자 지정":
        end_date = st.date_input("종료 날짜", datetime.now())
        end_time = st.time_input("종료 시간", datetime.now().time())
        start_date = st.date_input("시작 날짜", end_date - timedelta(days=1))
        start_time = st.time_input("시작 시간", end_time)
        
        start_dt = datetime.combine(start_date, start_time)
        end_dt = datetime.combine(end_date, end_time)
    else:
        end_dt = datetime.now()
        if time_range == "최근 1시간":
            start_dt = end_dt - timedelta(hours=1)
        elif time_range == "최근 3시간":
            start_dt = end_dt - timedelta(hours=3)
        elif time_range == "최근 6시간":
            start_dt = end_dt - timedelta(hours=6)
        elif time_range == "최근 12시간":
            start_dt = end_dt - timedelta(hours=12)
        elif time_range == "최근 24시간":
            start_dt = end_dt - timedelta(days=1)
        elif time_range == "최근 3일":
            start_dt = end_dt - timedelta(days=3)
        elif time_range == "최근 7일":
            start_dt = end_dt - timedelta(days=7)
    
    return start_dt, end_dt

def fetch_logbook(start_time, end_time, entity_id=None, exclude_entities=None):
    """Home Assistant Logbook API 호출"""
    ha_url = os.getenv('HA_URL')
    if not ha_url:
        st.error("HA_URL이 .env 파일에 설정되지 않았습니다.")
        st.stop()

    # API 엔드포인트 구성
    api_url = f"{ha_url}/api/logbook/{start_time.strftime('%Y-%m-%dT%H:%M:%S')}"
    
    # 쿼리 파라미터 구성
    params = {
        'end_time': end_time.strftime('%Y-%m-%dT%H:%M:%S')
    }
    
    # 엔티티 필터 추가
    if entity_id:
        params['entity'] = entity_id

    try:
        response = requests.get(api_url, headers=get_ha_headers(), params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if data:
            # 필터링할 조건들을 리스트로 관리
            filtered_data = data
            
            # 1. unavailable 상태 제외
            filtered_data = [entry for entry in filtered_data if entry.get('state') != 'unavailable']
            
            # 2. 제외할 엔티티가 있는 경우 필터링
            if exclude_entities:
                # 쉼표나 공백으로 구분된 엔티티를 리스트로 변환
                exclude_list = set(e.strip() for e in exclude_entities.replace(',', ' ').split() if e.strip())
                # 제외할 엔티티를 필터링
                filtered_data = [entry for entry in filtered_data if entry.get('entity_id') not in exclude_list]
            
            return filtered_data
        return data
    except requests.exceptions.RequestException as e:
        st.error(f"API 호출 실패: {str(e)}")
        return None

def main():
    st.title("📖 Home Assistant Logbook Viewer")
    
    # 사이드바 설정
    with st.sidebar:
        st.header("조회 옵션")
        start_time, end_time = get_time_range()
        
        st.subheader("엔티티 필터")
        col1, col2 = st.columns(2)
        with col1:
            entity_filter = st.text_input(
                "포함할 엔티티 ID",
                help="특정 엔티티의 로그만 보려면 입력하세요. (예: light.living_room)"
            )
        with col2:
            exclude_filter = st.text_input(
                "제외할 엔티티 ID",
                help="여러 엔티티를 제외하려면 쉼표나 공백으로 구분하여 입력하세요. (예: sensor.temp1, binary_sensor.motion)"
            )
        
        # 필터 상태 표시
        if entity_filter or exclude_filter:
            st.markdown("---")
            st.markdown("#### 현재 필터 상태")
            if entity_filter:
                st.info(f"포함: {entity_filter}")
            if exclude_filter:
                st.warning(f"제외: {exclude_filter}")
    
    # 로그북 데이터 가져오기
    logbook_data = fetch_logbook(start_time, end_time, entity_filter, exclude_filter)
    
    if logbook_data:
        # 데이터프레임 변환
        df = pd.DataFrame(logbook_data)
        
        if not df.empty:
            # 시간대 정보 추가
            local_tz = pytz.timezone('Asia/Seoul')
            if 'when' in df.columns:
                df['when'] = pd.to_datetime(df['when']).dt.tz_convert(local_tz)
            
            # 필요한 컬럼만 선택하고 순서 재정렬
            available_columns = []
            column_names = {}
            
            if 'when' in df.columns:
                available_columns.append('when')
                column_names['when'] = '시간'
            
            if 'name' in df.columns:
                available_columns.append('name')
                column_names['name'] = '이름'
            
            if 'entity_id' in df.columns:
                available_columns.append('entity_id')
                column_names['entity_id'] = '엔티티 ID'
            
            if 'state' in df.columns:
                available_columns.append('state')
                column_names['state'] = '상태'
            
            if 'domain' in df.columns:
                available_columns.append('domain')
                column_names['domain'] = '도메인'
            
            # 사용 가능한 컬럼만 선택
            df = df[available_columns]
            
            # 컬럼명 한글화
            df = df.rename(columns=column_names)
            
            # 데이터 표시
            st.write(f"총 {len(df)} 개의 로그 항목이 조회되었습니다.")
            
            # 데이터프레임 표시 설정
            st.dataframe(
                df,
                use_container_width=True,
                height=500
            )
            
            # CSV 다운로드 버튼
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "CSV 파일로 다운로드",
                csv,
                "logbook.csv",
                "text/csv",
                key='download-csv'
            )
            
            # API 응답 원본 데이터 보기 옵션
            if st.checkbox("API 응답 원본 데이터 보기"):
                st.json(logbook_data)
        else:
            st.info("해당 기간에 로그 데이터가 없습니다.")
    else:
        st.error("로그북 데이터를 가져오는데 실패했습니다.")

if __name__ == "__main__":
    main() 