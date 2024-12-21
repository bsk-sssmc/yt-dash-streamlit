from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import  pandas as pd
import os
import pickle
import streamlit as st
from datetime import timedelta, datetime

# Define the scopes
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]

api_key = os.getenv('YOUTUBE_API_KEY')

channel_handles = ["@SriSathyaSaiOfficial", "@SriSathyaSaiBhajans", "@PrasanthiMandirLiveRadioSai", "@SriSathyaSaiSpeaksOfficial", "@SriSathyaSaiTelugu", "@SriSathyaSaiTamil", "@SriSathyaSaiHindi", "@SriSathyaSaiKannada", "@SriSathyaSaiMalayalam", "@SriSathyaSaiKidsWorld", "@SriSathyaSaiMandarin"]


def get_authenticated_service():
    creds = None
    # Load credentials if they exist
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    # Authenticate if no valid credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("./client_secret.json", SCOPES)
            creds = flow.run_local_server(port=55574)
        # Save credentials for the next run
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)
    return build("youtube", "v3", credentials=creds)

youtube = get_authenticated_service()

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

def get_handles_stats(handles):
    handles_stats = []
    for handle in handles:
        try:
            # Make the API request
            request = youtube.channels().list(
                part="statistics",
                forHandle=handle
            )
            response = request.execute()
            
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

handles_data = get_handles_stats(channel_handles)
df_handles_data = pd.DataFrame(handles_data)

# STREAMLIT SECTION

# Testing and Debugging
# st.write("Selected Channel:", channel_filter)
# st.write("Filtered DataFrame:", df_handles_data_filtered)
# st.write("Filtered Handles Rows Dictionary:", filtered_handle_rows_dict)

# MAIN PAGE CONFIG
st.set_page_config(
    page_title="SSSMC YouTube Channels Statistics",
    page_icon="🎥",
    layout="wide")

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

# SSSMC CUMULATIVE STATS
st.subheader("Channel Wise Statistics")

# CHANNEL SELECTION
channel_filter = st.selectbox("Select the channel", pd.unique(df_handles_data["Channel Handle"]))

# FILTER DF BASED ON CHANNEL SELECTION
df_handles_data_filtered = df_handles_data[df_handles_data["Channel Handle"] == channel_filter]
filtered_handle_rows_dict = df_handles_data_filtered.to_dict(orient="records")

# MAIN STATS
kpi1, kpi2, kpi3 = st.columns(3)

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


tab1, tab2, tab3 = st.tabs(["Latest Videos", "Top Videos", "Search"])

with tab1:
    st.header("Latest Videos")
    filtered_handle_latest_videos_data = get_channel_latest_n_videos(filtered_handle_upload_playlist_id)
    df_filtered_handle_latest_videos_data = pd.DataFrame(filtered_handle_latest_videos_data)
    st.table(df_filtered_handle_latest_videos_data)

with tab2:
    st.header("Top Videos")
    filtered_handle_top_videos_data = get_channel_top_n_videos(filtered_handle_id)
    df_filtered_handle_top_videos_data = pd.DataFrame(filtered_handle_top_videos_data)
    st.table(df_filtered_handle_top_videos_data)

with tab3:
    st.header("Search for a video in this channel to see its statistics")
    text_search = st.text_input("Search videos of this channel...", value="")
    print(text_search)

    if text_search:
        video_search_results_data = get_video_stats_by_search(filtered_handle_id, text_search)
        df_video_search_results_data = pd.DataFrame(video_search_results_data)
        st.subheader("Search Results")

        # st.table(df_video_search_results_data)

        N_cards_per_row = 4
        if df_video_search_results_data.shape[0] > 0:
            for n_row, row in df_video_search_results_data.reset_index().iterrows():
                i = n_row%N_cards_per_row
                if i==0:
                    st.write("---")
                    cols = st.columns(N_cards_per_row, gap="large")
                # draw the card
                with cols[n_row%N_cards_per_row]:
                    # st.image(row["Video Thumbnail URL"])
                    # st.markdown("[![Foo](row["Video Thumbnail URL"])](http://google.com.au/)")
                    html_str = f"""
                    <a href="https://www.youtube.com/watch?v={row['Video ID'].strip()}">
                    <img src="{row['Video Thumbnail URL'].strip()}" alt="Video Thumbnail"></a>
                    """
                    st.markdown(html_str, unsafe_allow_html=True)
                    st.markdown(f"**{row['Video Title'].strip()}**")
                    st.markdown(f"Views: {int(row['Video Views'].strip()):,d}")
                    st.markdown(f"Likes: {int(row['Video Likes']):,d}")



