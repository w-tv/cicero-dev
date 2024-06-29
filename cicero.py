#!/usr/bin/env -S streamlit run
""" This is Cicero.
You must have streamlit installed to run this program. Among other things. Why not run this script using run.bat instead?
Check the cicero_*.py files for various functionalities of Cicero.
"""

from time import perf_counter_ns
nanoseconds_base : int = perf_counter_ns()
import streamlit as st
import os, psutil, platform
import cicero_prompter, cicero_topic_reporting, cicero_response_lookup, cicero_rag_only, cicero_new_pod_key
from cicero_shared import ensure_existence_of_activity_log, exit_error, get_base_url, sql_call_cacheless
from google.auth.transport import requests
from google.oauth2 import id_token
from streamlit.web.server.websocket_headers import _get_websocket_headers
from streamlit_profiler import Profiler

st.set_page_config(layout="wide", page_title="Cicero", page_icon=r"assets/CiceroLogo_Favicon.png") # Use wide mode in Cicero, mostly so that results display more of their text by default. Also, set title and favicon. #NOTE: "`set_page_config()` can only be called once per app page, and must be called as the first Streamlit command in your script."

def main() -> None:
  st.session_state["email"] = str(st.experimental_user["email"]) #this str call also accounts for if the user email is None.
  st.markdown("""
  <style>
    [data-testid="stDecoration"] {
      display: none;
    }

  </style>""", unsafe_allow_html=True) #this code removes the red bar at the top but keeps the hamburger menu
  # Google sign-in logic, using IAP. From https://cloud.google.com/iap/docs/signed-headers-howto, with modifications. Will set the email to a new value iff it succeeds.
  if h := _get_websocket_headers():
    if iap_jwt := h.get("X-Goog-Iap-Jwt-Assertion"):
      try:
        decoded_jwt = id_token.verify_token(iap_jwt, requests.Request(), audience=st.secrets["aud"], certs_url="https://www.gstatic.com/iap/verify/public_key") #type: ignore[no-untyped-call] #GOOGLE-OR-MYPY-BUG-WORKAROUND. I don't really know what the problem is here, but it's probably some inscrutable class thing. Could file a bug later, maybe.
        st.session_state["email"] = decoded_jwt["email"].split(":")[1]
      except Exception as e: # This pass probably hits if you don't have an aud, you don't have an X-Goog-IAP-JWT-Assertion header (you aren't behind an IAP), or the decode fails (the header is forged or otherwise invalid).
        st.write(e)

  if st.session_state['email'] == 'None':
    st.write("Your user email is None, which implies we are currently running publicly on Streamlit Community Cloud. https://docs.streamlit.io/library/api-reference/personalization/st.experimental_user#public-app-on-streamlit-community-cloud. This app is configured to function only privately and permissionedly, so we will now exit. Good day.")
    exit_error(34)
  if st.session_state['email'] == 'test@example.com' and not st.secrets.get("email_spoof"): # In this case, the streamlit app is running "locally", which means everywhere but the streamlit community cloud. email_spoof is a value in the secrets file to help me locally test-run the program without an IAP. This should be added to the secrets.toml. The value doesn't matter, so long as it's truthy. Do NOT add this value to the secrets.toml of production.
      st.write("Your user email is test@example.com, which implies we are currently running publicly, and not on Streamlit Community Cloud. https://docs.streamlit.io/library/api-reference/personalization/st.experimental_user#public-app-on-streamlit-community-cloud. This app is configured to function only privately and permissionedly, so we will now exit. Good day.")
      exit_error(35)

  title_and_loading_columns = st.columns(2)
  with title_and_loading_columns[0]:
    st.image(image="assets/CiceroLogo_Frontend_Cropped_400x107.png", use_column_width=False)
  with title_and_loading_columns[1]:
    loading_message = st.empty()
    loading_message.write("Loading CICERO.  This may take up to a minute...")

  st.session_state['developer_mode'] = st.session_state['email'] in ["achang@targetedvictory.com", "abrady@targetedvictory.com", "thall@targetedvictory.com", "afuhrer@targetedvictory.com", "wcarpenter@targetedvictory.com", "cmahon@targetedvictory.com", "rtauscher@targetedvictory.com", "cmajor@targetedvictory.com", "test@example.com"] and not st.session_state.get("developer_mode_disabled")
  def disable_developer_mode() -> None: st.session_state["developer_mode_disabled"] = True

  if st.session_state['developer_mode']: #dev-mode out the entirety of topic reporting (some day it will be perfect and the users will be ready for us to un-dev-mode it) # also dev-mode out response-lookup, which will probably be permanently dev-moded, along with New Pod Key
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🗣️ Prompter", "📈 Topic Reporting", "🔍 Response Lookup", "💬 Chat with Cicero", "🆕 New Pod Key"])
    with tab1:
      cicero_prompter.main()
    with tab2:
      cicero_topic_reporting.main()
    with tab3:
      cicero_response_lookup.main()
    with tab4:
      cicero_rag_only.main()
    with tab5:
      cicero_new_pod_key.main()
  else:
    cicero_prompter.main()
    st.markdown("""<style>
    [allow="accelerometer; ambient-light-sensor; autoplay; battery; camera; clipboard-write; document-domain; encrypted-media; fullscreen; geolocation; gyroscope; layout-animations; legacy-image-formats; magnetometer; microphone; midi; oversized-images; payment; picture-in-picture; publickey-credentials-get; sync-xhr; usb; vr ; wake-lock; xr-spatial-tracking"] { /*this is an arbitrary way to target the profiler element*/
      display: none;
    }

  </style>""", unsafe_allow_html=True)

  loading_message.empty() # At this point, we no longer need to display a loading message, once we've gotten here and displayed everything above.

  with st.sidebar:
    if st.session_state['developer_mode']:
      st.caption(f"""Streamlit app memory usage: {psutil.Process(os.getpid()).memory_info().rss // 1024 ** 2} MiB.<br>
        Time to display: {(perf_counter_ns()-nanoseconds_base)/1000/1000/1000} seconds.<br>
        Python version: {platform.python_version()}<br>
        Streamlit version: {st.__version__}<br>
        Base url: {get_base_url()}
      """, unsafe_allow_html=True)
      st.button("disable developer mode", on_click=disable_developer_mode, help="Click this button to disable developer mode, allowing you to see and interact with the app as a basic user would. You can refresh the page in your browser to re-enable developer mode.") #this is a callback for streamlit ui update-flow reasons.
if __name__ == "__main__":
  with Profiler():
    main()
    # This is here for end-user performance and convenience reasons, even though on every other axis this is a bad place for it.
    #TODO: it seems I can chat more before this is done loading. Do we lose some messages in the log that way?
    if st.session_state.get("activity_log_payload"):
      ensure_existence_of_activity_log()
      sql_call_cacheless(
        # The WTIH clause here basically just does a left join; I just happened to write it in this way.
        "WITH tmp(pod) AS (SELECT user_pod FROM cicero.default.user_pods WHERE user_email ilike :useremail) INSERT INTO cicero.default.activity_log\
        (timestamp,           user_email, user_pod,  prompter_or_chatbot,  prompt_sent,  response_given,  model_name,  model_url,  model_parameters,  system_prompt,  base_url) SELECT\
        current_timestamp(), :user_email, user_pod, :prompter_or_chatbot, :prompt_sent, :response_given, :model_name, :model_url, :model_parameters, :system_prompt, :base_url FROM tmp",
        st.session_state["activity_log_payload"]
      )
      st.session_state["activity_log_payload"] = None
