#!/usr/bin/env -S streamlit run
"""This is Cicero Voice Map Manager tab.
A tool for managing the voice map table using Streamlit's st.data_editor.
This file was largely AI-generated, except for the crucial step where I made it actually (mostly) work.
"""

import streamlit as st
from cicero_shared import admin_box, sql_call_cacheless, ssget, ssset
import json
import ast

#TODO: Use the corp/political column data instead of the types in cicero_types, the relevant ones of which can be removed completely. (The voice-accessing code should then be refactored to only access once, analagous to load_account_names(), for perf reasons.)
def ensure_existence_of_voice_map_table() -> None:
  """Run this code before accessing the voice map table. If the voice map table doesn't exist, this function call will create it."""
  sql_call_cacheless("""
    CREATE TABLE IF NOT EXISTS cicero.default.voice_map (
      enabled BOOLEAN COMMENT "Instead of deleting rows from this table, you can also just disable them here, for convenience (in case you want them back later).",
      chatbot_corporate BOOLEAN,
      chatbot_political BOOLEAN,
      voice_id STRING,
      voice_description STRING
    )
  """)

st.write("## Voice Map Manager")
st.write("This page allows you to manage the voice map table. Currently, it cannot delete rows (the could be changed in the future). Instead, you can disable them by setting the 'enabled' column to False.")

ensure_existence_of_voice_map_table()

voice_map_results = sql_call_cacheless("SELECT * FROM cicero.default.voice_map ORDER BY voice_id")

column_names = voice_map_results[0].asDict().keys() if len(voice_map_results) > 0 else []

@st.fragment
def _() -> None: # We only need this to be in a function so we can use st.fragment on it (so it doesn't lag when you update a value), and we only need it to return a value (rather than setting a nonlocal) so that pyright typechecking will be happy with the code.
  ssset("voice_map_new_data",
    st.data_editor(
      voice_map_results,
      num_rows="dynamic",
      key="voice_map_editor",
      use_container_width=True,
      column_config={str(i): col for i, col in enumerate(column_names)}
    )
  )
_()

def save_the_changes() -> None:
  #COULD: improve the performance of this function, possibly by exploiting the fact that the value at ssget("voice_map_editor") is like {"edited_rows":{ "23":{"0":true}}, "added_rows" […], "removed_rows"} and the fact that it's sorted by voice_id.
  # The fact that it writes all of the data every time, and in a for loop no less (instead of just one big SQL query), is disturbing, and I would fix it, but as much as I love Ted, he's the only person this tool is for, so I'm not going to touch it right now.
  the_new_data = ssget("voice_map_new_data")
  if the_new_data is None:
    st.error("No changes to save.")
    return
  admin_box("The entire new dataset", the_new_data)
  for row in the_new_data:
    sql_call_cacheless("""
      MERGE INTO cicero.default.voice_map AS target
      USING (SELECT :enabled AS enabled, :chatbot_corporate AS chatbot_corporate, :chatbot_political AS chatbot_political, :voice_id AS voice_id, :voice_description AS voice_description) AS source
      ON target.voice_id = source.voice_id
      WHEN MATCHED THEN
          UPDATE SET enabled = :enabled, chatbot_corporate = :chatbot_corporate, chatbot_political = :chatbot_political, voice_description = :voice_description
      WHEN NOT MATCHED THEN
          INSERT (enabled, chatbot_corporate, chatbot_political, voice_id, voice_description)
          VALUES (source.enabled, source.chatbot_corporate, source.chatbot_political, source.voice_id, source.voice_description)
      """,
      {
        "enabled": row[0],
        "chatbot_corporate": row[1],
        "chatbot_political": row[2],
        "voice_id": row[3],
        "voice_description": row[4]
      }
    )
  st.success("Changes saved successfully!")

# Since this button has a callback that runs during callback time, the next pageload after clicking the button will display the correct live data.
st.button("Save Changes (you MUST click this button to save changes, and it will take a minute to process)", type="primary", on_click=save_the_changes)

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
        for voice_id, voice_data in voice_map_dict.items():
          sql_call_cacheless("""
            INSERT INTO cicero.default.voice_map (enabled, chatbot_corporate, chatbot_political, voice_id, voice_description)
            VALUES (:enabled, :chatbot_corporate, :chatbot_political, :voice_id, :voice_description)
            """,
            {
              "enabled": voice_data["enabled"],
              "chatbot_corporate": voice_data["chatbot_corporate"],
              "chatbot_political": voice_data["chatbot_political"],
              "voice_id": voice_id,
              "voice_description": voice_data["voice_description"]
            }
          )
        st.success("Voice map table overwritten successfully! (Refresh the page to see the changes)")
      else:
        st.error("Invalid input: Please enter a valid dict.")
    except (json.JSONDecodeError, ValueError, SyntaxError):
      st.error("Invalid input: Please enter a valid json.")

with st.expander("## Manipulate the table using SQL directly"):
  cool_query = st.text_area(label="Arbitrary SQL", value="SELECT * FROM cicero.default.voice_map")
  if st.button("Go! (sql query)"):
    st.write(sql_call_cacheless(cool_query))
