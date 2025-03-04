#!/usr/bin/env -S streamlit run
"""This is Cicero Voice Map Manager tab.
A tool for managing the voice map table using Streamlit's st.data_editor.
This file was largely AI-generated, except for the crucial step where I made it actually (mostly) work
"""

import streamlit as st
from cicero_shared import sql_call_cacheless #, labeled_table
import json
import ast

#TODO: add column to this about whether it's corp or non-corp. Once that's done, use that information instead of the types in cicero_types, the relevant ones of which can be removed completely. (The voice-accessing code should then be refactored to only access once, for perf reasons.)
#TODO: rename voice_description column? I'm not quite sure what to call it.
def ensure_existence_of_voice_map_table() -> None:
  """Run this code before accessing the voice map table. If the voice map table doesn't exist, this function call will create it."""
  sql_call_cacheless("CREATE TABLE IF NOT EXISTS cicero.default.voice_map (voice_id STRING, voice_description STRING)")

st.write("## Voice Map Manager")
st.write("This page allows you to manage the voice map table using Streamlit's st.data_editor.")

# Ensure the voice map table exists
ensure_existence_of_voice_map_table()

# Fetch the current voice map table data
voice_map_results = sql_call_cacheless("SELECT * FROM cicero.default.voice_map")

# Display the voice map table using st.data_editor
edited_voice_map = st.data_editor(voice_map_results, num_rows="dynamic", key="voice_map_editor")

# Save changes to the database
if st.button("Save Changes"):
  for row in edited_voice_map: #TODO: This seems like a lot of extra logic, and I don't think this even deletes rows properly. Possibly instead we just want to overwrite the table every time?
    sql_call_cacheless("""
      MERGE INTO cicero.default.voice_map AS target
      USING (SELECT :voice_id AS voice_id, :voice_description AS voice_description) AS source
      ON target.voice_id = source.voice_id
      WHEN MATCHED THEN
          UPDATE SET voice_description = :voice_description
      WHEN NOT MATCHED THEN
          INSERT (voice_id, voice_description)
          VALUES (source.voice_id, source.voice_description)
      """,
      {"voice_id": row[0], "voice_description": row[1]}
    )
  st.success("Changes saved successfully! (Refresh the page to see the changes)")

with st.expander("Text box for pasting a Python dict or JSON"):
  st.write("### Write to Voice Map Table using a dict.")
  st.write("Honestly, I'm not sure if this writes to the table or overwrites the table. Well, whatever.")
  input_format = st.radio("Input format", ["JSON", "Python dict"])
  dict_input = st.text_area("Paste a Python dict or JSON here to overwrite the voice map table", height=200)
  if st.button("Overwrite Table"):
    try:
      if input_format == "JSON":
        voice_map_dict = json.loads(dict_input)
      else:
        voice_map_dict = ast.literal_eval(dict_input)

      if isinstance(voice_map_dict, dict):
        sql_call_cacheless("DELETE FROM cicero.default.voice_map")
        for voice_id, voice_description in voice_map_dict.items():
          sql_call_cacheless("""
            INSERT INTO cicero.default.voice_map (voice_id, voice_description)
            VALUES (:voice_id, :voice_description)
            """,
            {"voice_id": voice_id, "voice_description": voice_description}
          )
        st.success("Voice map table overwritten successfully! (Refresh the page to see the changes)")
      else:
        st.error("Invalid input: Please enter a valid dict.")
    except (json.JSONDecodeError, ValueError, SyntaxError):
      st.error("Invalid input: Please enter a valid json.")

# Display the current voice map table (again, I guess 🤷)
#st.write("### Current Voice Map Table")
#labeled_table(voice_map_results)
