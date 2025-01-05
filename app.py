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
import pycountry
import folium
from folium.plugins import MarkerCluster
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium
import plotly.express as px
from dotenv import load_dotenv
from auth import Authenticator


# MAIN PAGE CONFIG
st.set_page_config(
    page_title="SSSMC YouTube Channels Statistics",
    page_icon="🎥",
    layout="wide")

api_scopes = ["https://www.googleapis.com/auth/yt-analytics.readonly", "https://www.googleapis.com/auth/youtube.readonly"]

client_secret_file = "./client_secret.json"

token_pickle_file = "1"



# --- SESSION STATE VARIABLES ---
if 'channel_handles' not in st.session_state:
    st.session_state['channel_handles'] = ["@SriSathyaSaiOfficial", "@SriSathyaSaiBhajans", "@PrasanthiMandirLiveRadioSai", "@SriSathyaSaiSpeaksOfficial", "@SriSathyaSaiTelugu", "@SriSathyaSaiTamil", "@SriSathyaSaiHindi", "@SriSathyaSaiKannada", "@SriSathyaSaiMalayalam", "@SriSathyaSaiKidsWorld", "@SriSathyaSaiMandarin"]

if 'date_ranges' not in st.session_state:
    st.session_state['date_ranges'] = {
        "Last 7D": (datetime.now() - timedelta(days=7), datetime.now()),
        "Last 28D": (datetime.now() - timedelta(days=28), datetime.now()),
        "Last 3 Months": (datetime.now() - timedelta(days=90), datetime.now()),
        "Last Year": (datetime.now() - timedelta(days=365), datetime.now()),
    }

# --- SESSION STATE VARIABLES ---
if "selected_range" not in st.session_state:
    st.session_state["selected_range"] = "Last 7D"

# --- SESSION STATE UPDATES ---
def update_range():
    st.session_state["selected_range"] = st.session_state["range_selector"]
    
# --- OAUTH INIT ---
def authenticate_with_oauth():
    if "credentials" not in st.session_state:
        flow = Flow.from_client_secrets_file(client_secret_file, scopes=api_scopes)
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
    if os.path.exists(token_pickle_file):
        with open(token_pickle_file, "rb") as token:
            creds = pickle.load(token)

    # Authenticate if no valid credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, api_scopes)
            # Try different ports if default is in use
            for port in range(55574, 55584):
                try:
                    creds = flow.run_local_server(port=port)
                    break
                except OSError:
                    continue

        # Save credentials for the next run
        with open(token_pickle_file, "wb") as token:
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

def get_playlist_name(playlist_id):

    # Fetch the playlist details
    request = youtube.playlists().list(
        part='snippet',
        id=playlist_id
    )
    response = request.execute()

    # Extract and return the playlist title
    if 'items' in response and response['items']:
        playlist_title = response['items'][0]['snippet']['title']
        return playlist_title
    else:
        return None

def get_channel_latest_n_videos(channel_upload_playlist_id, n=10):
    video_details_data = []

    try:
        requestLatestVideos = youtube.playlistItems().list(
            part='snippet',
            maxResults=n,
            playlistId=channel_upload_playlist_id
        )
        response = requestLatestVideos.execute()

        if "items" in response and len(response["items"]) > 0:
            channel_latest_videos = response["items"]

            for video in channel_latest_videos:
                video_details = video["snippet"]
                row = {"Video Title" : video_details["title"]}

                try:
                    requestVideo = youtube.videos().list(
                        part="statistics",
                        id=video_details["resourceId"]["videoId"]
                    )
                    response = requestVideo.execute()
                    if "items" in response and len(response["items"]) > 0:
                        video_stats = response["items"][0]["statistics"]
                        row.update({"Video Views" : video_stats["viewCount"], "Video Likes" : video_stats["likeCount"], "Video Comments" : video_stats["commentCount"]})
                    else:
                        print(f"No video statistics found for video ID: {video_details['resourceId']['videoId']}")
                except Exception as e:
                    print(f"An error occurred in accessing Video Details: {e}")

                row.update({"Video ID" : video_details["resourceId"]["videoId"], "Video Published At" : video_details["publishedAt"],})

                video_details_data.append(row)
        else:
            print("No videos found in the playlist.")
    except Exception as e:
        print(f"An error occurred in accessing Channel Videos: {e}")

    return video_details_data

