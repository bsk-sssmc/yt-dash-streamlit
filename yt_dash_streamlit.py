from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from google.auth.transport.requests import Request
import  pandas as pd
import os
import pickle
import streamlit as st
from datetime import timedelta, datetime
from geopy.geocoders import Nominatim
import plotly.express as px
import pycountry
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

# Define the scopes
CLIENT_SECRETS_FILE = "./client_secret.json"  # Replace with your OAuth client secrets file
SCOPES = ["https://www.googleapis.com/auth/yt-analytics.readonly", "https://www.googleapis.com/auth/youtube.readonly"]
TOKEN_PICKLE_FILE = "token.pickle"

api_key = os.getenv('YOUTUBE_API_KEY')

# OAUTH INIT
def authenticate_with_oauth():
    if "credentials" not in st.session_state:
        flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES)
        flow.redirect_uri = st.secrets["redirect_uri"]

        authorization_url, _ = flow.authorization_url(prompt='consent')
        st.session_state["flow"] = flow
        st.write("Please authenticate using the link below:")
        st.markdown(f"[Authenticate here]({authorization_url})")
    else:
        credentials = st.session_state["credentials"]
        return build("youtubeAnalytics", "v2", credentials=credentials)

# OAUTH CALLBACK
def handle_oauth_callback():
    flow = st.session_state["flow"]
    flow.fetch_token(authorization_response=st.experimental_get_query_params()["code"])
    credentials = flow.credentials
    st.session_state["credentials"] = credentials

channel_handles = ["@SriSathyaSaiOfficial", "@SriSathyaSaiBhajans", "@PrasanthiMandirLiveRadioSai", "@SriSathyaSaiSpeaksOfficial", "@SriSathyaSaiTelugu", "@SriSathyaSaiTamil", "@SriSathyaSaiHindi", "@SriSathyaSaiKannada", "@SriSathyaSaiMalayalam", "@SriSathyaSaiKidsWorld", "@SriSathyaSaiMandarin"]

# Define the available date ranges
date_ranges = {
    "Last 7D": (datetime.now() - timedelta(days=7), datetime.now()),
    "Last 28D": (datetime.now() - timedelta(days=28), datetime.now()),
    "Last 3 Months": (datetime.now() - timedelta(days=90), datetime.now()),
    "Last Year": (datetime.now() - timedelta(days=365), datetime.now()),
    "Lifetime": (None, datetime.now()),  # None signifies no start date
}

# Initialize geolocator
geolocator = Nominatim(user_agent="geoapi")

# Function to get country coordinates dynamically
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


# ST SESSION DEFNS

if "selected_range" not in st.session_state:
    st.session_state["selected_range"] = "Last 7D"

# ST SESSION UPDATES

def update_range():
    st.session_state["selected_range"] = st.session_state["range_selector"]


# UTILS

def get_country_name(country_code):
    try:
        country = pycountry.countries.get(alpha_2=country_code.upper())
        return country.name if country else "Unknown country code"
    except Exception as e:
        return f"Error: {e}"


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
    # Build the YouTube Data API v3 and Analytics API v2 clients
    youtube = build("youtube", "v3", credentials=creds)
    youtube_analytics = build("youtubeAnalytics", "v2", credentials=creds)
    
    return youtube, youtube_analytics

youtube, youtube_analytics = get_authenticated_service()

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
            options=list(date_ranges.keys()),
            index=list(date_ranges.keys()).index(st.session_state["selected_range"]),
            key="range_selector",
            on_change=update_range,
        )
    
    with selected_time_display:
        # Set start_date and end_date based on the selected range
        start_date, end_date = date_ranges[st.session_state["selected_range"]]

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
formatted_start_date = start_date.strftime("%Y-%m-%d")
formatted_end_date = end_date.strftime("%Y-%m-%d")


# FETCH AND AUTHENTICATE BUTTONS
col1, col2 = st.columns([1, 1])

# Button to fetch data
if col1.button("Fetch Data"):


    try:
        st.subheader("Views by Traffic Source")
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
        st.write("Traffic Source Statistics:")
        st.table(traffic_source_df)
        # fig_traffic = get_traffic_source_interactive_bar(traffic_source_df)
        # st.plotly_chart(fig_traffic, use_container_width=True)

        st.subheader("Views by Country")
        country_data = fetch_analytics(
            youtube_analytics,
            filtered_handle_id,
            formatted_start_date,
            formatted_end_date,
            dimensions="country",
            metrics="views",
            sort="-views",
            max_results=25,  # Top 25 countries
        )
        country_views_df = pd.DataFrame(country_data, columns=["Country Code", "Views"])
        # Apply the function to create a new column
        country_views_df['Country Name'] = country_views_df['Country Code'].apply(get_country_name)
        country_views_df = country_views_df[['Country Code', 'Country Name', 'Views']]
        st.write("Top 25 Countries by Views:")
        st.table(country_views_df)

    #     st.header("Map Visualization")

    #     # Create a folium map
    #     m = folium.Map(location=[20, 0], zoom_start=2)  # Centered for global view
    #     marker_cluster = MarkerCluster().add_to(m)

    #     # Add markers dynamically
    #     for _, row in df.iterrows():
    #         coordinates = get_country_coordinates(row['CountryCode'])
    #         if coordinates:
    #             folium.Marker(
    #                 location=coordinates,
    #                 popup=f"Country: {row['CountryCode']}<br>Views: {row['Views']}",
    #                 icon=folium.Icon(color='blue', icon='info-sign')
    #             ).add_to(marker_cluster)

    # # Display the map in Streamlit
    # st_folium(m, width=800, height=500)    
            
    except Exception as e:
        st.error(f"Error: {e}")

# Button to reset authentication
if col2.button("Reset Authentication"):
    try:
        if os.path.exists(TOKEN_PICKLE_FILE):
            os.remove(TOKEN_PICKLE_FILE)
            youtube, youtube_analytics = get_authenticated_service()
            st.success("Authentication successful!")
            st.write("You can now fetch analytics data.")
        else:
            st.warning("No token file found to delete.")
    except Exception as e:
        st.error(f"Error: {e}")