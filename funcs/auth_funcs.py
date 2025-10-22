import os
import streamlit as st
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

# Global Configuration
SCOPE = "user-read-private user-library-read"
SPOTIFY_FETCH_LIMIT = 100       # Total number of saved songs to fetch
SPOTIFY_MAX_REQUEST = 50        # Max items per Spotify API request
REDIRECT_URI = "http://localhost:8501" 


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
