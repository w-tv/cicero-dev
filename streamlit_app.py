#!/usr/bin/env -S streamlit run
""" This is Cicero.
You must have streamlit installed to run this program. Among other things. Why not run this script using run.bat instead?
Check the component_pages/ directory for various functionality of Cicero.
"""
from time import perf_counter_ns
nanoseconds_base : int = perf_counter_ns()
import streamlit as st
from streamlit.components.v1 import html
import os, psutil, platform
import urllib.parse
from typing import NoReturn
from component_pages import prompter, topic_reporting

st.set_page_config(layout="wide", page_title="Cicero", page_icon="favicon.png") # Use wide mode in Cicero, mostly so that results display more of their text by default. Also, set title and favicon. #NOTE: "`set_page_config()` can only be called once per app page, and must be called as the first Streamlit command in your script."

title_and_loading_columns = st.columns(2)
with title_and_loading_columns[0]:
  st.markdown('<h1><img src="https://targetedvictory.com/wp-content/uploads/2019/07/favicon.png" alt="💬" style="display:inline-block; height:1em; width:auto;"> CICERO</h1>', unsafe_allow_html=True)
with title_and_loading_columns[1]:
  loading_message = st.empty()
  loading_message.write("Loading CICERO.  This may take up to a minute...")

def blank_the_page_for_redirect() -> NoReturn: #ideally we wouldn't have to do this, but it's tough to use a single-tab workflow here because streamlit is entirely in an iframe, which breaks several things.
  authorization_url = st.session_state["authorization_url"]
  html(f'<script>window.open("{authorization_url}");</script><p>You have elected to sign-in with Google, which opens a new tab. You may now close this tab. If you do not see a new tab, visit <a href="{authorization_url}">click here</a></p>')
  exit()

if st.experimental_user['email'] is None:
  st.write("Your user email is None, which implies we are currently running publicly on Streamlit Community Cloud. https://docs.streamlit.io/library/api-reference/personalization/st.experimental_user#public-app-on-streamlit-community-cloud. This app is configured to function only privately and permissionedly, so we will now exit. Good day.")
  exit()

st.session_state['developer_mode'] = st.experimental_user['email'] in ["achang@targetedvictory.com", "test@example.com", "abrady@targetedvictory.com", "thall@targetedvictory.com", "afuhrer@targetedvictory.com", "wcarpenter@targetedvictory.com"] and not st.session_state.get("developer_mode_disabled")
def disable_developer_mode() -> None: st.session_state["developer_mode_disabled"] = True

if st.experimental_user['email'] == 'text@example.com':
  pass #The streamlit app is running "locally", which means everywhere but the streamlit community cloud. We probably won't end up relying on this behavior. This should eventually use the google email stuff, or we should have a firm idea about how the google email should override or be overridden by the streamlit community cloud email. Either way, we will only do this when we are ready, as it will make local testing slightly more inconvenient.

def get_base_url() -> str:
  """Gets the url where the streamlit app is currently running, not including any page paths underneath. In testing, for example, this value is probably http://localhost:8501 . This function is from BramVanroy https://github.com/streamlit/streamlit/issues/798#issuecomment-1647759949 , with modifications. “WARNING: I found that in multi-page apps, this will always only return the base url and not the sub-page URL with the page appended to the end.”"""
  try:
    session = st.runtime.get_instance()._session_mgr.list_active_sessions()[0] # There's occasionally a harmless IndexError: list index out of range from this line of code on Streamlit Community Cloud, which I'd like to suppress via this try-catch for the convenience of the reader of the logs.
    return urllib.parse.urlunparse([session.client.request.protocol, session.client.request.host, "", "", "", ""]) #type: ignore[attr-defined] #this is basically dark magic in streamlit so it's no wonder that I have to ignore an attr-defined type error about it.
  except IndexError as e:
    return str(e)

# Google sign-in logic. Taken from Miguel_Hentoux here https://discuss.streamlit.io/t/google-authentication-in-a-streamlit-app/43252/18 , and modified
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
def auth_flow() -> None:
  auth_code = st.query_params.get("code")
  # Use your json credentials from your google auth app (Web Client). You must place them, adapting their format, in secrets.toml under a heading (you'll note that everything in the json is in an object with the key "installed", so from that you should be able to figure out the rest.
  # previous versions of this code used [google_signin_secrets.installed], because, of course, the only us-defined portion is the google_signin_secrets portion
  flow = google_auth_oauthlib.flow.Flow.from_client_config(
    st.secrets["google_signin_secrets"],
    scopes=["https://www.googleapis.com/auth/userinfo.email", "openid"],
    redirect_uri=get_base_url(),
  )
  signed_in = False
  if auth_code:
    try:
      flow.fetch_token(code=auth_code)
      user_info_service = build(serviceName="oauth2", version="v2", credentials=flow.credentials)
      user_info = user_info_service.userinfo().get().execute()
      assert user_info.get("email"), "Email not found in google OAuth info"
      st.session_state["google_auth_code"] = auth_code
      st.session_state["user_info"] = user_info
      signed_in = True
    except Exception as e: #we always get an InvalidGrantError on an F5 if the user was logged-in. Not sure why.
      pass
  if not signed_in:
    authorization_url, state = flow.authorization_url(access_type="offline", include_granted_scopes="true") #ignore the fact that this says the access_type is offline, that's not relevant to our deployment; it's about something different.
    st.session_state["authorization_url"] = authorization_url
    st.button("Sign in with Google", on_click=blank_the_page_for_redirect)

if "google_auth_code" not in st.session_state: #TODO: use cookies to extend this state's lifetime.
  auth_flow()
if "google_auth_code" in st.session_state:
  st.session_state["email"] = st.session_state["user_info"].get("email")
  st.write(f"""Google signed-in as {st.session_state["email"]}""")

if st.session_state['developer_mode']: #dev-mode out the entirety of topic reporting
  tab1, tab2 = st.tabs(["🗣️ Prompter", "🌈 Topic Reporting"])
  with tab2:
    topic_reporting.main()
  with tab1:
    prompter.main()
else:
  prompter.main()

loading_message.empty() # At this point, we no longer need to display a loading message, once we've gotten here and displayed everything above.

with st.sidebar:
  if st.session_state['developer_mode']:
    st.caption(f"""Streamlit app memory usage: {psutil.Process(os.getpid()).memory_info().rss // 1024 ** 2} MiB.<br>
  Time to display: {(perf_counter_ns()-nanoseconds_base)/1000/1000/1000} seconds.<br>
  Python version: {platform.python_version()}<br>
  Base url: {get_base_url()}""", unsafe_allow_html=True)
    st.button("disable developer mode", on_click=disable_developer_mode, help="Click this button to disable developer mode, allowing you to see and interact with the app as a basic user would. You can refresh the page in your browser to re-enable developer mode.") #this is a callback for streamlit ui update-flow reasons.
