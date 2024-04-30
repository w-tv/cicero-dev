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
from typing import NoReturn
import cicero_prompter, cicero_topic_reporting, cicero_response_lookup, cicero_rag_only
from cicero_shared import sql_call, exit_error
import secrets #TODO: could use this for nonce if we don't just the auth code?
import google_auth_oauthlib.flow
from googleapiclient.discovery import build

def get_base_url() -> str:
  """Gets the url where the streamlit app is currently running, not including any page paths underneath. In testing, for example, this value is probably http://localhost:8501 . This function is from BramVanroy https://github.com/streamlit/streamlit/issues/798#issuecomment-1647759949 , with modifications. “WARNING: I found that in multi-page apps, this will always only return the base url and not the sub-page URL with the page appended to the end.”"""
  try:
    session = st.runtime.get_instance()._session_mgr.list_active_sessions()[0] # There's occasionally a harmless IndexError: list index out of range from this line of code on Streamlit Community Cloud, which I'd like to suppress via this try-catch for the convenience of the reader of the logs.
    r = session.client.request #type: ignore[attr-defined] #MYPY-BUG-WORKAROUND mypy has various bugs about abstract classes and dataclasses, possibly this one: https://github.com/python/mypy/issues/16613
    return str(
      urllib.parse.urlunparse([r.protocol, r.host, "", "", "", ""]) #, list-item] #session.client.request is basically dark magic in streamlit so it's no wonder that I have to ignore an attr-defined type error about it. The list-item one just fixes a bug in either mypy or (less likely (since the type annotation looks alright) typeshed, though. (It wants all the arguments to be None for some reason.) The str call also is just to appease mypy's misconception. ), https://github.com/python/mypy/issues/17082
    )
  except IndexError as e:
    return str(e)

def google_email_from_nonce(nonce: str) -> str|None: #The nonce here is the nonsense string we associate with an email to prevent the user from being able to spoof identity using cookies. We get the nonce from the param code in the url elsewhere in this code.
  sql_call("CREATE TABLE IF NOT EXISTS cicero.default.nonce_to_google_email (nonce string, google_email string)")
  value = sql_call("SELECT google_email FROM cicero.default.nonce_to_google_email WHERE nonce = %(nonce)s", {"nonce": nonce})
  if len(value):
    return str(value[0])
  else:
    return None
def set_google_email_from_nonce(google_email: str, nonce: str) -> None:
  sql_call("CREATE TABLE IF NOT EXISTS cicero.default.nonce_to_google_email (nonce string, google_email string)")
  sql_call("INSERT INTO cicero.default.nonce_to_google_email (nonce, google_email) VALUES (%(nonce)s, %(google_email)s)", {"nonce": nonce, "google_email": google_email})
def remove_google_email_from_nonce(nonce: str) -> None: # Technically this is optional, but we might as well clear up the table.
  sql_call("CREATE TABLE IF NOT EXISTS cicero.default.nonce_to_google_email (nonce string, google_email string)")
  sql_call("DELETE FROM cicero.default.nonce_to_google_email WHERE nonce = %(nonce)s", {"nonce": nonce})

def blank_the_page_and_redirect(authorization_url: str) -> NoReturn: #ideally we wouldn't have to do this, but it's tough to use a single-tab workflow here because streamlit is entirely in an iframe, which breaks several things.
  print(authorization_url)
  html(f'<script>window.open("{authorization_url}");</script><p>You have elected to sign-in with Google, which opens a new tab. You may now close this tab. If you do not see a new tab, <b>enable pop-ups and/or redirects for this page in your browser</b> and <a href="{authorization_url}">click here</a></p>')
  exit() #Notably: not an exit_error, just a regular exit.