def get_channel_top_n_videos(channel_id, n=10):
    video_details_data = []
    try:
        requestTopVideos = youtube.search().list(
            part='snippet',
            channelId=channel_id,
            maxResults=n,
            order="viewCount",
        )
        response = requestTopVideos.execute()

        if "items" in response and len(response["items"]) > 0:
            channel_latest_videos = response["items"]

            for video in channel_latest_videos:
                video_details = video["snippet"]
                row = {"Video Title" : video_details["title"]}

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

                video_details_data.append(row)
        else:
            print("No videos found in the playlist.")
    except Exception as e:
        print(f"An error occurred in accessing Channel Videos: {e}")

    return video_details_data
 

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


# --- GET COUNTRY COORDS FROM GEO.L ---
def get_country_coordinates(country_code):
    try:
        country = pycountry.countries.get(alpha_2=country_code)
        if country:
            location = geolocator.geocode(country.name)
            if location:
                return (location.latitude, location.longitude)
    except Exception as e:
        print(f"Error fetching coordinates for {country_code}: {e}")
    return None

# --- GET COUNTRY NAME FROM CODE ---
def get_country_name(country_code):
    try:
        country = pycountry.countries.get(alpha_2=country_code.upper())
        return country.name if country else "Unknown country code"
    except Exception as e:
        return f"Error: {e}"


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


# SSSMC CUMULATIVE STATS
st.subheader("Channel Wise Statistics")

# CHANNEL SELECTION
channel_filter = st.selectbox("Select the channel", pd.unique(df_handles_data["Channel Handle"]))

# FILTER DF BASED ON CHANNEL SELECTION
df_handles_data_filtered = df_handles_data[df_handles_data["Channel Handle"] == channel_filter]
filtered_handle_rows_dict = df_handles_data_filtered.to_dict(orient="records")

# MAIN STATS
kpi1, kpi2, kpi3 = st.columns(3)

# CHANNEL CUMULATIVE STATS

kpi1.metric(
    label="Total Channel Views",
    value=f"{int(filtered_handle_rows_dict[0]["Cumulative Views"]):,d}",
)

kpi2.metric(
    label="Channel Subscribers",
    value=f"{int(filtered_handle_rows_dict[0]["Subscribers"]):,d}",
)

kpi3.metric(
    label="No. of Videos",
    value=f"{int(filtered_handle_rows_dict[0]["Videos Published"]):,d}",
)

filtered_handle = filtered_handle_rows_dict[0]["Channel Handle"]

filtered_handle_id = get_channel_id(filtered_handle)
filtered_handle_upload_playlist_id = get_channel_upload_playlist(filtered_handle)

# LATEST, TOP, SEARCH STATS

tab1, tab2 = st.tabs(["Latest Videos", "Top Videos"])

# LATEST VIDEOS STATS

with tab1:
    st.header("Latest Videos")
    filtered_handle_latest_videos_data = get_channel_latest_n_videos(filtered_handle_upload_playlist_id)
    df_filtered_handle_latest_videos_data = pd.DataFrame(filtered_handle_latest_videos_data)
    st.table(df_filtered_handle_latest_videos_data)

# TOP VIDEOS STATS

with tab2:
    st.header("Top Videos")
    filtered_handle_top_videos_data = get_channel_top_n_videos(filtered_handle_id)
    df_filtered_handle_top_videos_data = pd.DataFrame(filtered_handle_top_videos_data)
    st.table(df_filtered_handle_top_videos_data)


addn_stats_header, time_selector = st.columns([0.3, 0.7])

with addn_stats_header:
    st.subheader("Additional Statistics")

with time_selector:
    # TIME PERIOD SELECTOR

    time_selector_box, selected_time_display = st.columns([0.60, 0.40])

    with time_selector_box:
        # Tab selector
        selected_range = st.selectbox(
            "Select Date Range:",
            options=list(st.session_state['date_ranges'].keys()),
            index=list(st.session_state['date_ranges'].keys()).index(st.session_state["selected_range"]),
            key="range_selector",
            on_change=update_range,
        )
    
    with selected_time_display:
        # Set start_date and end_date based on the selected range
        start_date, end_date = st.session_state['date_ranges'][st.session_state["selected_range"]]

        # Display the selected range in a specific section
        with st.container():  # Isolated section
            st.write("Selected Date Range:")
            if start_date:
                st.write(f"{start_date.strftime('%d-%m-%Y')} - {end_date.strftime('%d-%m-%Y')}")
            else:
                st.write(f"Start Date: {selected_range}")

st.write("---")

# Fetch and display analytics

# FORMATTING DATE FOR REQUEST
if start_date:
    formatted_start_date = start_date.strftime("%Y-%m-%d")
formatted_end_date = end_date.strftime("%Y-%m-%d")


