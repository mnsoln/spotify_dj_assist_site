import streamlit as st
import os
import json
import http.client
import re
import pandas as pd
import time
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from typing import List, Dict, Any, Tuple

# Global Configuration
SCOPE = "user-read-private user-library-read"
SPOTIFY_FETCH_LIMIT = 100       # Total number of saved songs to fetch
SPOTIFY_MAX_REQUEST = 50        # Max items per Spotify API request
RECCOBEATS_BATCH_SIZE = 40      # Max IDs per ReccoBeats API request
RECCOBEATS_HOST = "api.reccobeats.com"
RECCOBEATS_PATH = "/v1/audio-features"
REDIRECT_URI = "http://localhost:8501" 

# SPOTIFY AUTHENTICATION

def get_spotify_oauth(session_cache_path=".cache") -> SpotifyOAuth:
    """Creates and returns the SpotifyOAuth object."""
    client_id = os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
    
    if not (client_id and client_secret):
        st.error("Please set SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET environment variables.")
        st.stop()
    
    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        cache_path=session_cache_path,
        show_dialog=True,
    )

def authenticate_spotify():
    """Handles the Spotipy authentication flow in Streamlit."""
    auth_manager = get_spotify_oauth()
    
    if 'token_info' not in st.session_state:
        st.session_state.token_info = auth_manager.get_cached_token()
        
    if not st.session_state.token_info or auth_manager.is_token_expired(st.session_state.token_info):
        query_params = st.query_params
        code = query_params.get("code")
        
        if code:
            try:
                st.session_state.token_info = auth_manager.get_access_token(code[0], as_dict=True)
                st.experimental_set_query_params() 
            except Exception as e:
                st.error(f"Failed to get access token: {e}")
                return None
        else:
            auth_url = auth_manager.get_authorize_url()
            st.info("Please log in to Spotify to proceed.")
            st.markdown(f'<a href="{auth_url}" target="_self"><button style="background-color:#1db954; color:white; border:none; padding: 10px 20px; border-radius: 5px; cursor: pointer;">Connect to Spotify</button></a>', unsafe_allow_html=True)
            return None
    
    if st.session_state.token_info:
        return Spotify(auth_manager=auth_manager)
        
    return None

# RECCOBEATS FUNCS

def get_reccobeats_audio_features_batched(spotify_ids: List[str]) -> List[Dict[str, Any]]:
    """Fetches audio features from ReccoBeats API, processing in batches."""
    if not spotify_ids: return []
    all_features = []
    
    for i in range(0, len(spotify_ids), RECCOBEATS_BATCH_SIZE):
        batch_ids = spotify_ids[i:i + RECCOBEATS_BATCH_SIZE]
        ids_query = ",".join(batch_ids)
        path = f"{RECCOBEATS_PATH}?ids={ids_query}"
        
        payload = ''
        headers = {'Accept': 'application/json'}
        conn = None
        try:
            conn = http.client.HTTPSConnection(RECCOBEATS_HOST, timeout=15)
            conn.request("GET", path, payload, headers)
            res = conn.getresponse()
            
            if res.status != 200:
                st.error(f"ReccoBeats API Error for batch {i//RECCOBEATS_BATCH_SIZE + 1}: Status {res.status} {res.reason}")
                continue
                
            data = res.read()
            response_json = json.loads(data.decode("utf-8"))
            all_features.extend(response_json.get('content', []))
            
        except Exception as e:
            st.exception(f"ReccoBeats API Connection Error on batch {i//RECCOBEATS_BATCH_SIZE + 1}: {e}")
            
        finally:
            if conn: conn.close()
    return all_features

def extract_spotify_id_from_href(href: str) -> str:
    """Extracts the Spotify Track ID from the href"""
    prefix = "https://open.spotify.com/track/"
    if href and prefix in href:
        return href.split(prefix)[-1].split('/')[0]
    return "ID_NOT_FOUND"


def convert_spotify_to_camelot(df: pd.DataFrame) -> pd.DataFrame:
    """Converts Spotify key and mode to Camelot notation and adds it to the DataFrame."""
    with open('camelot_converter.json', 'r') as f:
        camelot_data = json.load(f)
    
    key_mode_to_camelot = {
        (item['spotify_key'], item['spotify_mode']): item['camelot_key']
        for item in camelot_data
    }
    
    def get_camelot(row):
        return key_mode_to_camelot.get((row['key'], row['mode']), 'N/A')
    
    df['Camelot_Key'] = df.apply(get_camelot, axis=1)
    return df

