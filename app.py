from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from google.auth.transport.requests import Request
import  pandas as pd
import os
import pickle
import streamlit as st
import time
import httplib2
import ssl
from requests.adapters import HTTPAdapter
from datetime import timedelta, datetime
from requests.packages.urllib3.util.retry import Retry
import plotly.express as px


# MAIN PAGE CONFIG
st.set_page_config(
    page_title="SSSMC YouTube Channels Statistics",
    page_icon="🎥",
    layout="wide")

# --- SESSION STATE VARIABLES ---
if 'client_secret_file' not in st.session_state:
    st.session_state['client_secret_file'] = "./client_secret.json"  # Replace with your OAuth client secrets file

if 'api_scopes' not in st.session_state:
    st.session_state['api_scopes'] = ["https://www.googleapis.com/auth/yt-analytics.readonly", "https://www.googleapis.com/auth/youtube.readonly"]

if 'token_pickle_file' not in st.session_state:
    st.session_state['token_pickle_file'] = "./token.pickle"

if 'channel_handles' not in st.session_state:
    st.session_state['channel_handles'] = ["@SriSathyaSaiOfficial", "@SriSathyaSaiBhajans", "@PrasanthiMandirLiveRadioSai", "@SriSathyaSaiSpeaksOfficial", "@SriSathyaSaiTelugu", "@SriSathyaSaiTamil", "@SriSathyaSaiHindi", "@SriSathyaSaiKannada", "@SriSathyaSaiMalayalam", "@SriSathyaSaiKidsWorld", "@SriSathyaSaiMandarin"]

if 'date_ranges' not in st.session_state:
    st.session_state['date_ranges'] = {
        "Last 7D": (datetime.now() - timedelta(days=7), datetime.now()),
        "Last 28D": (datetime.now() - timedelta(days=28), datetime.now()),
        "Last 3 Months": (datetime.now() - timedelta(days=90), datetime.now()),
        "Last Year": (datetime.now() - timedelta(days=365), datetime.now()),
    }

# --- OAUTH INIT ---
def authenticate_with_oauth():
    if "credentials" not in st.session_state:
        flow = Flow.from_client_secrets_file(st.session_state['client_secret_file'], scopes=st.session_state['api_scopes'])
        flow.redirect_uri = st.secrets["redirect_uri"]

        authorization_url, _ = flow.authorization_url(prompt='consent')
        st.session_state["flow"] = flow
        st.write("Please authenticate using the link below:")
        st.markdown(f"[Authenticate here]({authorization_url})")
    else:
        credentials = st.session_state["credentials"]
        return build("youtubeAnalytics", "v2", credentials=credentials)

# --- OAUTH CALLBACK ---
def handle_oauth_callback():
    flow = st.session_state["flow"]
    flow.fetch_token(authorization_response=st.experimental_get_query_params()["code"])
    credentials = flow.credentials
    st.session_state["credentials"] = credentials

# --- GET YOUTUBE, YOUTUBE ANALYTICS OBJECTS ---
def get_authenticated_service():
    creds = None

    # Load credentials if they exist
    if os.path.exists(st.session_state['token_pickle_file']):
        with open(st.session_state['token_pickle_file'], "rb") as token:
            creds = pickle.load(token)

    # Authenticate if no valid credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(st.session_state['client_secret_file'], st.session_state['api_scopes'])
            # Try different ports if default is in use
            for port in range(55574, 55584):
                try:
                    creds = flow.run_local_server(port=port)
                    break
                except OSError:
                    continue

        # Save credentials for the next run
        with open(st.session_state['token_pickle_file'], "wb") as token:
            pickle.dump(creds, token)

    # Create HTTP object with proper SSL verification
    http = httplib2.Http(timeout=30)

    # Build the YouTube Data API v3 and Analytics API v2 clients
    youtube = build("youtube", "v3", credentials=creds)
    youtube_analytics = build("youtubeAnalytics", "v2", credentials=creds)
    
    return youtube, youtube_analytics

youtube, youtube_analytics = get_authenticated_service()

if 'youtube' not in st.session_state:
    st.session_state['youtube'] = youtube

if 'youtube_analytics' not in st.session_state:
    st.session_state['youtube_analytics'] = youtube_analytics

def get_channel_statistics(handle):
    requestChannelStats = youtube.channels().list(
            part="statistics",
            forHandle=handle
        )
    response = requestChannelStats.execute()
    channel_stats = response["items"][0]["statistics"]

    return channel_stats

def get_channel_id(handle):
    requestPlaylistID = youtube.channels().list(
                part="contentDetails,statistics",
                forHandle=handle
            )
    response = requestPlaylistID.execute()
    # channel_playlist_id = response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    # print(response["items"][0]["id"])
    channel_id = response["items"][0]["id"]
    return channel_id

def get_channel_upload_playlist(handle):
    requestPlaylistID = youtube.channels().list(
                part="contentDetails,statistics",
                forHandle=handle
            )
    response = requestPlaylistID.execute()
    channel_playlist_id = response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    return channel_playlist_id

