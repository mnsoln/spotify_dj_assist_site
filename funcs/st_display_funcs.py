import streamlit as st # pyright: ignore[reportMissingImports]

def display_matches(
    columns,
    matches_same,
    matches_up,
    matches_down,
    dominant_matches,
    whole_step_up_matches,
    half_step_up_matches,
    minor_third_up_matches,
):
# Display the matching songs
    st.markdown("## Same Key Matches:")
    st.write("These tracks will both be in the same key and are therefore perfectly compatible harmonically. It will give the effect that the tracks are singing together.")
    st.dataframe(matches_same.reset_index(drop=True), hide_index=True, column_order=columns)
    st.markdown("## Fifth Up Matches:")
    st.write("Moving up a Fifth will raise the energy in the room. Only one note is different between the two scales.")
    st.dataframe(matches_up.reset_index(drop=True), hide_index=True, column_order=columns)
    st.markdown("## Fifth Down Matches:")
    st.write("Going down a Fifth will take the crowd deeper. It won’t raise the energy necessarily but will give your listeners goosebumps!")
    st.dataframe(matches_down.reset_index(drop=True), hide_index=True, column_order=columns)
    st.markdown("## Dominant Key Relative Major Matches:")
    st.write("This is the best way to go from Major to Minor keys and from Minor to Major because the scales only have one note difference and the combination sounds great")
    st.dataframe(dominant_matches.reset_index(drop=True), hide_index=True, column_order=columns)
    st.markdown("## Whole Step Up Matches:")
    st.write("This will raise the energy of the room. It’s a common technique used by DJs to lift the energy and take the crowd higher.")
    st.dataframe(whole_step_up_matches.reset_index(drop=True), hide_index=True, column_order=columns)
    st.markdown("## Half Step Up Matches:")
    st.write("This shouldn’t sound good together but if you plan it right and mix a percussive outro of one song with a percussive intro of another song, and slowly bring in the melody this can have an amazing effect musically and raise the energy of the room dramatically.")
    st.dataframe(half_step_up_matches.reset_index(drop=True), hide_index=True, column_order=columns)
    st.markdown("## Minor Third Up Matches:")
    st.write("This is a more unconventional mix but can work really well if done right.  While these scales have 3 notes that are different they can still sound good played together, and tend to raise the energy of a room.")
    st.dataframe(minor_third_up_matches.reset_index(drop=True), hide_index=True, column_order=columns)