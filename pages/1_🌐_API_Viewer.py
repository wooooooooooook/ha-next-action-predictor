import streamlit as st
import pandas as pd
import json
import os
import requests
from dotenv import load_dotenv
import sys

# .env 파일 로드
load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="Home Assistant API Viewer",
    page_icon="🌐",
    layout="wide"
)

class HAApi:
    def __init__(self):
        self.base_url = os.getenv('HA_URL')  # HA 주소
        self.token = os.getenv('HA_TOKEN')
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def get_states(self):
        """현재 모든 엔티티의 상태를 조회"""
        try:
            response = requests.get(f"{self.base_url}/api/states", headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            st.error(f"HA API 호출 실패: {str(e)}")
            return None

@st.cache_resource
def get_ha_api():
    """HA API 클라이언트를 생성하고 캐시"""
    return HAApi()

def get_object_size(obj):
    """객체의 메모리 크기를 계산"""
    return len(json.dumps(obj).encode('utf-8'))

def format_size(size_bytes):
    """바이트 크기를 읽기 쉬운 형식으로 변환"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def main():
    st.title("🌐 Home Assistant API Viewer")
    
    # API 클라이언트 초기화
    ha_api = get_ha_api()
    
    # 필터 옵션
    with st.sidebar:
        st.header("필터 옵션")
        entity_filter = st.text_input("엔티티 ID 필터 (예: light.living_room)")
    
    # 메인 영역
    col1, col2 = st.columns([2, 3])
    
    with col1:
        st.header("엔티티 목록")
        
        # 세션 상태 초기화
        if 'current_states' not in st.session_state:
            st.session_state.current_states = None
        
        if st.button("새로고침", key="refresh_api"):
            st.session_state.current_states = ha_api.get_states()
        
        # 데이터가 없으면 자동으로 처음 로드
        if st.session_state.current_states is None:
            st.session_state.current_states = ha_api.get_states()
        
        if st.session_state.current_states:
            # 데이터프레임으로 변환
            states_data = []
            for state in st.session_state.current_states:
                domain = state['entity_id'].split('.')[0]
                states_data.append({
                    'domain': domain,
                    'entity_id': state['entity_id'],
                    'state': state['state'],
                    'last_updated': state['last_updated'],
                    'size': get_object_size(state)
                })
            
            df_current = pd.DataFrame(states_data)
            
            # 도메인 체크박스 생성
            st.subheader("도메인 필터")
            domains = sorted(df_current['domain'].unique())
            
            # 전체 선택/해제 버튼
            cols = st.columns(2)
            with cols[0]:
                if st.button("전체 선택"):
                    st.session_state.selected_domains = domains
            with cols[1]:
                if st.button("전체 해제"):
                    st.session_state.selected_domains = []
            
            # 세션 상태에 선택된 도메인 저장
            if 'selected_domains' not in st.session_state:
                st.session_state.selected_domains = domains
            
            # 도메��별 체크박스 생성 (3열로 표시)
            domain_cols = st.columns(3)
            for i, domain in enumerate(domains):
                with domain_cols[i % 3]:
                    if st.checkbox(
                        f"{domain} ({len(df_current[df_current['domain'] == domain])})",
                        value=domain in st.session_state.selected_domains,
                        key=f"domain_{domain}"
                    ):
                        if domain not in st.session_state.selected_domains:
                            st.session_state.selected_domains.append(domain)
                    else:
                        if domain in st.session_state.selected_domains:
                            st.session_state.selected_domains.remove(domain)
            
            # 필터 적용
            if entity_filter:
                df_current = df_current[df_current['entity_id'].str.contains(entity_filter, case=False)]
            
            # 선택된 도메인 필터 적용
            df_filtered = df_current[df_current['domain'].isin(st.session_state.selected_domains)]
            
            # 선택된 도메인의 총 데이터 크기 계산
            total_size = df_filtered['size'].sum()
            st.info(f"선택된 도메인의 총 데이터 크기: {format_size(total_size)}")
            
            # 도메인별 통계
            st.subheader("도메인별 엔티티 수")
            domain_counts = df_filtered['domain'].value_counts()
            st.bar_chart(domain_counts)
            
            # 도메인별 데이터 크기
            st.subheader("도메인별 데이터 크기")
            domain_sizes = df_filtered.groupby('domain')['size'].sum()
            domain_sizes_df = pd.DataFrame({
                'domain': domain_sizes.index,
                'size_formatted': domain_sizes.apply(format_size),
                'size': domain_sizes
            })
            st.dataframe(
                domain_sizes_df[['domain', 'size_formatted']],
                use_container_width=True
            )
            
            # 엔티티 목록 표시
            st.subheader(f"엔티티 목록 (총 {len(df_filtered)} 개)")
            display_df = df_filtered.copy()
            display_df['size'] = display_df['size'].apply(format_size)
            st.dataframe(
                display_df,
                use_container_width=True,
                height=400
            )
    
    with col2:
        # 선택된 도메인의 전체 데이터 표시
        st.header("선택된 도메인 데이터")
        if st.session_state.current_states and not df_filtered.empty:
            # 선택된 도메인의 모든 엔티티 데이터 수집
            selected_entities_data = [
                state for state in st.session_state.current_states 
                if state['entity_id'].split('.')[0] in st.session_state.selected_domains
            ]
            
            # 데이터 크기 계산 및 표시
            total_size = sum(get_object_size(state) for state in selected_entities_data)
            st.info(f"전체 데이터 크기: {format_size(total_size)}")
            
            # 전체 데이터를 JSON으로 변환
            json_data = json.dumps(selected_entities_data, indent=2, ensure_ascii=False)
            
            # 데이터 복사를 위한 텍스트 영역과 버튼
            st.text_area("전체 데이터 (복사하려면 선택 후 Ctrl+C)", json_data, height=200)
            
            # 데이터 다운로드 버튼
            st.download_button(
                label="JSON 파일로 다운로드",
                data=json_data,
                file_name="selected_domains_data.json",
                mime="application/json"
            )
        
        # 개별 엔티티 상세 정보 표시
        st.header("엔티티 상세 정보")
        if st.session_state.current_states and not df_filtered.empty:
            # 엔티티 선택
            entity_options = sorted(df_filtered['entity_id'].tolist())
            selected_entity = st.selectbox(
                "엔티티 선택",
                options=entity_options
            )
            
            if selected_entity:
                # 선택된 엔티티 정보 찾기
                entity_data = next(
                    (state for state in st.session_state.current_states 
                     if state['entity_id'] == selected_entity),
                    None
                )
                if entity_data:
                    # 주요 정보 표시
                    st.subheader("기본 정보")
                    cols = st.columns(4)
                    with cols[0]:
                        st.metric("상태", entity_data['state'])
                    with cols[1]:
                        st.metric("도메인", entity_data['entity_id'].split('.')[0])
                    with cols[2]:
                        st.metric("마지막 업데이트", entity_data['last_updated'].split('T')[1].split('.')[0])
                    with cols[3]:
                        st.metric("데이터 크기", format_size(get_object_size(entity_data)))
                    
                    # 전체 데이터 표시
                    st.subheader("전체 데이터")
                    st.json(entity_data)

if __name__ == "__main__":
    main() 