# TEMPO GROUPING

def add_tempo_grouping(df: pd.DataFrame) -> pd.DataFrame:
    """Calculates the Tempo_Group and adds it to the DataFrame."""
    if 'tempo' in df.columns:
        df['Tempo_Group'] = df['tempo'].round(0).astype(float)
    else:
        df['Tempo_Group'] = 0.0
    return df

def analyze_tempo_groups(df: pd.DataFrame):
    """Displays the grouped tempo analysis ."""
    st.header("BPM Grouping")
    st.info("This section shows songs grouped by Tempo (BPM).")
    
    if df is None or df.empty:
        st.warning("No songs to analyze for tempo groups (no songs match the filters).")
        return
    
    tempo_groups = df.groupby('Tempo_Group')
    large_groups = tempo_groups.filter(lambda x: len(x) > 1)
    
    if large_groups.empty:
        st.warning("No groups of songs found with Tempo values within 1 BPM of each other in the filtered set.")
        return

    unique_tempos = sorted(large_groups['Tempo_Group'].unique())
    
    for tempo_group_val in unique_tempos:
        st.subheader(f"🎶 Group  {tempo_group_val:.0f} BPM")
        group_df = large_groups[large_groups['Tempo_Group'] == tempo_group_val].sort_values(by='tempo', ascending=False).sort_values(by='Camelot_Key', ascending=False)

        st.dataframe(group_df[['Titre', 'Artistes', 'Camelot_Key', 'loudness', 'danceability', 'energy','valence']].fillna('N/A'),
                        width='stretch')


# FEATURE FILTERING

def filter_songs(sp: Spotify, df: pd.DataFrame) -> pd.DataFrame:
    st.header("Filter by Features")

    col1, col2 = st.columns(2)
    with col1:
        dance_range = st.slider('Danceability', 0.0, 1.0, (float(df['danceability'].min()), float(df['danceability'].max())), 0.05)
        energy_range = st.slider('Energy', 0.0, 1.0, (float(df['energy'].min()), float(df['energy'].max())), 0.05)
        valence_range = st.slider('Valence (Joy)', 0.0, 1.0, (float(df['valence'].min()), float(df['valence'].max())), 0.05)
        
    with col2:
        tempo_min = int(df['tempo'].min()) if not df.empty else 60
        tempo_max = int(df['tempo'].max()) if not df.empty else 180
        tempo_range = st.slider('Tempo (BPM) Range', float(tempo_min), float(tempo_max), (float(tempo_min), float(tempo_max)), 1.0)
        
        # unique_tempo_groups = sorted(df['Tempo_Group'].unique())
        # if not unique_tempo_groups:
        #     tempo_group_options = []
        # else:
        #     tempo_group_options = [f"{t:.1f}" for t in unique_tempo_groups]

        acoustic_range = st.slider('Acousticness', 0.0, 1.0, (float(df['acousticness'].min()), float(df['acousticness'].max())), 0.05)
        
        loudness_min = int(df['loudness'].min()) if not df.empty else -60
        loudness_max = int(df['loudness'].max()) if not df.empty else 0
        loudness_range = st.slider('Loudness (dB)', float(loudness_min), float(loudness_max), (float(loudness_min), float(loudness_max)), 1.0)

    # FILTERING THE EXISTING SONGS
    filtered_df = df[
        (df['danceability'] >= dance_range[0]) & (df['danceability'] <= dance_range[1]) &
        (df['energy'] >= energy_range[0]) & (df['energy'] <= energy_range[1]) &
        (df['valence'] >= valence_range[0]) & (df['valence'] <= valence_range[1]) &
        (df['tempo'] >= tempo_range[0]) & (df['tempo'] <= tempo_range[1]) &
        (df['acousticness'] >= acoustic_range[0]) & (df['acousticness'] <= acoustic_range[1]) &
        (df['loudness'] >= loudness_range[0]) & (df['loudness'] <= loudness_range[1])
    ]
    
    st.subheader(f"Filtered Songs: {len(filtered_df)} found")
    
    if filtered_df.empty:
        st.warning("No saved songs match the filtering criteria.")

    return filtered_df



# --- MAIN STREAMLIT FUNCTION ---

