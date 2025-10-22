import http.client
import json
import streamlit as st
from typing import List, Dict, Any
import pandas as pd
import os
from spotipy import Spotify


RECCOBEATS_BATCH_SIZE = 40      # Max IDs per ReccoBeats API request
RECCOBEATS_HOST = "api.reccobeats.com"
RECCOBEATS_PATH = "/v1/audio-features"
REDIRECT_URI = "http://localhost:8501" 


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
    with open("docs/camelot_converter.json") as f:
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

