#!/usr/bin/env -S streamlit run

import streamlit as st
from databricks_genai_inference import ChatSession
from cicero_shared import sql_call_cacheless
from zoneinfo import ZoneInfo as z
from datetime import datetime

def grow_chat(streamlit_key_suffix: str = "", alternate_content: str = "", display_only_this_at_first_blush: str|None = None) -> None:
  # the streamlit_key_suffix is only necessary because we use this code in two places #TODO: actually, it's not clear that we want to do that. And, the chat histories overlap, currently... So, maybe rethink this concept later. I don't even know why we have two of them. Maybe they were supposed to mutate in concept independently?
  model_name = st.session_state["the_real_dude_model_name"]
  sys_prompt = st.session_state["the_real_dude_system_prompt"]
  if not st.session_state.get("chat"):
    # Keep in mind that unless DATABRICKS_HOST and DATABRICKS_TOKEN are in the environment (streamlit does this with secret value by default), then the following line of code will fail with an extremely cryptic error asking you to run this program with a `setup` command line argument (which won't do anything)
    st.session_state.chat = ChatSession(model=model_name, system_message=sys_prompt, max_tokens=4096)
  if not st.session_state.get("messages"):
      st.session_state.messages = []
  p: str = alternate_content or st.session_state["user_input_for_chatbot_this_frame"+streamlit_key_suffix]
  st.session_state.chat.reply(p)
  st.session_state.messages.append({"role": "user", "content": display_only_this_at_first_blush or p})
  st.session_state.messages.append({"avatar": "assets/CiceroChat_800x800.jpg", "role": "assistant", "content": st.session_state.chat.last})
  # Write to the chatbot activity log:
  # (There's no model_uri field because I don't know how to access that from here.)
  # (Note that this table uses a real timestamp object instead of a mere string datetime. You can `SET TIME ZONE "US/Eastern";` in sql to read the timestamps in some non-UTC timezone. (UTC being the default) (Specifically this gets them in US Eastern time.))
  sql_call_cacheless("CREATE TABLE IF NOT EXISTS cicero.default.activity_log_chatbot (timestamp timestamp, user_email string, user_pod string, model_name string, model_parameters string, system_prompt string, user_prompt string, response_given string)")
  sql_call_cacheless(
    "WITH tmp(user_pod) AS (SELECT user_pod FROM cicero.default.user_pods WHERE user_email ilike :user_email)\
    INSERT INTO cicero.default.activity_log_chatbot\
            ( timestamp,  user_email, user_pod,  model_name,  model_parameters,  system_prompt,  user_prompt,  response_given)\
      SELECT :timestamp, :user_email, user_pod, :model_name, :model_parameters, :system_prompt, :user_prompt, :response_given FROM tmp",
    {"timestamp": datetime.now(z("US/Eastern")), "user_email": st.session_state["email"], "model_name": st.session_state.chat.model, "model_parameters": str(st.session_state.chat.parameters), "system_prompt": st.session_state.chat.system_message, "user_prompt": p, "response_given": st.session_state.chat.last}
  )

def reset_chat() -> None:
  st.session_state["chat"] = None
  st.session_state["messages"] = None
  st.session_state['cicero_ai'] = None

# chat.history
# return: [
#     {'role': 'system', 'content': 'You are a helpful assistant.'},
#     {'role': 'user', 'content': 'Knock, knock.'},
#     {'role': 'assistant', 'content': "Hello! Who's there?"},
#     {'role': 'user', 'content': 'Guess who!'},
#     {'role': 'assistant', 'content': "Okay, I'll play along! Is it a person, a place, or a thing?"}
# ]

def main(streamlit_key_suffix: str = "") -> None:
  # st.error("*A computer can never be held accountable. Therefore a computer must never make a management decision.*[꙳](https://twitter.com/bumblebike/status/832394003492564993)")
  
  # st.markdown("What do you need help with? Cicero can help you: <ul><li>Rewrite a message<li>Analyze a message<li>_**MORE!**_</ul>", unsafe_allow_html=True)

  # Display chat messages from history on app reload; this is how we get the messages to display, and then the chat box.
  if st.session_state.get("messages"):
    for message in st.session_state.messages:
      with st.chat_message(message["role"], avatar=message.get("avatar")):
        st.markdown(message["content"].replace("$", r"\$").replace("[", r"\[")) #COULD: remove the \[ escaping, which is only useful for, what, markdown links? Which nobody uses.

  st.chat_input( "How can I help?", on_submit=grow_chat, key="user_input_for_chatbot_this_frame"+streamlit_key_suffix, args=(streamlit_key_suffix,) )

if __name__ == "__main__": main()
