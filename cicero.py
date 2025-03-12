#!/usr/bin/env -S streamlit run
"""This is Cicero.
You must have streamlit installed to run this program. Among other things. Why not run this script using run.bat instead?
Check the cicero_*.py files for various functionalities of Cicero. This file basically just does user auth, displays some stats, and hosts subsidiary pages (one will be open by default).
"""

import streamlit as st
import os
import psutil
import platform
from sys import argv
from cicero_chat import main as cicero_chat_main
from cicero_shared import admin_box, admin_str, ensure_existence_of_activity_log, exit_error, get_base_url, get_list_value_of_column_in_table, get_value_of_column_in_table, is_admin, sql_call_cacheless, ssget, ssset, sspop, st_print
from google.auth.transport import requests
from google.oauth2 import id_token
from wfork_streamlit_profiler import Profiler
from datetime import datetime
from time import perf_counter_ns
nanoseconds_base : int = perf_counter_ns()

if argv[1:]:
  print(f"Running Cicero with command-line arguments: {argv[1:]}")

def get_git_head_hash() -> str|FileNotFoundError:
  try:
    return open(".git/refs/heads/master", "r").read()[:7]
  except FileNotFoundError as e:
    return e

if not ssget("git_head_hash_on_startup"):
  # The idea is that we set this only once until the program completely resets, so that the version of Cicero that is active in RAM won't read the wrong version off of the disk storage (thereby ruining the entire point of displaying the head hash value), which may or may not have been the cause of a problem we were running into. (Note that during local development the active code won't match the head hash anyway, since it's running from the working tree, instead; but that doesn't matter.)
  ssset( "git_head_hash_on_startup", get_git_head_hash() )