# FETCH AND AUTHENTICATE BUTTONS
col_1, col_2 = st.columns([1, 1])

# Button to fetch data
if col_1.button("Fetch Data"):

    col_1_1, col_1_2 = st.columns(2)

    try:
        with col_1_1:
            st.subheader("Views by Traffic Source (Excluding Shorts)")
            traffic_source_data = fetch_analytics(
                youtube_analytics,
                filtered_handle_id,
                formatted_start_date,
                formatted_end_date,
                dimensions="insightTrafficSourceType",
                metrics="views",
                sort="-views",
            )
            traffic_source_df = pd.DataFrame(traffic_source_data, columns=["Traffic Source", "Views"])
            traffic_source_filtered_df = traffic_source_df[traffic_source_df['Traffic Source'] != 'SHORTS']
            st.write("Traffic Source Statistics:")
            # st.table(traffic_source_df)
            st.bar_chart(traffic_source_filtered_df, x='Traffic Source', y='Views', x_label="Traffic Source", y_label="Views", color='#29b5e8', horizontal=True) 
        
        with col_1_2:
            st.subheader("Views by Country (Excluding India and US)")
            country_data = fetch_analytics(
                youtube_analytics,
                filtered_handle_id,
                formatted_start_date,
                formatted_end_date,
                dimensions="country",
                metrics="views",
                sort="-views",
                max_results=25,  # Top 25 countries excluding India and US
            )
            country_views_df = pd.DataFrame(country_data, columns=["Country Code", "Views"])
            # Apply the function to create a new column
            country_views_df['Country Name'] = country_views_df['Country Code'].apply(get_country_name)
            country_views_df = country_views_df[country_views_df['Country Name'] != 'India']
            country_views_df = country_views_df[country_views_df['Country Name'] != 'United States']
            country_views_filtered_df = country_views_df[['Country Code', 'Country Name', 'Views']]
            st.write("Top 25 Countries by Views:")
            # st.table(country_views_filtered_df)
            st.bar_chart(country_views_filtered_df, x='Country Name', y='Views', x_label="Country Name", y_label="Views", color='#29b5e8', horizontal=True) 

        col_2_1, col_2_2 = st.columns(2)

        with col_2_1:
            st.subheader("Views by Device Type")
            device_data = fetch_analytics(
                youtube_analytics,
                filtered_handle_id,
                formatted_start_date,
                formatted_end_date,
                dimensions="deviceType",
                metrics="views",
                sort="-views",
            )
            device_views_df = pd.DataFrame(device_data, columns=["Device Type", "Views"])
            st.write("Views by Device Type:")
            st.table(device_views_df)
            # st.bar_chart(device_views_df, x='Device Type', y='Views', x_label="Device Type", y_label="Views", color='#D45B90', horizontal=True)
        
        with col_2_2:
            st.subheader("Playlist Stats")
            playlist_stats_data = fetch_analytics(
                youtube_analytics,
                filtered_handle_id,
                formatted_start_date,
                formatted_end_date,
                dimensions="playlist",
                metrics="playlistViews,playlistEstimatedMinutesWatched,playlistStarts,averageTimeInPlaylist,playlistSaves",
                max_results=10,
                sort="-playlistViews",
            )
            playlist_stats_df = pd.DataFrame(playlist_stats_data, columns=["Playlist ID", "Views", "Minutes Watched", "Starts", "Avg Time in Playlist", "Saves"])
            playlist_stats_df['Playlist Name'] = playlist_stats_df['Playlist ID'].apply(get_playlist_name)
            playlist_stats_df = playlist_stats_df[['Playlist Name', 'Views', 'Minutes Watched', 'Starts', 'Avg Time in Playlist', 'Saves']]
            st.write("Playlist Stats:")
            # st.table(playlist_stats_df)
            st.bar_chart(playlist_stats_df, x='Playlist Name', y='Views', x_label="Playlist Name", y_label="Playlist Views", color='#FF9F36', horizontal=True)
            
    except Exception as e:
        st.error(f"Error: {e}")

# Button to reset authentication
if col_2.button("Reset Authentication"):
    try:
        if os.path.exists(token_pickle_file):
            os.remove(token_pickle_file)
            youtube, youtube_analytics = get_authenticated_service()
            st.session_state['youtube'] = youtube
            st.session_state['youtube_analytics'] = youtube_analytics
            st.success("Authentication successful!")
            st.write("You can now fetch analytics data.")
        else:
            st.warning("No token file found to delete.")
    except Exception as e:
        st.error(f"Error: {e}")