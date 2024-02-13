from time import perf_counter_ns
nanoseconds_base : int = perf_counter_ns()
import streamlit as st
import pandas as pd
import requests
import json
import os, psutil, platform
from databricks import sql # Spooky that this is not the same name as the pypi package databricks-sql-connector, but is the way to refer to the same thing.
from datetime import datetime, date
import faiss
from sentence_transformers import SentenceTransformer # Weird that this is how you reference the sentence-transformers package on pypi, too. Well, whatever.
#COULD: use https://pypi.org/project/streamlit-profiler/ for profiling
from transformers import GenerationConfig

st.set_page_config(layout="wide") # Use wide mode in Cicero, mostly so that results display more of their text by default. #NOTE: "`set_page_config()` can only be called once per app page, and must be called as the first Streamlit command in your script."

if st.experimental_user['email'] is None:
  st.write("Your user email is None, which implies we are currently running publicly on Streamlit Community Cloud. https://docs.streamlit.io/library/api-reference/personalization/st.experimental_user#public-app-on-streamlit-community-cloud. This app is configured to function only privately and permissionedly, so we will now exit. Good day.")
  exit()
email = st.experimental_user['email']
if st.experimental_user['email'] == 'text@example.com': #TODO: we should not rely on this behavior. Which is easy, because we don't currently use it for anything
  pass #The streamlit app is running "locally", which means everywhere but the streamlit community cloud.

# Google sign-in logic
# Taken from Miguel_Hentoux here https://discuss.streamlit.io/t/google-authentication-in-a-streamlit-app/43252/18 , and modified
import google_auth_oauthlib.flow
from googleapiclient.discovery import build

#This part is from BramVanroy https://github.com/streamlit/streamlit/issues/798#issuecomment-1647759949
import urllib.parse
# "WARNING: I found that in multi-page apps, this will always only return the base url and not the sub-page URL with the page appended to the end."
session = st.runtime.get_instance()._session_mgr.list_active_sessions()[0]
redirect_uri = urllib.parse.urlunparse([session.client.request.protocol, session.client.request.host, "", "", "", ""]) # for example, in testing, this value is probably: http://localhost:8501