def app_main():
    st.set_page_config(page_title="Saved Songs Analysis 🎧", layout="wide")
    st.title(f"Saved Songs Analysis for DJing 🎧")
    st.caption("Analyze and filter your Spotify saved songs based on audio features. ")
    st.caption("Project by Solène Medina to learn the basics of mixing songs while practicing her Python, APIs and Streamlit skills !")

    sp = authenticate_spotify()

    if sp:
        try:
            user = sp.current_user()
            st.success(f"Connected as : **{user.get('display_name')}**", icon="👤")

            # Get total number of saved tracks
            total_saved_tracks = int(sp.current_user_saved_tracks(limit=1).get('total', 0))
            
            number_total_to_fetch = st.slider(
                "How many saved songs to fetch?",
                min_value=10,
                max_value=total_saved_tracks,
                value=SPOTIFY_FETCH_LIMIT,
                step=20
            )

            st.header(f"Fetching {number_total_to_fetch} of your saved songs")

            # Initialize session storage for features
            if 'df_features' not in st.session_state:
                st.session_state['df_features'] = None

            # If features not yet fetched require the button
            if st.session_state['df_features'] is None:
                if not st.button("Fetch Saved Songs"):
                    st.info("Select the number of songs and click 'Fetch Saved Songs' to start the operation.")
                    return

                all_tracks = []
                start_fetching = time.time()
                with st.spinner(f"Fetching your saved songs from Spotify ..."):
                    for offset in range(0, number_total_to_fetch, SPOTIFY_MAX_REQUEST):
                        current_limit = min(SPOTIFY_MAX_REQUEST, number_total_to_fetch - offset)
                        results = sp.current_user_saved_tracks(limit=current_limit, offset=offset)
                        all_tracks.extend(results.get('items', []))
                        if len(results.get('items', [])) < current_limit:
                            break

                        
                st.success(f"Total fetched: {len(all_tracks)} songs.")
                elapsed_fetching = time.time() - start_fetching
                st.info(f"Fetching songs took {elapsed_fetching:.2f} seconds.")
                if not all_tracks:
                    return

                # Extract Spotify IDs and metadata
                track_metadata_map = {}
                spotify_ids = []
                
                for item in all_tracks:
                    track = item.get('track', {})
                    track_id = track.get('id')
                    if track_id:
                        spotify_ids.append(track_id)
                        track_metadata_map[track_id] = {
                            'name': track.get('name'),
                            'artists': ", ".join([artist.get('name', '') for artist in track.get('artists', [])])
                        }

                # Fetch ReccoBeats audio features
                st.header(f"Get the audio features")
                start_featuring = time.time()
                with st.spinner(f"Fetching ReccoBeats features (Batches of {RECCOBEATS_BATCH_SIZE})..."):
                    all_features = get_reccobeats_audio_features_batched(spotify_ids)
                elapsed_featuring = time.time() - start_featuring
                st.info(f"Fetched features for {len(all_features)} songs in {elapsed_featuring:.2f} seconds.")

                data_for_df = []
                for features in all_features:
                    returned_href = features.get('href')
                    spotify_id_from_feature = extract_spotify_id_from_href(returned_href)
                    metadata = track_metadata_map.get(spotify_id_from_feature)
                    
                    if metadata:
                        data_row = {
                            "Titre": metadata['name'],
                            "Artistes": metadata['artists'],
                            "ID": spotify_id_from_feature
                        }
                        data_row.update({k: v for k, v in features.items() if isinstance(v, (int, float))})
                        data_for_df.append(data_row)
                        
                if not data_for_df:
                    st.warning("Can't build features dataframe :no valid data retrieved.")
                    return

                df_features = pd.DataFrame(data_for_df)
                df_features = convert_spotify_to_camelot(df_features)  # ADD CAMELOT KEY
                df_features = add_tempo_grouping(df_features) # ADD TEMPO GROUP
                st.session_state['df_features'] = df_features

            # Use the stored dataframe
            df_features = st.session_state['df_features']

            # Feature Filtering
            st.markdown("---")
            filtered_df = filter_songs(sp, df_features)

            # Tempo Group Analysis on the filtered set
            st.markdown("---")
            analyze_tempo_groups(filtered_df)

        except Exception as e:
            st.error("Unexcpected error occurred:")
            st.exception(e)
            

if __name__ == "__main__":
    app_main()
