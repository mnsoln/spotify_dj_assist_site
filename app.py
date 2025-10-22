import streamlit as st
import os
import json
import http.client
import re
import pandas as pd
import time
from typing import List, Dict, Any, Tuple
from spotipy import Spotify

from funcs.auth_funcs import authenticate_spotify
import funcs.features_funcs as features_funcs

# Global Configuration
SCOPE = "user-read-private user-library-read"
SPOTIFY_FETCH_LIMIT = 100       # Total number of saved songs to fetch
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
                    all_features = features_funcs.get_reccobeats_audio_features_batched(spotify_ids)
                elapsed_featuring = time.time() - start_featuring
                st.info(f"Fetched features for {len(all_features)} songs in {elapsed_featuring:.2f} seconds.")

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
                    st.warning("Can't build features dataframe :no valid data retrieved.")
                    return

                df_features = pd.DataFrame(data_for_df)
                df_features = features_funcs.convert_spotify_to_camelot(df_features)  # ADD CAMELOT KEY
                df_features = features_funcs.add_tempo_grouping(df_features) # ADD TEMPO GROUP
                st.session_state['df_features'] = df_features

            # Use the stored dataframe
            df_features = st.session_state['df_features']

            # Feature Filtering
            st.markdown("---")
            filtered_df = features_funcs.filter_songs(sp, df_features)

            # Tempo Group Analysis on the filtered set
            st.markdown("---")
            features_funcs.analyze_tempo_groups(filtered_df)

        except Exception as e:
            st.error("Unexcpected error occurred:")
            st.exception(e)
            

if __name__ == "__main__":
    app_main()
