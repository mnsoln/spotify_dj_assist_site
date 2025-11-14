import streamlit as st # pyright: ignore[reportMissingImports]
import os
import json
import http.client
import re
import pandas as pd # pyright: ignore[reportMissingModuleSource]
import time
from typing import List, Dict, Any, Tuple
from spotipy import Spotify

from funcs.auth_funcs import authenticate_spotify
import funcs.features_funcs as features_funcs
from funcs.match_funcs import get_all_matches
from funcs.st_display_funcs import display_matches

# Global Configuration
SCOPE = "user-read-private user-library-read"
SPOTIFY_MAX_REQUEST = 50        # Max items per Spotify API request
RECCOBEATS_BATCH_SIZE = 40      # Max IDs per ReccoBeats API request
REDIRECT_URI = "http://localhost:8501"


# --- MAIN STREAMLIT FUNCTION ---

def app_main():
    st.set_page_config(page_title="Saved Songs Analysis 🎧", layout="wide", )
    st.title(f"Saved Songs Analysis for DJing 🎧")
    st.caption("Analyze and filter your Spotify saved songs based on audio features. ")
    st.caption("Project by Solène Medina to learn the basics of mixing songs while practicing her Python, APIs and Streamlit skills !")

    sp = authenticate_spotify()

    if sp:
        try:
            # User info
            user = sp.current_user()
            st.success(f"Connected as : **{user.get('display_name')}**", icon="👤")

            # Initialize session state
            if 'df_features' not in st.session_state:
                st.session_state['df_features'] = None
                

            total_saved_tracks = int(sp.current_user_saved_tracks(limit=1).get('total', 0))

            # Fetching Songs
            number_total_to_fetch = st.slider(
                "How many saved songs to fetch?",
                min_value=10,
                max_value=total_saved_tracks,
                value=100,
                step=10,
                key='fetch_limit_slider'
            )
            st.session_state['fetch_limit'] = number_total_to_fetch # Store the selected value

            fetching_button_label = "Refetch Songs" if st.session_state['df_features'] is not None else "Fetch Saved Songs"
            
            # Fetch or clear the old data and fetch
            if st.button(fetching_button_label, key='fetch_button', help="Click to fetch your saved songs from Spotify and their audio features from ReccoBeats."):
                st.session_state['df_features'] = None # Clear old data

                all_tracks = []
                start_fetching = time.time()
                with st.spinner(f"Fetching your saved songs from Spotify ..."):
                    for offset in range(0, number_total_to_fetch, SPOTIFY_MAX_REQUEST):
                        current_limit = min(SPOTIFY_MAX_REQUEST, number_total_to_fetch - offset)
                        results = sp.current_user_saved_tracks(limit=current_limit, offset=offset)
                        all_tracks.extend(results.get('items', []))
                        if len(results.get('items', [])) < current_limit or len(all_tracks) >= number_total_to_fetch:
                            break
                elapsed_fetching = time.time() - start_fetching
                st.success(f"Total fetched: {len(all_tracks)} songs in {elapsed_fetching:.2f} seconds.")
                if not all_tracks:
                    st.warning("No songs fetched.")
                    return # Stop execution if no tracks were fetched

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
                st.markdown(f"### Get the audio features")
                start_featuring = time.time()
                with st.spinner(f"Fetching ReccoBeats features (Batches of {RECCOBEATS_BATCH_SIZE})..."):
                    all_features = features_funcs.get_reccobeats_audio_features_batched(spotify_ids) 
                elapsed_featuring = time.time() - start_featuring
                st.info(f"ReccoBeats found features for {len(all_features)} songs in {elapsed_featuring:.2f} seconds.")

                data_for_df = []
                for features in all_features:
                    returned_href = features.get('href')
                    spotify_id_from_feature = features_funcs.extract_spotify_id_from_href(returned_href) 
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
                    st.warning("Can't build features dataframe : no valid data retrieved.")
                    return

                df_features = pd.DataFrame(data_for_df)
                df_features = features_funcs.convert_spotify_to_camelot(df_features) 
                df_features = features_funcs.add_tempo_grouping(df_features) 
                st.session_state['df_features'] = df_features

            # Check if there's data
            if st.session_state['df_features'] is None:
                return 

            ##  Main content with data fetched

            df_features = st.session_state['df_features']
            
            st.header("Analysis and Filtering")
            tab_features, tab_search = st.tabs([":violet Filter by Features", ":rainbow Filter by Song Matching"], default=":rainbow Filter by Song Matching")
            
            with tab_features:
                filtered_df = features_funcs.filter_songs(sp, df_features)
                
                col1, col2 = st.columns([1, 1])
                with col2:
                    if st.button("Reset Filters", help="Click to reset all filters to default values."):
                        filtered_df = features_funcs.filter_songs(sp, df_features)

                st.subheader("Filtered Tracklist")
                st.dataframe(filtered_df)

                # Tempo Group Analysis on the filtered set
                if st.button("Group the filtered songs by tempo"):
                    features_funcs.analyze_tempo_groups(filtered_df)




            with tab_search:

                columns_to_show = ['Titre', 'Artistes', 'tempo', 'Camelot Key', 'danceability', 'energy', 'valence', 'loudness']
                st.header("Search Your Song and find what matches with it !")
                try:
                    options_for_search = (df_features['Titre'].fillna('').astype(str) + ' - ' + df_features['Artistes'].fillna('').astype(str)).tolist()
                    search_query = st.selectbox("Enter a song name to search in your saved songs:", options=options_for_search, key="search_selectbox", index=None)

                    # If the song isn't in the list, allow manual input
                    if not search_query:
                        st.write("If the song is not in the list, enter its tempo and Camelot key manually:")
                        tempo_manual = st.number_input("Enter the tempo (BPM) of your song:", min_value=0, max_value=300, step=1, key="tempo_input")
                        camelot_key_manual = st.selectbox("Select the Camelot Key of your song:", options=[f"{i}{k}" for i in range(1,13) for k in ['A','B']], key="camelot_selectbox", index=None)
                        searched_song = pd.DataFrame() 
                        search_title = ""

                    if search_query:
                        search_title = search_query.split(' - ')[0]
                        search_artist = search_query.split(' - ')[1] 
                        searched_song = df_features[
                            (df_features['Titre'].fillna('').astype(str).str.contains(search_title, case=False, na=False, regex=False)) &
                            (df_features['Artistes'].fillna('').astype(str).str.contains(search_artist, case=False, na=False, regex=False))
                        ]
                        st.dataframe(searched_song, hide_index=True, column_order=columns_to_show)
                        tempo_manual = 0
                        camelot_key_manual = ""
                    tempo_tolerance = st.slider("Select Tempo Tolerance (BPM):", min_value=0, max_value=30, value=1, step=1)

                    

                    if not searched_song.empty or (tempo_manual > 0 and camelot_key_manual):
                        st.subheader(f"Songs matching {search_title}:")

                        # Get matches based on the searched song or manual input
                        if searched_song.empty:
                            matches_same, matches_up, matches_down, dominant_matches, whole_step_up_matches, half_step_up_matches, minor_third_up_matches = get_all_matches(features_df=df_features, chosen_song_id="", tempo_tolerance=tempo_tolerance, manual_tempo=tempo_manual, manual_key=camelot_key_manual)
                        else:
                            chosen_song_id = searched_song['ID'].values[0]
                            matches_same, matches_up, matches_down, dominant_matches, whole_step_up_matches, half_step_up_matches, minor_third_up_matches = get_all_matches(features_df=df_features, chosen_song_id=chosen_song_id, tempo_tolerance=tempo_tolerance)


                        # Display the matching songs
                        display_matches(
                            columns_to_show,
                            matches_same,
                            matches_up,
                            matches_down,
                            dominant_matches,
                            whole_step_up_matches,
                            half_step_up_matches,
                            minor_third_up_matches,
                        )
                        

                except Exception as e:
                    print("Error during search:", e)
                    st.error("Error during search:")
                    st.exception(e)

        except Exception as e:
            st.error("Unexpected error occurred:")
            st.exception(e)
            
    else:
        st.warning("Please reload or connect to Spotify to proceed.", icon="⚠️")

if __name__ == "__main__":
    app_main()