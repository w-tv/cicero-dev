#!/usr/bin/env -S streamlit run
""" This is Cicero.
You must have streamlit installed to run this program. Among other things. Why not run this script using run.bat instead?
Check the cicero_*.py files for various functionalities of Cicero.
"""

from time import perf_counter_ns
nanoseconds_base : int = perf_counter_ns()
import streamlit as st
import os, psutil, platform
from cicero_shared import ensure_existence_of_activity_log, exit_error, get_base_url, sql_call_cacheless
from google.auth.transport import requests
from google.oauth2 import id_token
from streamlit.web.server.websocket_headers import _get_websocket_headers
from streamlit_profiler import Profiler
from datetime import datetime

with Profiler():
  st.set_page_config(layout="wide", page_title="Cicero", page_icon=r"assets/CiceroLogo_Favicon.png") # Use wide mode in Cicero, mostly so that results display more of their text by default. Also, set title and favicon. #NOTE: "`set_page_config()` can only be called once per app page, and must be called as the first Streamlit command in your script."
  for x in st.session_state: #If we don't do this ritual, streamlit drops all the non-active-pages widget states on the floor (bad). https://docs.streamlit.io/develop/concepts/multipage-apps/widgets#option-3-interrupt-the-widget-clean-up-process
    if not x.startswith("FormSubmitter:") and not x.startswith("⚡") and not x.startswith("👍") and not x.startswith("👎") and not x.startswith("user_input_for_chatbot_this_frame"): #Prevent this error: streamlit.errors.StreamlitAPIException: Values for the widget with key "FormSubmitter:query_builder-Submit" cannot be set using `st.session_state`. # Also prevent this error: StreamlitAPIException: Values for the widget with key "⚡1" cannot be set using st.session_state. And similarly for 👍. In general the buttons that can't have state set, I set their keys to emoji+suffix. Just because.
      st.session_state[x] = st.session_state[x]

  st.session_state["email"] = str(st.experimental_user["email"]) #this str call also accounts for if the user email is None.
  st.markdown("""<style> [data-testid="stDecoration"] { display: none; } </style>""", unsafe_allow_html=True) #this code removes the red bar at the top but keeps the hamburger menu
  st.markdown("""<style> [data-testid="stAppViewBlockContainer"] { padding-top: 1.5rem; } </style>""", unsafe_allow_html=True) #this removes much of the annoying headroom padding on the main ui, although we can't remove all of it because the loading indicators are actually a solid bar that would obscure the logo (I'm not sure why).


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
  def disable_developer_mode() -> None:
    st.session_state["developer_mode_disabled"] = True

  # Since we use st.navigation explicitly, the default page detection is disabled, even though we may use a pages folder later (although we shouldn't name that folder pages/, purely in order to suppress a warning message about how we shouldn't do that). This is good, because we want to hide some of the pages from non-dev-mode users.
  pages = [ #pages visible to everyone
    st.Page("cicero_prompter.py", title="🗣️ Prompter"), # There is an icon parameter to st.Page, so we could write eg icon="🗣️", but including the emoji in the title makes it slightly larger and thus nicer-looking.
  ]
  if st.session_state.get('developer_mode'):
    pages += [
      st.Page("cicero_topic_reporting.py", title="📈 Topic Reporting"),
      st.Page("cicero_response_lookup.py", title="🔍 Response Lookup"),
      st.Page("cicero_chat.py", title="💬 Chat with Cicero"),
      st.Page("cicero_new_pod_key.py", title="🆕 New Pod Key"),
      st.Page("cicero_activity_looker.py", title="👁️ Activity Looker")
    ]
  st.navigation(pages).run()
  loading_message.empty() # At this point, we no longer need to display a loading message, once we've gotten here and displayed everything above.

  if st.session_state.get('developer_mode'): # Developer information about the app (performance, etc).
    with st.sidebar:
      st.caption(f"""Streamlit app memory usage: {psutil.Process(os.getpid()).memory_info().rss // 1024 ** 2} MiB.<br>
        Time to display: {(perf_counter_ns()-nanoseconds_base)/1000/1000/1000} seconds.<br>
        Python version: {platform.python_version()}<br>
        Streamlit version: {st.__version__}<br>
        Base url: {get_base_url()}
      """, unsafe_allow_html=True)
      st.button("disable developer mode", on_click=disable_developer_mode, help="Click this button to disable developer mode, allowing you to see and interact with the app as a basic user would. You can refresh the page in your browser to re-enable developer mode.") #this is a callback for streamlit ui update-flow reasons.
  else: # Disable the profiler element visually, using css, if not in dev mode.
    st.markdown("""<style> [allow="accelerometer; ambient-light-sensor; autoplay; battery; camera; clipboard-write; document-domain; encrypted-media; fullscreen; geolocation; gyroscope; layout-animations; legacy-image-formats; magnetometer; microphone; midi; oversized-images; payment; picture-in-picture; publickey-credentials-get; sync-xhr; usb; vr ; wake-lock; xr-spatial-tracking"] { /*this is an arbitrary way to target the profiler element*/ display: none; } </style>""", unsafe_allow_html=True)

  # Write to the activity log if we need to. These are here for end-user performance/convenience reasons, even though on every other axis this is a bad place for it:
  if st.session_state.get("activity_log_payload"):
    print("Writing to log.")
    ensure_existence_of_activity_log()
    sql_call_cacheless(
      # The WTIH clause here basically just does a left join; I just happened to write it in this way.
      # Note that this will implicitly null the user_feedback. Which simplifies the deployment of that as a new feature, at least...!
      "WITH tmp(user_pod) AS (SELECT user_pod FROM cicero.default.user_pods WHERE user_email ilike :user_email) INSERT INTO cicero.default.activity_log\
      (timestamp,           user_email, user_pod,  prompter_or_chatbot,  prompt_sent,  response_given,  model_name,  model_url,  model_parameters,  system_prompt,  base_url) SELECT\
      current_timestamp(), :user_email, user_pod, :prompter_or_chatbot, :prompt_sent, :response_given, :model_name, :model_url, :model_parameters, :system_prompt, :base_url FROM tmp",
      st.session_state["activity_log_payload"]
    )
    st.session_state["activity_log_payload"] = None
    print("Done writing to log.")

  if st.session_state.get("outstanding_activity_log_payload_fulfilled"):
    try:
      print("Writing to 👍/👎 log.")
    except UnicodeEncodeError:
      print("Writing to Thumbs Log")
      pass
    ensure_existence_of_activity_log()
    sql_call_cacheless(
      # Note: we are GAMBLING that the user_pod and timestamp will never be necessary in practice to have in here, because getting them would be inconvenient.
      "UPDATE cicero.default.activity_log SET user_feedback = :user_feedback WHERE user_email = :user_email AND prompter_or_chatbot = :prompter_or_chatbot AND prompt_sent = :prompt_sent AND response_given = :response_given AND model_name = :model_name AND model_url = :model_url AND model_parameters = :model_parameters AND system_prompt = :system_prompt AND base_url = :base_url;",
      st.session_state["outstanding_activity_log_payload_fulfilled"]
    )
    st.session_state["outstanding_activity_log_payload_fulfilled"] = None
    print("Done writing to log.")

  print("End of a run.", str(datetime.now()).split('.')[0])
