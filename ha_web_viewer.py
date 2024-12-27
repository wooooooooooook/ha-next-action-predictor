import streamlit as st
import pandas as pd
from ha_db_reader import HomeAssistantDB
from datetime import datetime, timedelta
import json
from sqlalchemy import text
import pytz
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="Home Assistant DB Viewer",
    page_icon="🏠",
    layout="wide"
)

@st.cache_resource
def get_db_connection():
    """DB 연결을 생성하고 캐시"""
    return HomeAssistantDB()

def format_json(json_str):
    """JSON 문자열을 보기 좋게 포맷팅"""
    try:
        if isinstance(json_str, str):
            return json.dumps(json.loads(json_str), indent=2, ensure_ascii=False)
        return json.dumps(json_str, indent=2, ensure_ascii=False)
    except:
        return json_str

def format_timestamp(ts):
    """타임스탬프를 읽기 쉬운 형식으로 변환"""
    if pd.isna(ts):
        return None
    try:
        return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    except:
        return ts

def get_time_range():
    """시간 범위 선택 옵션"""
    time_range = st.selectbox(
        "시간 범위 선택",
        [
            "전체 기간",
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
        if time_range == "전체 기간":
            return None, None
        elif time_range == "최근 1시간":
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
    
    return start_dt.timestamp(), end_dt.timestamp()

def main():
    st.title("🏠 Home Assistant DB Viewer")
    
    # DB 연결
    ha_db = get_db_connection()
    
    # 사이드바에 테이블 선택 옵션
    with st.sidebar:
        st.header("테이블 선택")
        table_info = ha_db.get_table_info()
        if table_info is not None:
            selected_table = st.selectbox(
                "조회할 테이블을 선택하세요",
                options=table_info['table_name'].tolist()
            )
        
        st.header("조회 옵션")
        # 시간 범위 선택
        start_ts, end_ts = get_time_range()
        
        limit = st.number_input("조회할 행 수", min_value=1, max_value=500000, value=100)
        
        if selected_table == 'states':
            entity_filter = st.text_input("엔티티 ID 필터 (예: light.living_room)")
        elif selected_table == 'events':
            event_type_filter = st.text_input("이벤트 타입 필터 (예: state_changed)")
    
    # 메인 영역
    st.header(f"📊 {selected_table} 테이블 데이터")
    
    if selected_table == 'states':
        # states 테이블과 states_meta 테이블 조인 쿼리
        query = """
        SELECT 
            s.state_id,
            sm.entity_id,
            s.state,
            s.attributes_id,
            s.last_changed_ts,
            s.last_updated_ts,
            s.metadata_id
        FROM states s
        JOIN states_meta sm ON s.metadata_id = sm.metadata_id
        """
        
        where_clauses = []
        params = {'limit': limit}
        
        if entity_filter:
            where_clauses.append("sm.entity_id LIKE :entity_pattern")
            params['entity_pattern'] = f"%{entity_filter}%"
        
        if start_ts is not None and end_ts is not None:
            where_clauses.append("s.last_updated_ts BETWEEN :start_ts AND :end_ts")
            params['start_ts'] = start_ts
            params['end_ts'] = end_ts
        
        if where_clauses:
            query += "\nWHERE " + " AND ".join(where_clauses)
        
        query += "\nORDER BY s.last_updated_ts DESC"
        query += "\nLIMIT :limit"
        
    elif selected_table == 'events':
        # events 테이블과 event_data 테이블 조인 쿼리
        query = """
        SELECT 
            et.event_type as event_type_name,
            e.time_fired_ts,
            ed.shared_data as event_data
        FROM events e
        LEFT JOIN event_data ed ON e.data_id = ed.data_id
        LEFT JOIN event_types et ON e.event_type_id = et.event_type_id
        """
        
        where_clauses = []
        params = {'limit': limit}
        
        if event_type_filter:
            where_clauses.append("(e.event_type LIKE :event_type_pattern OR et.event_type LIKE :event_type_pattern)")
            params['event_type_pattern'] = f"%{event_type_filter}%"
        
        if start_ts is not None and end_ts is not None:
            where_clauses.append("e.time_fired_ts BETWEEN :start_ts AND :end_ts")
            params['start_ts'] = start_ts
            params['end_ts'] = end_ts
        
        if where_clauses:
            query += "\nWHERE " + " AND ".join(where_clauses)
        
        query += "\nORDER BY e.time_fired_ts DESC"
        query += "\nLIMIT :limit"
        
    else:
        # 기본 쿼리 실행
        query = f"""
        SELECT *
        FROM {selected_table}
        LIMIT {limit}
        """
        params = {'limit': limit}
    
    # 디버깅을 위한 쿼리 출력
    st.code(f"실행될 쿼리:\n{query}\n\n파라미터:\n{params}")
    
    try:
        with ha_db.engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)
            
            # 타임스탬프를 읽기 쉬운 형식으로 변환
            timestamp_columns = ['last_changed_ts', 'last_updated_ts', 'time_fired_ts']
            for col in timestamp_columns:
                if col in df.columns:
                    df[col] = df[col].apply(format_timestamp)
            
            # JSON 형식 컬럼 포맷팅
            json_columns = df.select_dtypes(include=['object']).columns
            for col in json_columns:
                try:
                    if col == 'event_data':  # event_data는 JSON으로 파싱
                        df[col] = df[col].apply(format_json)
                except:
                    pass
            
            # 데이터프레임 표시
            if not df.empty:
                st.write(f"총 {len(df)} 개의 행이 조회되었습니다.")
                st.dataframe(
                    df,
                    use_container_width=True,
                    height=500
                )
                
                # 선택된 행 상세 보기
                if st.checkbox("선택한 행 상세 보기"):
                    row_index = st.number_input(
                        "행 번호를 선택하세요",
                        min_value=0,
                        max_value=len(df)-1,
                        value=0
                    )
                    st.json(df.iloc[row_index].to_dict())
            else:
                st.info("조회된 데이터가 없습니다.")
    except Exception as e:
        st.error(f"데이터 조회 실패: {str(e)}")
        return

if __name__ == "__main__":
    main() 