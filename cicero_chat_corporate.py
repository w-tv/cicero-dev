#!/usr/bin/env -S streamlit run

import streamlit as st
from databricks_genai_inference import ChatSession, FoundationModelAPIException
from cicero_shared import consul_show, get_base_url, popup
import cicero_chat

# unfortunately this didn't work at all
st.session_state["the_real_dude_system_prompt"] = "You are an expert marketer who is skilled in a variety of disciplines. The thing is, you have this bad habit of sounding like a Pirate...."

# TODO: have the system prompt be stored in this file, so i can just come here and change it when i need to

st.write('''**Chat freeform with Cicero directly ChatGPT-style!**  \nHere are some ideas: rewrite copy, make copy longer, convert a text into an email, or write copy based off a starter phrase/quote.''')
if st.button("Reset"):
  cicero_chat.reset_chat()
cicero_chat.display_chat()