with Profiler():
  st.set_page_config(layout="wide", page_title="Cicero", page_icon=r"assets/CiceroLogo_Favicon.png") # Use wide mode in Cicero, mostly so that results display more of their text by default. Also, set title and favicon. #NOTE: "`set_page_config()` can only be called once per app page, and must be called as the first Streamlit command in your script."

  for x in st.session_state: #If we don't do this ritual, streamlit drops all the non-active-pages widget states on the floor (bad). https://docs.streamlit.io/develop/concepts/multipage-apps/widgets#option-3-interrupt-the-widget-clean-up-process
    if not x.startswith("FormSubmitter:") and not x.startswith("⚡") and not x.startswith("👍") and not x.startswith("👎") and not x.startswith("user_input_for_chatbot_this_frame") and x not in ("unlucky", "chat_file_uploader", "voice_map_editor"): #Prevent this error: streamlit.errors.StreamlitAPIException: Values for the widget with key "FormSubmitter:query_builder-Submit" cannot be set using `st.session_state`. # Also prevent this error: StreamlitAPIException: Values for the widget with key "⚡1" cannot be set using st.session_state. And similarly for 👍. In general the buttons that can't have state set, I set their keys to emoji+suffix. Just because.
      st.session_state[x] = st.session_state[x]

  st.markdown("""<style> [data-testid="stDecoration"] { display: none; } </style>""", unsafe_allow_html=True) #this code removes the red bar at the top but keeps the hamburger menu
  st.markdown("""<style> [data-testid="stAppViewBlockContainer"] { padding-top: 1.5rem; } </style>""", unsafe_allow_html=True) #this removes much of the annoying headroom padding on the main ui, although we can't remove all of it because the loading indicators are actually a solid bar that would obscure the logo (I'm not sure why).

  if fe := ssget("fake_email"):
    ssset("email", fe)
  else:
    if (e := st.experimental_user.email) is None:
      st_print("Your user email is `None`, which implies we are currently running publicly on Streamlit Community Cloud. https://docs.streamlit.io/library/api-reference/personalization/st.experimental_user#community-cloud. This app is configured to function only privately and permissionedly, so we will now exit. Good day.")
      exit_error(34)
    else:
      ssset("email", e)

    # Google identity/sign-in logic, using IAP. From https://cloud.google.com/iap/docs/signed-headers-howto, with modifications. Will set the email to a new value iff it succeeds.
    if iap_jwt := st.context.headers.get("X-Goog-Iap-Jwt-Assertion"):
      try:
        decoded_jwt = id_token.verify_token(iap_jwt, requests.Request(), audience=st.secrets["aud"], certs_url="https://www.gstatic.com/iap/verify/public_key")
        ssset("email", decoded_jwt["email"].split(":")[1])
      except Exception as e: # This pass probably hits if you don't have an aud, you don't have an X-Goog-IAP-JWT-Assertion header (you aren't behind an IAP), or the decode fails (the header is forged or otherwise invalid).
        st_print(e)

    if ssget('email') == 'test@example.com': # In this case, the streamlit app is running "locally", which means everywhere but the streamlit community cloud.
      if "--disable_user_authentication_requirement_DO_NOT_USE_THIS_FLAG_WITH_PUBLIC_INSTANCES_OF_CICERO_ITS_ONLY_FOR_LOCAL_TESTING_USE" in argv:
        pass # The command-line flag we check for here lets you locally test-run the program without an IAP. Do NOT add this flag to any instance of Cicero running publicly, such as the production or development environments. In deployed environments, the other authentication methods are enabled.
      else:
        st_print("Your user email is test@example.com, which implies we are currently running publicly, and not on Streamlit Community Cloud. And (our bespoke) google identity didn't work. https://docs.streamlit.io/library/api-reference/personalization/st.experimental_user#community-cloud. This app is configured to function only privately and permissionedly, so we will now exit. Good day.")
        exit_error(35)

  title_and_loading_columns = st.columns(2)
  with title_and_loading_columns[0]:
    st.image(image="assets/CiceroLogo_Frontend_Cropped_400x107.png", use_column_width=False)
  with title_and_loading_columns[1]:
    loading_message = st.empty()
    loading_message.write("Loading CICERO.  This may take up to a minute...")
  
  with st.sidebar:
    st.write(
      f"You are {'fake-'*bool(ssget('fake_email'))}logged in as {ssget('email')}{admin_str( f" (internally, {st.experimental_user.email})" )}. {admin_str("You are in admin mode.")}"
    )

  #This is the way you set admin mode. However, for the sake of brevity and DRY, the way to *check* admin mode is is_admin() from cicero_shared. You should always use that way.
  ssset('admin_mode', not ssget("admin_mode_disabled") and get_value_of_column_in_table("user_pod", "cicero.ref_tables.user_pods") == "Admin")
  def disable_admin_mode() -> None:
    ssset("admin_mode_disabled", True)

  # Since we use st.navigation explicitly, the default page detection is disabled, even though we may use a pages folder later (although we shouldn't name that folder pages/, purely in order to suppress a warning message about how we shouldn't do that). This is good, because we want to hide some of the pages from non-admin-mode users.
  # There is an icon parameter to st.Page, so we could write eg icon="🗣️", but including the emoji in the titles makes them slightly larger and thus nicer-looking.
  pages = [] #pages visible to the user
  page_access: list[str] = get_list_value_of_column_in_table("page_access", "cicero.ref_tables.user_pods")
  if 'topic_reporting' in page_access:
    pages += [ st.Page("cicero_topic_reporting.py", title="📈 Topic Reporting") ]
  # These next two pages need a url_path because otherwise they have dumb names for implementation reasons.
  if 'chat_with_cicero' in page_access:
    pages += [ st.Page(cicero_chat_main, title="💬 Chat with Cicero", url_path="chat_with_cicero") ]
  if 'chat_with_corpo' in page_access: #the following logic implements how we want people with corpo access to not see the prompter, unless they are admins.
    pages += [ st.Page(lambda: cicero_chat_main("_corporate"), title="💼 Chat with Cicero", url_path="chat_with_cicero_corporate") ]
  elif not is_admin(): #we prevent giving this to admins just because we also add it to admins' view in a second (in order to let admins have everything, but not twice (twice would be a Multiple Pages specified with URL the same error))
    pages += [st.Page("cicero_prompter.py", title="🗣️ Prompter")]
  if is_admin():
    pages += [
      st.Page("cicero_prompter.py", title="🗣️ Prompter"),
      st.Page("cicero_response_lookup.py", title="🔍 Response Lookup"),
      st.Page("cicero_pod_key.py", title="🫛 Pod Key"),
      st.Page("cicero_activity_looker.py", title="👁️ Activity Looker"),
      st.Page("cicero_meddler.py", title="✍️ Meddler"),
      st.Page("cicero_video_brief.py", title="🎬 Video Brief"),
      st.Page("cicero_voice_map_manager.py", title="👄 Voice Map Manager"),
    ]
  st.navigation(pages).run()
  loading_message.empty() # At this point, we no longer need to display a loading message, once we've gotten here and displayed everything above.

  if is_admin(): # Developer information about the app (performance, etc).
    admin_box("Admin Mode Message: the entire session_state", st.session_state)
    with st.sidebar:
      st.caption(f"""Streamlit app memory usage: {psutil.Process(os.getpid()).memory_info().rss // 1024 ** 2} MiB.<br>
        Time to display: {(perf_counter_ns()-nanoseconds_base)/1000/1000/1000} seconds.<br>
        Python version: {platform.python_version()}<br>
        Streamlit version: {st.__version__}<br>
        Cicero version (git HEAD hash) on disk on startup: `{ssget("git_head_hash_on_startup")}`<br>
        Cicero version (git HEAD hash) currently on disk: `{get_git_head_hash()}`<br>
        Base url: {get_base_url()}
      """, unsafe_allow_html=True)
      st.button("disable Admin Mode", on_click=disable_admin_mode, help="Click this button to disable admin mode, allowing you to see and interact with the app as a basic user would. You can refresh the page in your browser to re-enable admin mode.") #this is a callback for streamlit ui update-flow reasons.
      st.text_input("see the page as this user", key="fake_email")
  else: # Disable the profiler element visually, using css, if not in admin mode.
    st.markdown("""<style> [allow="accelerometer; ambient-light-sensor; autoplay; battery; camera; clipboard-write; document-domain; encrypted-media; fullscreen; geolocation; gyroscope; layout-animations; legacy-image-formats; magnetometer; microphone; midi; oversized-images; payment; picture-in-picture; publickey-credentials-get; sync-xhr; usb; vr ; wake-lock; xr-spatial-tracking"] { /*this is an arbitrary way to target the profiler element*/ display: none; } </style>""", unsafe_allow_html=True)

  # Write to the activity log if we need to. These are here for end-user performance/convenience reasons, even though on every other axis this is a bad place for it:
  if alp := sspop("activity_log_payload"):
    print("Writing to log.")
    ensure_existence_of_activity_log()
    sql_call_cacheless(
      # The WTIH clause here basically just does a left join; I just happened to write it in this way.
      # Note that this will implicitly null the user_feedback, as that field is not specified here.
      """WITH tmp(user_pod) AS (SELECT user_pod FROM cicero.ref_tables.user_pods WHERE user_email ilike :user_email) INSERT INTO cicero.default.activity_log
      (timestamp,           user_email, user_pod,                               prompter_or_chatbot,  prompt_sent,  response_given,  model_name,  model_url,  model_parameters,  system_prompt,  base_url,  user_feedback,  user_feedback_satisfied,  used_similarity_search_backup,  hit_readlink_time_limit,  pii_concern,  fec_concern,  winred_concern, voice, account) SELECT
      current_timestamp(), :user_email, COALESCE(tmp.user_pod, 'Pod unknown'), :prompter_or_chatbot, :prompt_sent, :response_given, :model_name, :model_url, :model_parameters, :system_prompt, :base_url, :user_feedback, :user_feedback_satisfied, :used_similarity_search_backup, :hit_readlink_time_limit, :pii_concern, :fec_concern, :winred_concern, :voice, :account
      FROM tmp RIGHT JOIN (SELECT 1) AS dummy ON true -- I don't really know if this is the best way to make the log still get written to if the pod is unknown, but it's the one I found.""",
      alp
    )
    print("Done writing to log.")

  if alu := sspop("activity_log_update"):
    print("Writing good/bad to log.")
    ensure_existence_of_activity_log()
    sql_call_cacheless(
      # Note: we are gambling that the user_pod and timestamp will never be necessary in practice to have in here, because getting them would be inconvenient. Theoretically, an exact replica circumstance could occur, without those disambiguators. But this is so unlikely; it's probably fine.
      "UPDATE cicero.default.activity_log SET user_feedback = :user_feedback WHERE user_email = :user_email AND prompter_or_chatbot = :prompter_or_chatbot AND prompt_sent = :prompt_sent AND response_given = :response_given AND model_name = :model_name AND model_url = :model_url AND model_parameters = :model_parameters AND system_prompt = :system_prompt AND base_url = :base_url AND voice = :voice and account = :account;",
      alu
    )
    print("Done writing update to log.")

  if alu2 := sspop("activity_log_update2"):
    print("Writing good/bad 2 to log.")
    ensure_existence_of_activity_log()
    sql_call_cacheless(
      # Note: we are gambling that the user_pod and timestamp will never be necessary in practice to have in here, because getting them would be inconvenient. Theoretically, an exact replica circumstance could occur, without those disambiguators. But this is so unlikely; it's probably fine.
      "UPDATE cicero.default.activity_log SET user_feedback_satisfied = :user_feedback_satisfied WHERE user_email = :user_email AND prompter_or_chatbot = :prompter_or_chatbot AND prompt_sent = :prompt_sent AND response_given = :response_given AND model_name = :model_name AND model_url = :model_url AND model_parameters = :model_parameters AND system_prompt = :system_prompt AND base_url = :base_url AND voice = :voice and account = :account;",
      alu2
    )
    print("Done writing update 2 to log.")

  print("End of a run.", str(datetime.now(tz=datetime.now().astimezone().tzinfo)) )
