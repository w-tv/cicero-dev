#!/usr/bin/env -S streamlit run
""" This is Cicero.
You must have streamlit installed to run this program. Among other things. Why not run this script using run.bat instead?
Check the cicero_*.py files for various functionalities of Cicero.
"""
from time import perf_counter_ns
nanoseconds_base : int = perf_counter_ns()
import streamlit as st
#from streamlit.components.v1 import html
import os, psutil, platform
import urllib.parse
import cicero_prompter, cicero_topic_reporting, cicero_response_lookup, cicero_rag_only
from cicero_shared import exit_error
from google.auth.transport import requests
from google.oauth2 import id_token
from streamlit.web.server.websocket_headers import _get_websocket_headers

def get_base_url() -> str:
  """Gets the url where the streamlit app is currently running, not including any page paths underneath. In testing, for example, this value is probably http://localhost:8501 . This function is from BramVanroy https://github.com/streamlit/streamlit/issues/798#issuecomment-1647759949 , with modifications. “WARNING: I found that in multi-page apps, this will always only return the base url and not the sub-page URL with the page appended to the end.”"""
  try:
    session = st.runtime.get_instance()._session_mgr.list_active_sessions()[0] # There's occasionally a harmless IndexError: list index out of range from this line of code on Streamlit Community Cloud, which I'd like to suppress via this try-catch for the convenience of the reader of the logs.
    r = session.client.request #type: ignore[attr-defined] #MYPY-BUG-WORKAROUND mypy has various bugs about abstract classes and dataclasses, possibly this one: https://github.com/python/mypy/issues/16613
    if r.protocol == "http" and not r.host.startswith("localhost:"): # STREAMLIT-BUG-WORKAROUND (?) for some reason even when we're in an https connection the r.protocol is http. https://github.com/streamlit/streamlit/issues/8600
      r.protocol = "https"
    return str(
      urllib.parse.urlunparse([r.protocol, r.host, "", "", "", ""])# see also: https://github.com/python/mypy/issues/17082
    )
  except IndexError as e:
    return str(e)

def main() -> None:
  st.set_page_config(layout="wide", page_title="Cicero", page_icon="favicon.png") # Use wide mode in Cicero, mostly so that results display more of their text by default. Also, set title and favicon. #NOTE: "`set_page_config()` can only be called once per app page, and must be called as the first Streamlit command in your script."
  st.session_state["email"] = str(st.experimental_user["email"]) #this str call also accounts for if the user email is None.
  st.caption("Web headers:")
  st.write(h := _get_websocket_headers())
  # Google sign-in logic, using IAP. From https://cloud.google.com/iap/docs/signed-headers-howto, with modifications. Will set the email to a new value iff it succeeds.
  if h := _get_websocket_headers():
    if iap_jwt := h.get("X-Goog-IAP-JWT-Assertion"):
      try:
        aud = "/projects/513922616175/global/backendServices/7187241006853512289" # should this be in st.secrets["aud"] ?
        decoded_jwt = id_token.verify_token(iap_jwt, requests.Request(), audience=aud, certs_url="https://www.gstatic.com/iap/verify/public_key")
        st.session_state["email"] = decoded_jwt["email"]
      except Exception as _e: # This pass probably hits if you don't have an aud, you don't have an X-Goog-IAP-JWT-Assertion header (you aren't behind an IAP), or the decode fails (the header is forged or otherwise invalid).
        pass
  if st.session_state['email'] == 'None':
    st.write("Your user email is None, which implies we are currently running publicly on Streamlit Community Cloud. https://docs.streamlit.io/library/api-reference/personalization/st.experimental_user#public-app-on-streamlit-community-cloud. This app is configured to function only privately and permissionedly, so we will now exit. Good day.")
    exit_error(34)
  if st.session_state['email'] == 'test@example.com' and not st.secrets.get("email_spoof"): # In this case, the streamlit app is running "locally", which means everywhere but the streamlit community cloud. email_spoof is a value in the secrets file to help me locally test-run the program without an IAP. This should be added to the secrets.toml. The value doesn't matter, so long as it's truthy. Do NOT add this value to the secrets.toml of production.
      st.write("Your user email is test@example.com, which implies we are currently running publicly, and not on Streamlit Community Cloud. https://docs.streamlit.io/library/api-reference/personalization/st.experimental_user#public-app-on-streamlit-community-cloud. This app is configured to function only privately and permissionedly, so we will now exit. Good day.")
      exit_error(35)

  title_and_loading_columns = st.columns(2)
  with title_and_loading_columns[0]:
    st.markdown('<h1><img src="https://targetedvictory.com/wp-content/uploads/2019/07/favicon.png" alt="💬" style="display:inline-block; height:1em; width:auto;"> CICERO</h1>', unsafe_allow_html=True)
  with title_and_loading_columns[1]:
    loading_message = st.empty()
    loading_message.write("Loading CICERO.  This may take up to a minute...")

  st.session_state['developer_mode'] = st.session_state['email'] in ["achang@targetedvictory.com", "abrady@targetedvictory.com", "thall@targetedvictory.com", "afuhrer@targetedvictory.com", "wcarpenter@targetedvictory.com", "cmahon@targetedvictory.com", "rtauscher@targetedvictory.com", "cmajor@targetedvictory.com", "test@example.com"] and not st.session_state.get("developer_mode_disabled")
  def disable_developer_mode() -> None: st.session_state["developer_mode_disabled"] = True

  if st.session_state['developer_mode']: #dev-mode out the entirety of topic reporting (some day it will be perfect and the users will be ready for us to un-dev-mode it) # also dev-mode out response-lookup, which will probably be permanently dev-moded
    tab1, tab2, tab3, tab4 = st.tabs(["🗣️ Prompter", "🌈 Topic Reporting", "🔍 Response Lookup", "🎰 The RAG Man"])
    with tab2: # We load this first because it takes less time, so a person trying to use topic reporting quickly can simply switch to that tab to do so.
      cicero_topic_reporting.main()
    with tab1:
      cicero_prompter.main()
    with tab3:
      cicero_response_lookup.main()
    with tab4:
      cicero_rag_only.main()
  else:
    cicero_prompter.main()

  loading_message.empty() # At this point, we no longer need to display a loading message, once we've gotten here and displayed everything above.

  with st.sidebar:
    if st.session_state['developer_mode']:
      st.caption(f"""Streamlit app memory usage: {psutil.Process(os.getpid()).memory_info().rss // 1024 ** 2} MiB.<br>
        Time to display: {(perf_counter_ns()-nanoseconds_base)/1000/1000/1000} seconds.<br>
        Python version: {platform.python_version()}<br>
        Streamlit version: {st.__version__}<br>
        Base url: {get_base_url()}
      """, unsafe_allow_html=True)
      st.caption("Web headers:")
      st.write(h := _get_websocket_headers())
      if h:
        st.write("X-Goog-Authenticated-User-Email", h.get("X-Goog-Authenticated-User-Email"))
        st.write("X-Goog-IAP-JWT-Assertion", h.get("X-Goog-IAP-JWT-Assertion"))
      if st.button("Crash the program."):
        exit_error(27)
      st.button("disable developer mode", on_click=disable_developer_mode, help="Click this button to disable developer mode, allowing you to see and interact with the app as a basic user would. You can refresh the page in your browser to re-enable developer mode.") #this is a callback for streamlit ui update-flow reasons.
if __name__ == "__main__": main()