def auth_flow():
  auth_code = st.query_params.get("code")
  # Use your json credentials from your google auth app. You must place them, adapting their format, in secrets.toml under a heading [google_signin_secrets.installed] (you'll note that everything in the json is in an object with the key "installed", so from that you should be able to figure out the rest.
  flow = google_auth_oauthlib.flow.Flow.from_client_config(
    st.secrets["google_signin_secrets"],
    scopes=["https://www.googleapis.com/auth/userinfo.email", "openid"],
    redirect_uri=redirect_uri,
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
    except Exception as e: #we always get an InvalidGrantError on an F5 if the user was logged-in.
      pass
  if not signed_in:
    authorization_url, state = flow.authorization_url(access_type="offline", include_granted_scopes="true") #ignore the fact that this says the access_type is offline, that's not relevant to our deployment; it's about something different.
    st.link_button("Sign in with Google", authorization_url)

if "google_auth_code" not in st.session_state: #TODO: use cookies to extend this state's lifetime.
  auth_flow()
if "google_auth_code" in st.session_state:
  email = st.session_state["user_info"].get("email")
  st.write(f"Google signed-in as {email}")

developer_mode = email in ["achang@targetedvictory.com", "test@example.com", "abrady@targetedvictory.com", "thall@targetedvictory.com", "afuhrer@targetedvictory.com", "wcarpenter@targetedvictory.com"] and not st.session_state.get("developer_mode_disabled")
def disable_developer_mode() -> None: st.session_state["developer_mode_disabled"] = True

loading_message = st.empty()
loading_message.write("Loading CICERO.  This may take up to a minute...")

databricks_api_token = st.secrets['databricks_api_token']

@st.cache_data()
def load_model_permissions(useremail: str) -> list[str]:
  with sql.connect(server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME"), http_path=os.getenv("DATABRICKS_HTTP_PATH"), access_token=os.getenv("databricks_api_token")) as connection: #These secrets should be in the root level of the .streamlit/secrets.toml
    with connection.cursor() as cursor:
      results = cursor.execute(
        "SELECT DISTINCT modelname FROM models.default.permissions WHERE useremail = %(useremail)s", {'useremail': useremail}
      ).fetchall()
      return [result[0].lower() for result in results]
model_permissions = load_model_permissions(email) #model_permissions is ALL LOWERCASE
if "context" not in model_permissions: #We want everyone to want to have access to default, at least at time of writing this comment.
  model_permissions.insert(0, "Context")
#NOTE: these model secrets have to be in the secrets.toml as, like:
# models.Default = ''
# models.Context = ''
# Or some other way of making a dict in toml
models: dict[str,str] = { k:v for k, v in st.secrets['models'].items() if k.lower() in [m.lower() for m in model_permissions] } #filter for what the actual permissions are for the user.

@st.cache_data() #Necessity demands we do a manual cache of this function's result anyway in the one place we call it, but (for some reason) it seems like our deployed environment is messed up in some way I cannot locally replicate, which causes it to run this function once every five minutes. So, we cache it as well, to prevent waking up our server and costing us money.
def count_from_activity_log_times_used_today(useremail: str = email) -> int: #this goes by whatever the datetime default timezone is because we don't expect the exact boundary to matter much.
  print("count_from_activity_log_times_used_today ACTIVE")
  try: # This can fail if the table doesn't exist (at least not yet, as we create it on insert if it doesn't exist), so it's nice to have a default
    with sql.connect(server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME"), http_path=os.getenv("DATABRICKS_HTTP_PATH"), access_token=os.getenv("databricks_api_token")) as connection: #These secrets should be in the root level of the .streamlit/secrets.toml
      with connection.cursor() as cursor:
        return cursor.execute(
          f"SELECT COUNT(*) FROM main.default.activity_log WHERE useremail = %(useremail)s AND datetime LIKE '{date.today()}%%'",
          {'useremail': useremail}
        ).fetchone()[0]
  except Exception as e:
    print("There was an exception in count_from_activity_log_times_used_today, so I'm just returning a value of 0. Here's the exception:", str(e))
    return 0

def write_to_activity_log_table(datetime: str, useremail: str, promptsent: str, responsegiven: str, modelparams: str) -> int:
  """The most sensical thing for this function to return is the closest thing to a result value that an insert command produces: the .rowcount variable of the cursor, which is "the number of rows that the last .execute*() [...] affected (for DML statements like UPDATE or INSERT)." <https://peps.python.org/pep-0249/#rowcount>. However, that PEP also states that "The attribute is -1 in case no .execute*() has been performed on the cursor or the rowcount of the last operation is cannot be determined by the interface." And the implementation of databricks-sql-connector seems to have taken this liberty to, indeed, always return -1. So this return value is useless."""
  with sql.connect(server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME"), http_path=os.getenv("DATABRICKS_HTTP_PATH"), access_token=os.getenv("databricks_api_token")) as connection: #These should be in the root level of the .streamlit/secrets.toml
    with connection.cursor() as cursor:
      cursor.execute("CREATE TABLE IF NOT EXISTS main.default.activity_log (datetime string, useremail string, promptsent string, responsegiven string, modelparams string)")
      return cursor.execute(
        "INSERT INTO main.default.activity_log VALUES (%(datetime)s, %(useremail)s, %(promptsent)s, %(responsegiven)s, %(modelparams)s)",
        {'datetime': datetime, 'useremail': useremail, 'promptsent': promptsent, 'responsegiven': responsegiven, 'modelparams': modelparams} #this probably could be a kwargs, but I couldn't figure out how to do that neatly the particular way I wanted so whatever, you just have to change this 'signature' four times in this function if you want to change it.
      ).rowcount

if 'use_count' not in st.session_state:
  st.session_state['use_count'] = count_from_activity_log_times_used_today()
use_count_limit = 100 #arbitrary but reasonable choice of limit
if email in ["abrady@targetedvictory.com", "thall@targetedvictory.com" "test@example.com"]: # Give certain users nigh-unlimited uses.
  use_count_limit = 100_000_000
if st.session_state['use_count'] >= use_count_limit:
  st.write(f"You cannot use this service more than {use_count_limit} times a day, and you have reached that limit. Please contact the team if this is in error or if you wish to expand the limit.")
  exit() # When a user hits the limit it completely locks them out of the ui using an error message. This wasn't a requirement, but it seems fine.

bespoke_title_element = '<h1><img src="https://targetedvictory.com/wp-content/uploads/2019/07/favicon.png" alt="💬" style="display:inline-block; height:1em; width:auto;"> CICERO</h1>'
st.markdown(bespoke_title_element, unsafe_allow_html=True)
st.error('REMINDER! Please tag all projects with "optimization" in the LABELS field in Salesforce.')
@st.cache_data()
def load_bios() -> dict[str, str]:
  bios : dict[str, str] = dict(pd.read_csv("Candidate_Bios.csv", index_col="ID").to_dict('split')['data'])
  return bios
bios : dict[str, str] = load_bios()

@st.cache_data()
def load_account_names() -> list[str]:
  return list(pd.read_csv("Client_List.csv")['ACCOUNT_NAME'])
account_names = load_account_names()

@st.cache_data()
def load_headlines(get_all:bool=False, past_days:int=7) -> list[str]:
  try: # This can fail if the table doesn't exist (at least not yet, as we create it on insert if it doesn't exist), so it's nice to have a default
    with sql.connect(server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME"), http_path=os.getenv("DATABRICKS_HTTP_PATH"), access_token=os.getenv("databricks_api_token")) as connection: #These secrets should be in the root level of the .streamlit/secrets.toml
      with connection.cursor() as cursor:
        results = cursor.execute(
          "SELECT DISTINCT headline FROM cicero.default.headline_log" if get_all else
          f"""WITH SortedHeadlines AS (
                SELECT
                    datetime,
                    headline,
                    ROW_NUMBER() OVER (PARTITION BY headline ORDER BY datetime DESC, headline) AS row_num
                FROM
                    cicero.default.headline_log
                )
              SELECT
                headline
              FROM
                SortedHeadlines
              WHERE
                row_num = 1
                AND datetime >= NOW() - INTERVAL {past_days} DAY
              ORDER BY
                datetime DESC, headline;
          """ # The (arbitrary) requirement is that we return results from the last 7 days, and this is the easiest way to do it. Might not be the most performant query, but it works. COULD: review performance, see if there are any alternative queries that could be faster.
        ).fetchall()
        return [result[0] for result in results]
  except Exception as e:
    print("There was an exception in load_headlines, so I'm just returning this. Here's the exception:", str(e))
    return ["There was an exception in load_headlines, so I'm just returning this. Here's the exception: "+str(e)]
headlines : list[str] = load_headlines(get_all=False) #COULD: if we don't need to allow the user this list all the time, we could move this line to the expander, in some kind of `if` statement, possibly a checkbox, to save maybe 2 seconds on app load times. (Unfortunately, the expansion state of the expander is not programmatically available to `if` upon. Also, we do kind of want the user to be able to access this list all the time, without sorting or searching necessarily being in play.)
headlines_overdrive : list[str] = load_headlines(get_all=False, past_days=3)

@st.cache_data()
def sort_headlines_semantically(headlines: list[str], query: str, number_of_results_to_return:int=1) -> list[str]:
  """This does a bunch of gobbledygook no one understands. But the important thing is that it returns to you a function that will return to you the top k news results for a given query."""
  model = SentenceTransformer("BAAI/bge-large-en-v1.5")
  faiss_title_embedding = model.encode(headlines)
  faiss.normalize_L2(faiss_title_embedding)
  # Index1DMap translates search results to IDs: https://faiss.ai/cpp_api/file/IndexIDMap_8h.html#_CPPv4I0EN5faiss18IndexIDMapTemplateE ; The IndexFlatIP below builds index.
  index_content = faiss.IndexIDMap(faiss.IndexFlatIP(len(faiss_title_embedding[0])))
  index_content.add_with_ids(faiss_title_embedding, range(len(headlines)))
  query_vector = model.encode([query])
  faiss.normalize_L2(query_vector)
  top_results = index_content.search(query_vector, number_of_results_to_return)
  ids = top_results[1][0].tolist()
  similarities = top_results[0][0].tolist() # COULD: return this, for whatever we want.
  results = [headlines[i] for i in ids]
  return results

#Make default state, and other presets, so we can manage presets and resets.
# Ah, finally, I've figured out how you're actually supposed to do it: https://docs.streamlit.io/library/advanced-features/button-behavior-and-examples#option-1-use-a-key-for-the-button-and-put-the-logic-before-the-widget
#IMPORTANT: these field names are the same field names as what we eventually submit. HOWEVER, these are just the default values, and are only used for that, and are stored in this particular data structure, and do not overwrite the other variables of the same names that represent the returned values.
presets: dict[ str, dict[str, float|int|bool|str|list[str]|None] ] = {
  "default": {
    "temperature": 0.7,
    "target_charcount_min": 80,
    "target_charcount_max": 160,
    "num_beams" : 1,
    "top_k" : 50,
    "top_p" : 1.0,
    "repetition_penalty" : 1.2,
    "no_repeat_ngram_size" : 4,
    "num_return_sequences" : 5,
    "early_stopping" : False,
    "do_sample" : True,
    "output_scores" : False,
    "model": "Context",
    "account" : None,
    "ask_type": "Fundraising Hard Ask",
    "tone" : [],
    "topics" : [],
    "additional_topics" : "",
    "semantic_query": "",
    "headline": None,
    "overdrive": False,
    "exact_match": False
  },
}

def set_ui_to_preset(preset_name: str) -> None:
  preset = presets[preset_name]
  for i in preset: #this iterates over the keys
    st.session_state[i] = preset[i]

if not st.session_state.get("initted"):
  set_ui_to_preset("default")
  st.session_state["initted"] = True
  st.rerun() #STREAMLIT-BUG-WORKAROUND: this rerun actually has nothing to do with initing, it's just convenient to do here, since we need to do it exactly once, on app startup. It prevents the expander from experiencing a streamlit bug (<https://github.com/streamlit/streamlit/issues/2360>) that is only present in the initial run state. Anyway, this rerun is really fast and breaks nothing (except the developer mode initial performance timer readout, which is now gone) so it's a good workaround.

login_activity_counter_container = st.container()

if st.button("Reset", help="Resets the UI elements to their default values. This button will also trigger cached data like the Candidate Bios and the news RSS feed to refresh. You can also just press F5 to refresh the page."):
  st.cache_data.clear()
  st.session_state["headline_search_function"] = None
  set_ui_to_preset("default")

def send(model_uri: str, databricks_token: str, data: pd.DataFrame) -> list[str]:
  headers = {
    "Authorization": f"Bearer {databricks_token}",
    "Content-Type": "application/json",
  }
  # As we were flailing around trying to get the model to work, we made the parameter format logic needlessly complicated.
  ds_dict = {'dataframe_split': data.to_dict(orient='split')}
  data_json = json.dumps(ds_dict, allow_nan=True)

  response = requests.request(method='POST', headers=headers, url=model_uri, data=data_json)
  if response.status_code == 504:
    return send(model_uri, databricks_token, data) #we recursively call this until the machine wakes up.
  elif response.status_code == 404 and response.json()["error_code"] == "RESOURCE_DOES_NOT_EXIST":
    raise Exception("Encountered 404 error \"RESOURCE_DOES_NOT_EXIST\" when trying to query the model. This usually means the model endpoint has been moved. Please contact the team in charge of model serving to rectify the situation.")
  elif response.status_code != 200:
    if response.json()["error_code"] == "BAD_REQUEST":
      raise Exception(response.json()["message"])
    else:
      raise Exception(f"Request failed with status {response.status_code}, {response.text}")
  return response.json()["predictions"][0]["0"]

tone_indictators_sorted = ["Urgency", "Agency", "Exclusivity"]

def sortedUAE(unsorted_tones: list[str]) -> list[str]:
  """For some reason (mnemonic?) the canonical ordering of these tone tags is Urgency Agency Exclusivity. They never appear in any other order, although they do appear in every subset. Anyway, this function implements that ordering, regardless of the order the user selected them."""
  sorted_tones = []
  for indicator in tone_indictators_sorted:
    if indicator in unsorted_tones: sorted_tones.append(indicator)
  return sorted_tones

def list_to_bracketeds_string(l: list[str]) -> str:
  s = ""
  is_first_item = True
  for i in l:
    s += " " if not is_first_item else "" #malarkey to space only between bracketeds, not before or after
    is_first_item = False
    s += ("["+i.strip().replace(" ", "_")+"]")
  return s

# setting default values for advanced parameters for our non-developer end-user
num_beams=1
top_k=50
top_p=1.0
repetition_penalty=1.2
no_repeat_ngram_size=4
num_return_sequences=5
early_stopping=False
do_sample=True
output_scores=False

def only_those_strings_of_the_list_that_contain_the_given_substring_case_insensitively(l: list[str], s: str) -> list[str]: return [s for s in l if s.lower().find(semantic_query.lower()) != -1]

#For technical reasons (various parts of it update when other parts of it are changed, iirc) this can't go within the st.form

with st.expander(r"$\textsf{\Large FOX NEWS HEADLINES}$"if developer_mode else r"$\textsf{\Large NEWS HEADLINES}$"):
  semantic_query = st.text_input("Semantic Search  \n*Returns headlines matching the meaning of the search terms, not necessarily exact matches. Must hit Enter.*  \n*Example: searching for `border' will also return headlines for 'immigration', 'migrants', 'border crossings', 'deportation', etc.*", key="semantic_query")
  col1, col2 = st.columns(2) #this column setup arguably looks worse than the default, and we've already blown the vertical-single-screen idea when you open this expander, so maybe you don't have to keep this formatting idk.
  with col1:
    exact_match: bool = st.checkbox("Use exact match instead of semantic match.", key="exact_match") #an option for persnickety people ohoho
  with col2:
    overdrive: bool = st.checkbox("Only search headlines from the last 3 days.", key="overdrive")
  h = headlines if not overdrive else headlines_overdrive
  if semantic_query:
    if exact_match:
      headlines_sorted = only_those_strings_of_the_list_that_contain_the_given_substring_case_insensitively(h, semantic_query)
    else:
      headlines_sorted = sort_headlines_semantically(h, semantic_query, 10) # The limit of 10 is arbitrary. No need to let the user change it.
  else:
    headlines_sorted = h # I forget if this is actually sorted in any way by default. Possibly date?
  headline = st.selectbox("Selected headlines will be added to your prompt below.", [""]+list(headlines_sorted), key="headline") #STREAMLIT-BUG-WORKAROUND: see other [""] STREAMLIT-BUG-WORKAROUND in file.

st.text("") # Just for vertical spacing.

with st.form('query_builder'):
  with st.sidebar:
    st.header("Settings")
    temperature : float = st.slider("Output Variance:", min_value=0.0, max_value=1.0, key="temperature") #temperature: slider between 0 and 1, defaults to 0.7, float
    #character count max, min: int, cannot be negative or 0, starts at 40. floor divide by 4 to get token count to pass to model:
    target_charcount_min = st.number_input("Min Target Characters:", min_value=40, format='%d', step=1, key="target_charcount_min")
    target_charcount_max = st.number_input("Max Target Characters:", min_value=40, format='%d', step=1, key="target_charcount_max")
    if developer_mode:
      with st.expander("Advanced Parameters"):
        num_beams = int( st.number_input("num_beams:", min_value=1, format='%d', step=1, key="num_beams", help="Number of beams for beam search. 1 means no beam search. Beam search is a particular strategy for generating text that the model can elect to use or not use. It can use more or fewer beams in the beam search, as well. More beams basically means it considers more candidate possibilities.") )
        top_k = int( st.number_input("top_k:", min_value=1, format='%d', step=1, key="top_k" , help="The number of highest probability vocabulary tokens to keep for top-k-filtering. In other words: how many likely words the model will consider."))
        top_p = st.number_input("top_p:", min_value=0.0, format='%f', key="top_p" , help="A decimal number, not merely an integer. If set to < 1, only the smallest set of most probable tokens with probabilities that add up to top_p or higher are kept for generation. In other words: if you reduce this number below 1, the model will consider fewer possibilities.")
        repetition_penalty = st.number_input("repetition_penalty:", min_value=1.0, max_value=2.0, format='%f', key="repetition_penalty" , help="A decimal number, not merely an integer. The parameter for repetition penalty. 1.0 means no penalty. In other words: if you increase this parameter, the model will be less likely to repeat itself.")
        no_repeat_ngram_size = int( st.number_input("no_repeat_ngram_size:", min_value=0, max_value=10, format='%d', step=1, key="no_repeat_ngram_size" , help="If set to > 0, all ngrams (essentially, continuous sequences of words or word-parts) of that size can only occur once. In other words: if you set this parameter to a number greater than 0, any string of words can only occur in the output at most that many times.") )
        num_return_sequences = int( st.number_input("num_return_sequences:", min_value=1, max_value=10, format='%d', step=1, key="num_return_sequences" , help="The number of independently computed returned sequences for each element in the batch. In other words: how many responses you want the model to generate.") )
        early_stopping = st.checkbox("early_stopping", key="early_stopping" , help="Controls the stopping condition for beam-based methods, like beam-search. It accepts the following values: True, where the generation stops as soon as there are num_beams complete candidates; False, where an heuristic is applied and the generation stops when is it very unlikely to find better candidates; \"never\", where the beam search procedure only stops when there cannot be better candidates (canonical beam search algorithm). In other words: if the model is using beam search (see num_beams, above), then if this box is checked the model will spend less time trying to improve its beams after it generates them. If num_beams = 1, this checkbox does nothing either way. There is no way to select \"never\" using this checkbox, as that setting is just a waste of time.")
        do_sample = st.checkbox("do_sample", key="do_sample" , help="Whether or not to use sampling ; use greedy decoding otherwise. These are two different strategies the model can use to generate text. Greedy is probably much worse, and you should probably always keep this box checked.")
        output_scores = st.checkbox("output_scores", key="output_scores" , help="Whether or not to return the prediction scores. See scores under returned tensors for more details. In other words: This will not only give you back responses, like normal, it will also tell you how likely the model thinks the response is. Usually useless, and there's probably no need to check this box.")
  model_name = str( st.selectbox(r"$\textsf{\Large COPYWRITING MODEL}$", models, key="model") )
  model_uri = models[model_name]
  account = st.selectbox("Account (required)", [""]+list(account_names), key="account" ) #STREAMLIT-BUG-WORKAROUND: For some reason, in the current version of streamlit, st.selectbox ends up returning the first value if the index has value is set to None via the key in the session_state, which is a bug (<https://github.com/streamlit/streamlit/issues/7649>), but anyway we work around it using this ridiculous workaround. This does leave a first blank option in there. But whatever.
  ask_type = str( st.selectbox("Ask Type", ["Fundraising Hard Ask", "Fundraising Medium Ask", "Fundraising Soft Ask", "List Building"], key="ask_type") )
  topics = st.multiselect("Topics", ["Announce", "Bio", "Border", "China", "Contest", "Control", "Covid", "Crime", "DC", "Debate", "Dems", "Election", "GOP", "GovOverreach", "Judiciary", "Match", "Merch", "Military", "Opponents", "Raid", "Religion", "Roe", "Runoff", "Schools", "Second_Amd", "State_of_the_Race", "Trump"], key="topics" )
  additional_topics = [x for x in st.text_input("Additional Topics (examples: Biden, survey, deadline)", key="additional_topics" ).split(",") if x.strip()] # The list comprehension is to filter out empty strings on split, because otherwise this fails to make a truly empty list in the default case, instead having a list with an empty string in, because split changes its behavior when you give it arguments. Anyway, this also filters out trailing comma edge-cases and such.
  tone = st.multiselect("Tone", tone_indictators_sorted, key="tone")
  generate_button = st.form_submit_button("Submit")

loading_message.empty() # At this point, we no longer need to display a loading message, once we've gotten here and displayed everything above.

#Composition and sending a request:
did_a_query = False
if generate_button:
  if account:
    did_a_query = True
    st.session_state['use_count']+=1 #this is just an optimization for the front-end display of the query count
    st.session_state['human-facing_prompt'] = (
      ((bios[account]+"\n\n") if "Bio" in topics and account in bios else "") +
      "Write a "+ask_type.lower()+
      " text for "+account+
      " about: "+list_to_bracketeds_string(topics+additional_topics or ["No_Hook"])+
      ( "" if not tone else " emphasizing "+ list_to_bracketeds_string(sortedUAE(tone)) ) +
      (" {"+headline+"} " if headline else "")
    )
    prompt = "<|startoftext|> "+st.session_state['human-facing_prompt']+" <|body|>"
    dict_prompt = {"prompt": [prompt],
                    "temperature": [temperature],
                    "max_new_tokens": [int(target_charcount_max) // 4],
                    "min_new_tokens": [int(target_charcount_min) // 4],
                    "num_beams": [num_beams],
                    "top_k": [top_k],
                    "top_p": [top_p],
                    "repetition_penalty": [repetition_penalty],
                    "no_repeat_ngram_size": [no_repeat_ngram_size],
                    "num_return_sequences": [num_return_sequences],
                    "early_stopping": [early_stopping],
                    "do_sample": [do_sample],
                    "output_scores": [output_scores]
                  }
    unpsycho_dict_prompt = {k:v[0] for (k,v) in dict_prompt.items()}
    try:
      GenerationConfig(**unpsycho_dict_prompt)# This validates the parameters, throwing an exception that displays to the user and explains the problem if the parameters are wrong.
      df_prompt = pd.DataFrame(dict_prompt)
      outputs = send(model_uri, databricks_api_token, df_prompt)
      st.session_state['outputs_df'] = pd.DataFrame(outputs, columns=["Model outputs (double click any output to expand it)"]) #Styling this doesn't seem to work, for some reason. Well, whatever.
      if 'history' not in st.session_state: st.session_state['history'] = []
      st.session_state['history'] += outputs
      st.session_state['character_counts_caption'] = "Character counts: "+str([len(o) for o in outputs])
    except Exception as e:
      st.error(e)
      did_a_query = False
  else:
    st.error("***No account name is selected, so I can't send the request!***")

# The idea is for these output elements to persist after one query button, until overwritten by the results of the next query.
if 'human-facing_prompt' in st.session_state: st.caption(st.session_state['human-facing_prompt'])
st.error("WARNING! Outputs have not been fact checked. CICERO is not responsible for inaccuracies in deployed copy. Please check all *names*, *places*, *counts*, *times*, *events*, and *titles* (esp. military titles) for accuracy.  \nAll numbers included in outputs are suggestions only and should be updated. They are NOT analytically optimized to increase conversions (yet) and are based solely on frequency in past copy.", icon="⚠️")
if 'outputs_df' in st.session_state: st.dataframe(st.session_state['outputs_df'], hide_index=True, use_container_width=True)
if 'character_counts_caption' in st.session_state: st.caption(st.session_state['character_counts_caption'])

with st.sidebar: #The history display includes a result of the logic of the script, that has to be updated in the middle of the script where the button press is (when the button is in fact pressed), so the code to display it has to be after all the logic of the script or else it will lag behind the actual state of the history by one time step.
  st.header("History of replies:")
  if 'history' not in st.session_state: st.session_state['history'] = []
  st.dataframe( pd.DataFrame(reversed( st.session_state['history'] ),columns=(["Outputs"])), hide_index=True, use_container_width=True)
  #These stats are unrelated to the concept of history, but for formatting reasons it works best here:
  if developer_mode:
    st.caption(f"""Streamlit app memory usage: {psutil.Process(os.getpid()).memory_info().rss // 1024 ** 2} MiB.<br>
Time to display: {(perf_counter_ns()-nanoseconds_base)/1000/1000/1000} seconds.<br>
Python version: {platform.python_version()}""", unsafe_allow_html=True)
    st.button("disable developer mode", on_click=disable_developer_mode, help="Click this button to disable developer mode, allowing you to see and interact with the app as a basic user would. You can refresh the page in your browser to re-enable developer mode.") #this is a callback for streamlit ui update-flow reasons.

login_activity_counter_container.write( f"You are logged in as {email} . You have queried {st.session_state['use_count']} {'time' if st.session_state['use_count'] == 1 else 'times'} today, out of a limit of {use_count_limit}."+(" You are in developer mode." if developer_mode else "") )

#activity logging takes a bit, so I've put it last to preserve immediate-feeling performance and responses for the user making a query
if did_a_query:
  dict_prompt.pop('prompt')
  no_prompt_dict_str = str(dict_prompt)
  write_to_activity_log_table(datetime=str(datetime.now()), useremail=email, promptsent=prompt, responsegiven=json.dumps(outputs), modelparams=no_prompt_dict_str)

# from streamlit.components.v1 import html
# html('<!--<script>//you can include arbitrary html and javascript this way</script>-->')
