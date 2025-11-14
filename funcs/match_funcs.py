import pandas as pd # pyright: ignore[reportMissingModuleSource]
import numpy as np # pyright: ignore[reportMissingImports]


def match_same_key_tempo(features_df: pd.DataFrame, chosen_song_id : str, tempo : float, camelot_key: str, tempo_tolerance: float = 1.0 ) -> pd.DataFrame:
    """Finds songs that match the chosen song's key and are within the specified tempo tolerance."""
    matches = features_df[
        (features_df['Camelot_Key'] == camelot_key) &
        (np.abs(features_df['tempo'] - tempo) <= tempo_tolerance) &
        (features_df['ID'] != chosen_song_id)
    ]
    return matches


def matches_fifth(features_df: pd.DataFrame, tempo : float, camelot_key: str, tempo_tolerance: float = 1.0 ) -> pd.DataFrame:
    """Finds songs that are a fifth up or down from the chosen song's key and within the specified tempo tolerance."""
    # Moving up a Fifth (+1 on the Camelot Wheel) will raise the energy in the room.
    camelot_key_up = str(int(camelot_key[0])+1) + camelot_key[1] if camelot_key[0] != '12' else '1' + camelot_key[1]
    matches_up = features_df[
        (features_df['Camelot_Key'] == camelot_key_up) &
        (np.abs(features_df['tempo'] - tempo) <= tempo_tolerance)
    ]
    # Going down a Fifth will take the crowd deeper.
    camelot_key_down = str(int(camelot_key[0])-1) + camelot_key[1] if camelot_key[0] != '1' else '12' + camelot_key[1]
    matches_down = features_df[
        (features_df['Camelot_Key'] == camelot_key_down) &
        (np.abs(features_df['tempo'] - tempo) <= tempo_tolerance)
    ]
    return matches_up, matches_down

def dominant_key_relative_major(features_df: pd.DataFrame, tempo : float, camelot_key: str, tempo_tolerance: float = 1.0 ) -> pd.DataFrame:
    #+1 on the Camelot Wheel and change the letter
    final_key = str(int(camelot_key[0])+1) + ('B' if camelot_key[1] == 'A' else 'A') if camelot_key[0] != '12' else '1' + ('B' if camelot_key[1] == 'A' else 'A')
    matches = features_df[
        (features_df['Camelot_Key'] == final_key) &
        (np.abs(features_df['tempo'] - tempo) <= tempo_tolerance)
    ]
    return matches

def whole_step_up(features_df: pd.DataFrame, tempo : float, camelot_key: str, tempo_tolerance: float = 1.0 ) -> pd.DataFrame:
    #+2 on the Camelot Wheel
    final_key = str(int(camelot_key[0])+2) + camelot_key[1] if camelot_key[0] not in ['11', '12'] else str((int(camelot_key[0])+2)%12) + camelot_key[1]
    matches = features_df[
        (features_df['Camelot_Key'] == final_key) &
        (np.abs(features_df['tempo'] - tempo) <= tempo_tolerance)
    ]
    return matches

def half_step_up(features_df: pd.DataFrame, tempo : float, camelot_key: str, tempo_tolerance: float = 1.0 ) -> pd.DataFrame:
    #+7 on the Camelot Wheel
    final_key = str(int(camelot_key[0])+7) + camelot_key[1] if camelot_key[0] not in ['6', '7', '8', '9', '10', '11', '12'] else str((int(camelot_key[0])+7)%12) + camelot_key[1]
    matches = features_df[
        (features_df['Camelot_Key'] == final_key) &
        (np.abs(features_df['tempo'] - tempo) <= tempo_tolerance)
    ]
    return matches


def minor_third_up(features_df: pd.DataFrame, tempo : float, camelot_key: str, tempo_tolerance: float = 1.0 ) -> pd.DataFrame:
    #-3 on the Camelot Wheel
    final_key = str(int(camelot_key[0])-3) + camelot_key[1] if camelot_key[0] not in ['1', '2', '3'] else str((int(camelot_key[0])-3)%12) + camelot_key[1]
    matches = features_df[
        (features_df['Camelot_Key'] == final_key) &
        (np.abs(features_df['tempo'] - tempo) <= tempo_tolerance)
    ]
    return matches

def get_all_matches(features_df: pd.DataFrame, chosen_song_id: str, tempo_tolerance: int, manual_tempo = None, manual_key = None) -> pd.DataFrame:
    """Filters the DataFrame to get all matches for the chosen song ID."""
    if manual_tempo is None and manual_key is  None:
        chosen_song = features_df[features_df['ID'] == chosen_song_id]
        key = chosen_song['Camelot_Key'].values[0]
        tempo = chosen_song['tempo'].values[0]
    else:
        key = manual_key
        tempo = manual_tempo

    matches_same = match_same_key_tempo(features_df, chosen_song_id, tempo, key, tempo_tolerance)
    matches_up, matches_down = matches_fifth(features_df, tempo, key, tempo_tolerance)
    dominant_matches = dominant_key_relative_major(features_df, tempo, key, tempo_tolerance)
    whole_step_up_matches = whole_step_up(features_df, tempo, key, tempo_tolerance)
    half_step_up_matches = half_step_up(features_df, tempo, key, tempo_tolerance)
    minor_third_up_matches = minor_third_up(features_df, tempo, key, tempo_tolerance)

    return matches_same, matches_up, matches_down, dominant_matches, whole_step_up_matches, half_step_up_matches, minor_third_up_matches


