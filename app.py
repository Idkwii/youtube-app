import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from datetime import datetime, timedelta

# 페이지 설정
st.set_page_config(page_title="유튜브 분석기", layout="wide")

st.title("📺 우리 팀 유튜브 분석 대시보드")

# 1. 사이드바: 설정 및 채널 추가
with st.sidebar:
    st.header("설정")
    # API 키 입력받기
    api_key = st.text_input("YouTube API Key를 입력하세요", type="password")
    
    st.divider()
    
    st.header("채널 관리")
    # 세션 상태 초기화 (새로고침 해도 데이터 유지)
    if 'channels' not in st.session_state:
        st.session_state['channels'] = {} # {핸들: 폴더명}
    
    # 채널 추가 입력
    new_channel = st.text_input("채널 핸들(@이름) 또는 ID")
    folder_options = ["기본", "경쟁사", "벤치마킹", "우리팀"]
    selected_folder = st.selectbox("폴더 선택", folder_options)
    
    if st.button("채널 추가"):
        if new_channel:
            st.session_state['channels'][new_channel] = selected_folder
            st.success(f"{new_channel} 추가 완료!")

    # 추가된 채널 목록 보여주기
    st.write("---")
    st.write("📋 추가된 채널 목록")
    for ch, folder in st.session_state['channels'].items():
        st.write(f"📂 [{folder}] {ch}")

# 2. 메인 화면: 데이터 분석
if not api_key:
    st.warning("👈 왼쪽 사이드바에 API Key를 먼저 입력해주세요!")
    st.stop()

if not st.session_state['channels']:
    st.info("👈 왼쪽에서 분석할 채널을 추가해주세요.")
    st.stop()

# 데이터 수집 함수
def get_channel_stats(api_key, channels_dict):
    youtube = build('youtube', 'v3', developerKey=api_key)
    all_videos = []
    
    today = datetime.now()
    week_ago = (today - timedelta(days=7)).isoformat() + "Z"

    for handle, folder in channels_dict.items():
        try:
            # 1. 채널 ID 찾기
            if handle.startswith('@'):
                search_response = youtube.search().list(part='snippet', q=handle, type='channel').execute()
                if not search_response['items']: continue
                channel_id = search_response['items'][0]['snippet']['channelId']
            else:
                channel_id = handle

            # 2. 최근 영상 가져오기
            videos_response = youtube.search().list(
                part='snippet,id', channelId=channel_id, order='date', 
                publishedAfter=week_ago, type='video', maxResults=10
            ).execute()

            for item in videos_response['items']:
                video_id = item['id']['videoId']
                # 3. 영상 상세 정보(통계, 길이) 가져오기
                stats_response = youtube.videos().list(
                    part='snippet,statistics,contentDetails', id=video_id
                ).execute()
                
                if not stats_response['items']: continue
                vid = stats_response['items'][0]
                
                # 길이 파싱 (PT1M30S 등)
                duration_str = vid['contentDetails']['duration']
                is_short = 'M' not in duration_str and 'S' in duration_str or (duration_str.find('M') != -1 and int(duration_str.split('M')[0].replace('PT','')) < 1)

                stats = vid['statistics']
                all_videos.append({
                    '썸네일': vid['snippet']['thumbnails']['default']['url'],
                    '제목': vid['snippet']['title'],
                    '채널명': vid['snippet']['channelTitle'],
                    '폴더': folder,
                    '게시일': vid['snippet']['publishedAt'][:10],
                    '조회수': int(stats.get('viewCount', 0)),
                    '좋아요': int(stats.get('likeCount', 0)),
                    '댓글': int(stats.get('commentCount', 0)),
                    '링크': f"https://www.youtube.com/watch?v={video_id}",
                    '타입': '숏폼' if is_short else '롱폼'
                })
        except Exception as e:
            st.error(f"에러 발생 ({handle}): {e}")
            
    return pd.DataFrame(all_videos)

# 실행 버튼
if st.button("📊 분석 시작하기"):
    with st.spinner("데이터를 불러오는 중..."):
        df = get_channel_stats(api_key, st.session_state['channels'])
        
        if df.empty:
            st.write("최근 1주일간 올라온 영상이 없습니다.")
        else:
            # 상단 필터
            filter_type = st.radio("영상 길이 선택", ["전체", "롱폼", "숏폼"], horizontal=True)
            if filter_type != "전체":
                df = df[df['타입'] == filter_type]

            # 요약 카드
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("총 영상 수", f"{len(df)}개")
            c2.metric("총 조회수", f"{df['조회수'].sum():,}회")
            c3.metric("총 좋아요", f"{df['좋아요'].sum():,}개")
            c4.metric("총 댓글", f"{df['댓글'].sum():,}개")

            # 데이터 표 보여주기 (이미지, 링크 기능 포함)
            st.dataframe(
                df,
                column_config={
                    "썸네일": st.column_config.ImageColumn("썸네일"),
                    "링크": st.column_config.LinkColumn("링크", display_text="보러가기"),
                    "조회수": st.column_config.NumberColumn(format="%d"),
                    "좋아요": st.column_config.NumberColumn(format="%d"),
                    "댓글": st.column_config.NumberColumn(format="%d"),
                },
                hide_index=True
            )
