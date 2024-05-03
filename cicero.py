#!/usr/bin/env -S streamlit run
""" This is Cicero.
You must have streamlit installed to run this program. Among other things. Why not run this script using run.bat instead?
Check the cicero_*.py files for various functionalities of Cicero.
"""
from time import perf_counter_ns
nanoseconds_base : int = perf_counter_ns()
import streamlit as st
from streamlit.components.v1 import html
import os, psutil, platform
import urllib.parse
from typing import Any, NoReturn
import cicero_prompter, cicero_topic_reporting, cicero_response_lookup, cicero_rag_only
from cicero_shared import sql_call, exit_error
#import secrets #COULD: use this for nonce if we don't just the auth code?
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from streamlit_cookies_controller import CookieController

def assert_always(x: Any, message_to_assert: str|None = None) -> None | NoReturn:
  """This function is equivalent to assert, but cannot be disabled by -O"""
  if not x:
    raise AssertionError(message_to_assert or x)
  return None

def get_base_url() -> str:
  """Gets the url where the streamlit app is currently running, not including any page paths underneath. In testing, for example, this value is probably http://localhost:8501 . This function is from BramVanroy https://github.com/streamlit/streamlit/issues/798#issuecomment-1647759949 , with modifications. “WARNING: I found that in multi-page apps, this will always only return the base url and not the sub-page URL with the page appended to the end.”"""
  try:
    session = st.runtime.get_instance()._session_mgr.list_active_sessions()[0] # There's occasionally a harmless IndexError: list index out of range from this line of code on Streamlit Community Cloud, which I'd like to suppress via this try-catch for the convenience of the reader of the logs.
    r = session.client.request #type: ignore[attr-defined] #MYPY-BUG-WORKAROUND mypy has various bugs about abstract classes and dataclasses, possibly this one: https://github.com/python/mypy/issues/16613
    if r.protocol == "http" and not r.host.startswith("localhost:"): # STREAMLIT-BUG-WORKAROUND (?) for some reason even when we're in an https connection the r.protocol is http.
      r.protocol = "https"
    return str(
      urllib.parse.urlunparse([r.protocol, r.host, "", "", "", ""]) #, list-item] #session.client.request is basically dark magic in streamlit so it's no wonder that I have to ignore an attr-defined type error about it. The list-item one just fixes a bug in either mypy or (less likely (since the type annotation looks alright) typeshed, though. (It wants all the arguments to be None for some reason.) The str call also is just to appease mypy's misconception. ), https://github.com/python/mypy/issues/17082
    )
  except IndexError as e:
    return str(e)

def google_email_from_nonce(nonce: str) -> str|None: #The nonce here is the nonsense string we associate with an email to prevent the user from being able to spoof identity using cookies. We get the nonce from the param code in the url elsewhere in this code.
  sql_call("CREATE TABLE IF NOT EXISTS cicero.default.nonce_to_google_email (nonce string, google_email string)")
  value = sql_call("SELECT google_email FROM cicero.default.nonce_to_google_email WHERE nonce = %(nonce)s", {"nonce": nonce})
  if len(value):
    return str(value[0][0])
  else:
    return None
def set_google_email_from_nonce(google_email: str, nonce: str) -> None:
  sql_call("CREATE TABLE IF NOT EXISTS cicero.default.nonce_to_google_email (nonce string, google_email string)")
  sql_call("INSERT INTO cicero.default.nonce_to_google_email (nonce, google_email) VALUES (%(nonce)s, %(google_email)s)", {"nonce": nonce, "google_email": google_email})
def remove_google_email_from_nonce(nonce: str) -> None: # Technically this step is optional, but we might as well clear up the table.
  sql_call("CREATE TABLE IF NOT EXISTS cicero.default.nonce_to_google_email (nonce string, google_email string)")
  sql_call("DELETE FROM cicero.default.nonce_to_google_email WHERE nonce = %(nonce)s", {"nonce": nonce})

def google_sign_out(cookie_manager: CookieController, nonce: str) -> None:
  cookie_manager.remove("google_account_nonce")
  remove_google_email_from_nonce(nonce)
  st.write("Note: it disturbs the Google API for me to offer you the option to sign in again, so instead the app will now end. You may reload the page to continue.") # TODO: Not sure if this is true or it's some other problem. Possibly just an invisible max quota I'm running into during testing?
  exit_error(99)

def blank_the_page_and_redirect(authorization_url: str) -> NoReturn: #ideally we wouldn't have to do this, but it's tough to use a single-tab workflow here because streamlit is entirely in an iframe, which breaks several things.
  html(f'<script>window.open("{authorization_url}");</script><p>You have elected to sign-in with Google, which opens a new tab. You may now close this tab. If you do not see a new tab, <b>enable pop-ups and/or redirects for this page in your browser</b> and <a href="{authorization_url}">click here</a></p>')
  exit() #Notably: not an exit_error, just a regular exit.

