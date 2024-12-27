import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import pandas as pd
from datetime import datetime, timedelta

# .env 파일에서 환경 변수 로드
load_dotenv()

class HomeAssistantDB:
    def __init__(self):
        # PostgreSQL DB 연결 문자열
        self.db_url = os.getenv('DB_URL')
        self.engine = create_engine(self.db_url)

    def test_connection(self):
        """DB 연결 테스트"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT version()"))
                version = result.scalar()
                print(f"PostgreSQL 버전: {version}")
                return True
        except Exception as e:
            print(f"DB 연결 실패: {str(e)}")
            return False

    def get_states_history(self, limit=1000):
        """상태 이력 조회"""
        query = """
        SELECT 
            state_id,
            state,
            entity_id,
            attributes,
            last_updated,
            last_changed
        FROM states
        ORDER BY last_updated DESC
        LIMIT :limit
        """
        try:
            with self.engine.connect() as conn:
                df = pd.read_sql(text(query), conn, params={'limit': limit})
                return df
        except Exception as e:
            print(f"데이터 조회 실패: {str(e)}")
            return None

    def get_table_info(self):
        """테이블 정보 조회"""
        query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        """
        try:
            with self.engine.connect() as conn:
                df = pd.read_sql(text(query), conn)
                print("\n사용 가능한 테이블:")
                print(df)
                return df
        except Exception as e:
            print(f"테이블 정보 조회 실패: {str(e)}")
            return None

    def get_logbook(self, start_time=None, end_time=None, entity_id=None):
        """특정 기간의 로그북 조회
        
        Args:
            start_time (datetime): 시작 시간 (기본값: 24시간 전)
            end_time (datetime): 종료 시간 (기본값: 현재)
            entity_id (str): 특정 엔티티 ID (선택사항)
        """
        if start_time is None:
            start_time = datetime.now() - timedelta(days=1)
        if end_time is None:
            end_time = datetime.now()

        query = """
        SELECT 
            l.time_fired,
            l.entity_id,
            l.domain,
            l.message,
            l.context_id,
            s.state as entity_state,
            s.attributes as entity_attributes
        FROM logbook l
        LEFT JOIN states s ON l.entity_id = s.entity_id 
            AND s.last_updated <= l.time_fired 
            AND s.state_id = (
                SELECT state_id 
                FROM states 
                WHERE entity_id = l.entity_id 
                AND last_updated <= l.time_fired 
                ORDER BY last_updated DESC 
                LIMIT 1
            )
        WHERE l.time_fired BETWEEN :start_time AND :end_time
        """
        
        if entity_id:
            query += " AND l.entity_id = :entity_id"
        
        query += " ORDER BY l.time_fired DESC"
        
        params = {
            'start_time': start_time,
            'end_time': end_time,
            'entity_id': entity_id
        }
        
        try:
            with self.engine.connect() as conn:
                df = pd.read_sql(text(query), conn, params=params)
                return df
        except Exception as e:
            print(f"로그북 조회 실패: {str(e)}")
            return None

def main():
    ha_db = HomeAssistantDB()
    
    # DB 연결 테스트
    if ha_db.test_connection():
        print("DB 연결 성공")
        
        # 테이블 정보 조회
        ha_db.get_table_info()
        
    else:
        print("DB 연결에 실패했습니다.")

if __name__ == "__main__":
    main() 