def main() -> None:
  st.set_page_config(layout="wide", page_title="Cicero", page_icon="favicon.png") # Use wide mode in Cicero, mostly so that results display more of their text by default. Also, set title and favicon. #NOTE: "`set_page_config()` can only be called once per app page, and must be called as the first Streamlit command in your script."
  class FakeCookieManager: #TODO: had to remove the actual cookie manager, so only this fake one remains. It does not actually persist state.
    def __init__(self, di = {}):
      self.d = di
    def get(self, x):
      return self.d.get(x)
    def set(self, x, y):
      self.d[x] = y
    def get_all(self):
      return self.d
  cookie_manager = FakeCookieManager()
  title_and_loading_columns = st.columns(2)
  with title_and_loading_columns[0]:
    st.markdown('<h1><img src="https://targetedvictory.com/wp-content/uploads/2019/07/favicon.png" alt="💬" style="display:inline-block; height:1em; width:auto;"> CICERO</h1>', unsafe_allow_html=True)
  with title_and_loading_columns[1]:
    loading_message = st.empty()
    loading_message.write("Loading CICERO.  This may take up to a minute...")

  if st.experimental_user['email'] is None:
    st.write("Your user email is None, which implies we are currently running publicly on Streamlit Community Cloud. https://docs.streamlit.io/library/api-reference/personalization/st.experimental_user#public-app-on-streamlit-community-cloud. This app is configured to function only privately and permissionedly, so we will now exit. Good day.")
    exit_error(34)

  st.session_state['developer_mode'] = st.experimental_user['email'] in ["achang@targetedvictory.com", "test@example.com", "abrady@targetedvictory.com", "thall@targetedvictory.com", "afuhrer@targetedvictory.com", "wcarpenter@targetedvictory.com"] and not st.session_state.get("developer_mode_disabled")
  def disable_developer_mode() -> None: st.session_state["developer_mode_disabled"] = True

  if st.experimental_user['email'] == 'text@example.com':
    pass #The streamlit app is running "locally", which means everywhere but the streamlit community cloud. We probably won't end up relying on this behavior. This should eventually use the google email stuff, or we should have a firm idea about how the google email should override or be overridden by the streamlit community cloud email. Either way, we will only do this when we are ready, as it will make local testing slightly more inconvenient.

  if st.session_state['developer_mode']: #dev-mode out the entirety of google sign-in
    #TODO: why doesn't this work? It seems to work locally, so maybe the google permission granting settings are wrong?
    # Google sign-in logic, adapted from Miguel_Hentoux here https://discuss.streamlit.io/t/google-authentication-in-a-streamlit-app/43252/18
    # Set up the flow (which is just an api call or something I guess. For the first argument, the secrets, use your json credentials from your google auth app (Web Client). You must place them, adapting their format, in secrets.toml under a heading (you'll note that everything in the json is in an object with the key "installed", so from that you should be able to figure out the rest.
    # previous versions of this code used [google_signin_secrets.installed], because, of course, the only us-defined portion is the google_signin_secrets portion
    st.write("Cookie time:", cookie_manager.get("google_account_nonce"))
    if not cookie_manager.get("google_account_nonce"): # We don't have any nonce, so just offer the option to sign in like regular using google OR we are currently in the process of signing in, in which case continue that.
      auth_code = st.query_params.get("code")
      flow = google_auth_oauthlib.flow.Flow.from_client_config( st.secrets["google_signin_secrets"], scopes=["https://www.googleapis.com/auth/userinfo.email", "openid"], redirect_uri=get_base_url() )
      if auth_code: # detect whether the current url has '&code=' in it (in which case we're actively signing in during this step).
        print("!"*20, auth_code)
        try:
          flow.fetch_token(code=auth_code)
          user_info_service = build(serviceName="oauth2", version="v2", credentials=flow.credentials)
          user_info = user_info_service.userinfo().get().execute()
          assert user_info.get("email"), "Email not found in google OAuth info"
          st.session_state["email"] = user_info.get("email")
          set_google_email_from_nonce(google_email=st.session_state["email"], nonce=auth_code)
          cookie_manager.set("google_account_nonce", auth_code)
        except Exception as e: #I'm pretty sure this fires multiple times, which is the problem.
          if str(e) == "(invalid_grant) Bad Request":
            pass
          else:
            raise e
      else: #if we aren't actively logging in, and we aren't already logged in, give the user the option to log in:
        authorization_url, state = flow.authorization_url(access_type="offline", include_granted_scopes="true") #ignore the fact that this says the access_type is "offline", that's not relevant to our deployment (which is both online and offline, so to speak); it's about something different.
        st.write(secrets.token_hex(256))
        st.button("Sign in with Google", on_click=lambda: blank_the_page_and_redirect(authorization_url))

    if nonce := cookie_manager.get("google_account_nonce"): # We "remember" a nonce in our cookies, and are going to try to "sign in" to cicero using it (in cicero's local table, not in google itself).
      st.write("we have nonce")
      if google_email := google_email_from_nonce(nonce): # There is an email, so we have "signed in" successfully.
        st.session_state["email"] = google_email
        st.write(f"""Google signed-in as {st.session_state["email"]}""")
        if st.button("Sign out from Google"): #since we're signed-in, have an option to sign out!
          cookie_manager.delete("google_account_nonce")
          remove_google_email_from_nonce(nonce)
      else: # We had a nonce, but it was not associated with an email, so we did not "sign in" successfully.
        st.write("nonce bad, removing nonce")
        cookie_manager.delete("google_account_nonce")

  if st.session_state['developer_mode']: #dev-mode out the entirety of topic reporting (some day it will be perfect and the users will be ready for us to un-dev-mode it) # also response-lookup, which will probably be permanently dev-moded
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
      cookies = cookie_manager.get_all()
      st.write(cookies)

      if st.button("Crash the program."):
        exit_error(27)

      st.button("disable developer mode", on_click=disable_developer_mode, help="Click this button to disable developer mode, allowing you to see and interact with the app as a basic user would. You can refresh the page in your browser to re-enable developer mode.") #this is a callback for streamlit ui update-flow reasons.
if __name__ == "__main__": main()