def main() -> None:
  st.set_page_config(layout="wide", page_title="Cicero", page_icon="favicon.png") # Use wide mode in Cicero, mostly so that results display more of their text by default. Also, set title and favicon. #NOTE: "`set_page_config()` can only be called once per app page, and must be called as the first Streamlit command in your script."
  st.session_state["email"] = str(st.experimental_user["email"]) #this str call also accounts for if the user email is None.

  cookie_manager = CookieController()

  # Google sign-in logic, adapted from Miguel_Hentoux here https://discuss.streamlit.io/t/google-authentication-in-a-streamlit-app/43252/18
  # Set up the flow (which is just an api call or something I guess). For the first argument, the secrets, use your json credentials from your google auth app (Web Client). You must place them, adapting their format (try json-to-toml.py in this folder), in secrets.toml under a heading (you'll note that everything in the json is in an object with the key "installed", so from that you should be able to figure out the rest).
  if not cookie_manager.get("google_account_nonce"): # In this case, we don't have any nonce, so just offer the option to sign in like regular using google OR we are currently in the process of signing in, in which case continue that.
    auth_code = st.query_params.get("code")
    flow = google_auth_oauthlib.flow.Flow.from_client_config( st.secrets["google_signin_secrets"], scopes=["https://www.googleapis.com/auth/userinfo.email", "openid"], redirect_uri=get_base_url() )
    try:
      assert_always(auth_code, "This assert detects whether the current url has '&code=' in it (in which case we're actively signing in during this step). It is expected to fail pretty often, and in fact is just used for flow control here.")
      flow.fetch_token(code=auth_code)
      user_info_service = build(serviceName="oauth2", version="v2", credentials=flow.credentials)
      user_info = user_info_service.userinfo().get().execute()
      assert_always(user_info.get("email"), "Email not found in google OAuth info")
      st.session_state["email"] = user_info.get("email")
      set_google_email_from_nonce(google_email=st.session_state["email"], nonce=auth_code or "") #COULD: replace this ‘ or "" ’ with some sophisticated typeguard (possibly parameterized) or something. But I haven't bothered.
      cookie_manager.set("google_account_nonce", auth_code)
      st.query_params.clear()
    except Exception as e: #if we aren't actively logging in, and we aren't already logged in, give the user the option to log in:
      print(e)
      authorization_url, state = flow.authorization_url(access_type="offline", include_granted_scopes="true") #ignore the fact that this says the access_type is "offline", that's not relevant to our deployment (which is both online and offline, so to speak); it's about something different.
      #st.write(secrets.token_hex(256))
      st.button("Sign in with Google", on_click=lambda: blank_the_page_and_redirect(authorization_url))

  if nonce := cookie_manager.get("google_account_nonce"): # We "remember" a nonce in our cookies, and are going to try to "sign in" to cicero using it (in cicero's local table, not in google itself).
    #st.write("we have nonce")
    if google_email := google_email_from_nonce(nonce): # There is an email, so we have "signed in" successfully.
      st.session_state["email"] = google_email
      #st.write(f"""Google signed-in as {st.session_state["email"]}""")
      st.button("Sign out from Google", on_click=google_sign_out, args=(cookie_manager, nonce)) #since we're signed-in, have an option to sign out!
    else: # We had a nonce, but it was not associated with an email, so we did not "sign in" successfully.
      st.write("nonce bad, removing nonce")
      cookie_manager.remove("google_account_nonce")

  if st.session_state['email'] == 'None':
    st.write("Your user email is None, which implies we are currently running publicly on Streamlit Community Cloud. https://docs.streamlit.io/library/api-reference/personalization/st.experimental_user#public-app-on-streamlit-community-cloud. This app is configured to function only privately and permissionedly, so we will now exit. Good day.")
    exit_error(34)
  if st.session_state['email'] == 'test@example.com': # In this case, the streamlit app is running "locally", which means everywhere but the streamlit community cloud.
    st.write("Please sign in to continue.")
    exit()

  title_and_loading_columns = st.columns(2)
  with title_and_loading_columns[0]:
    st.markdown('<h1><img src="https://targetedvictory.com/wp-content/uploads/2019/07/favicon.png" alt="💬" style="display:inline-block; height:1em; width:auto;"> CICERO</h1>', unsafe_allow_html=True)
  with title_and_loading_columns[1]:
    loading_message = st.empty()
    loading_message.write("Loading CICERO.  This may take up to a minute...")



  st.session_state['developer_mode'] = st.session_state['email'] in ["achang@targetedvictory.com", "abrady@targetedvictory.com", "thall@targetedvictory.com", "afuhrer@targetedvictory.com", "wcarpenter@targetedvictory.com"] and not st.session_state.get("developer_mode_disabled")
  def disable_developer_mode() -> None: st.session_state["developer_mode_disabled"] = True

  if st.session_state['developer_mode']: #dev-mode out the entirety of topic reporting (some day it will be perfect and the users will be ready for us to un-dev-mode it) # also dev-mode out response-lookup, which will probably be permanently dev-moded
    tab1, tab2, tab3, tab4 = st.tabs(["🗣️ Prompter", "🌈 Topic Reporting", "🔍 Response Lookup", "🎰 The RAG Man"])
    with tab2: # We load this first because it's less onerous, so a person trying to use topic reporting quickly can simply switch to that tab to do so.
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
        Base url: {get_base_url()}<br>
        User info: {st.session_state.get("user_info")}
      """, unsafe_allow_html=True)

      st.caption("Cookies:")
      cookies = cookie_manager.getAll()
      st.write(cookies)

      if st.button("Crash the program."):
        exit_error(27)

      st.button("disable developer mode", on_click=disable_developer_mode, help="Click this button to disable developer mode, allowing you to see and interact with the app as a basic user would. You can refresh the page in your browser to re-enable developer mode.") #this is a callback for streamlit ui update-flow reasons.
if __name__ == "__main__": main()