def get_handles_stats(handles):
    handles_stats = []
    for handle in handles:
        try:
            # Add retry mechanism with backoff
            for attempt in range(3):
                try:
                    request = youtube.channels().list(
                        part="statistics",
                        forHandle=handle,
                    )
                    response = request.execute()
                    break
                except Exception:
                    if attempt == 2:
                        raise
                    time.sleep(2 ** attempt)
            
            # Extract the statistics object
            if "items" in response and len(response["items"]) > 0:
                stats = response["items"][0]["statistics"]
                # Add the channel handle and statistics to the row
                row = {"Channel Handle": handle}
                row.update({"Cumulative Views" : stats["viewCount"], "Subscribers" : stats["subscriberCount"], "Videos Published" : stats["videoCount"]})  # Add all statistics keys and values
                handles_stats.append(row)
            else:
                print(f"No data found for handle: {handle}")
        except Exception as e:
            print(f"Error fetching data for handle: {handle}. Error: {e}")
    
    return handles_stats

def get_video_stats_by_search(search_channel_id, search_query, n=20):
    video_search_results_data = []

    try:
        requestSearchResults = youtube.search().list(
            part='snippet',
            q=search_query,
            maxResults=n,
            channelId=search_channel_id,
            type="video"
        )

        response = requestSearchResults.execute()
        if "items" in response and len(response["items"]) > 0:
            search_result_videos = response["items"]

        if search_result_videos:
            for video in search_result_videos:
                video_details = video["snippet"]
                row = {"Video Title" : video_details["title"]}
                row.update({"Video Thumbnail URL": video_details["thumbnails"]["medium"]["url"]})
                try:
                    requestVideo = youtube.videos().list(
                        part="statistics",
                        id=video["id"]["videoId"]
                    )
                    response = requestVideo.execute()
                    if "items" in response and len(response["items"]) > 0:
                        video_stats = response["items"][0]["statistics"]
                        row.update({"Video Views" : video_stats["viewCount"], "Video Likes" : video_stats["likeCount"], "Video Comments" : video_stats["commentCount"]})
                    else:
                        print(f"No video statistics found for video ID: {video_details['resourceId']['videoId']}")
                except Exception as e:
                    print(f"An error occurred in accessing Video Details: {e}")
                
                row.update({"Video ID" : video["id"]["videoId"], "Video Published At" : video_details["publishedAt"],})

                video_search_results_data.append(row)

    except Exception as e:
        print(f"An error occurred in accessing Video Search Results: {e}")
    
    return video_search_results_data

def get_traffic_source_interactive_bar(dataframe):
    # Create a pie chart
    fig = px.bar(dataframe, x=dataframe["Views"], y=dataframe["Traffic Source"], orientation='h', labels={'Views': 'Number of Views', 'Traffic Source': 'Traffic Source'}, title='Views by Traffic Source')
    return fig
    
def fetch_analytics(youtube_analytics, channel_id, start_date, end_date, dimensions, metrics, max_results=None, sort="-views"):
    query = {
        "ids": f"channel==MINE",
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": dimensions,
        "metrics": metrics,
        "sort": sort,
    }
    if max_results:
        query["maxResults"] = max_results

    response = youtube_analytics.reports().query(**query).execute()
    return response.get("rows", [])

handles_data = get_handles_stats(st.session_state['channel_handles'])
df_handles_data = pd.DataFrame(handles_data)

# --- UI SECTION ---

# MAIN HEADING
st.title("🎥 SSSMC YouTube Channels Statistics")

# SSSMC CUMULATIVE STATS
st.subheader("SSSMC Cumulative Statistics (Across all channels)")
kpi_all1, kpi_all2, kpi_all3 = st.columns(3)

kpi_all1.metric(
    label="Cumulative Views",
    value=f"{df_handles_data["Cumulative Views"].astype(int).sum():,d}",
)

kpi_all2.metric(
    label="Subscribers",
    value=f"{df_handles_data["Subscribers"].astype(int).sum():,d}",
)

kpi_all3.metric(
    label="No. of Videos",
    value=f"{df_handles_data["Videos Published"].astype(int).sum():,d}",
)

st.write("---")

# # SEARCH VIDEOS STATS

# with tab3:
#     st.header("Search for a video in this channel to see its statistics")
#     text_search = st.text_input("Search videos of this channel...", value="")
#     print(text_search)

#     if text_search:
#         video_search_results_data = get_video_stats_by_search(filtered_handle_id, text_search)
#         df_video_search_results_data = pd.DataFrame(video_search_results_data)
#         st.subheader("Search Results")

#         # st.table(df_video_search_results_data)

#         N_cards_per_row = 4
#         if df_video_search_results_data.shape[0] > 0:
#             for n_row, row in df_video_search_results_data.reset_index().iterrows():
#                 i = n_row%N_cards_per_row
#                 if i==0:
#                     st.write("---")
#                     cols = st.columns(N_cards_per_row, gap="large")
#                 # draw the card
#                 with cols[n_row%N_cards_per_row]:
#                     # st.image(row["Video Thumbnail URL"])
#                     # st.markdown("[![Foo](row["Video Thumbnail URL"])](http://google.com.au/)")
#                     html_str = f"""
#                     <a href="https://www.youtube.com/watch?v={row['Video ID'].strip()}">
#                     <img src="{row['Video Thumbnail URL'].strip()}" alt="Video Thumbnail"></a>
#                     """
#                     st.markdown(html_str, unsafe_allow_html=True)
#                     st.markdown(f"**{row['Video Title'].strip()}**")
#                     st.markdown(f"Views: {int(row['Video Views'].strip()):,d}")
#                     st.markdown(f"Likes: {int(row['Video Likes']):,d}")
