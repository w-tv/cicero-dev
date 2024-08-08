#!/usr/bin/env -S streamlit run
"""If something is used in more than one cicero file, typically put it in this file and import it into the other files.
It's useless to run this stand-alone. But I guess I won't stop you."""

from databricks import sql # Spooky that this is not the same name as the pypi package databricks-sql-connector, but is the way to refer to the same thing.
from databricks.sql.types import Row as Row
import streamlit as st
from streamlit import runtime
from typing import Any, NoReturn, TypedDict, TypeVar, Sequence
import urllib.parse

def ssget(string_to_get_from_streamlit_session_state: str, *args: Any) -> Any | None:
  """ .get() all Y-combinatorally. This function repeatedly retrieves things from things using `.get()` . Starting with the first argument from st.session_state, and then all the subsequent args from the first. This loses type-safety, in a way, since it just returns Any, but st.session_state already didn't have type-safety (TODO: figure out how to TypedDict the session_state? Seems impossible.) because it always just returns `Any | None`. This function also returns `Any | None`. However, long get chains on things taken from session_state like `st.session_state.get("chat").get(streamlit_key_suffix)` get you errors like `error: Item "None" of "Any | None" has no attribute "get"  [union-attr]` — and quite likely so, because that could give you a type error at runtime! You also can't do the ol' `if st.session_state.get("messages") and st.session_state.get("messages").get(streamlit_key_suffix)` "shortcut"-`and` trick, because there might be side-effects between the first and second call of the function. So you'd have to do something crazy like `if m := st.session_state.get("messages") and m.get(streamlit_key_suffix)` (actually, that leads to a type error `error: Name "m" is used before definition  [used-before-def]`). Or break up the clauses or use a variable. Or, you can simply call `get("messages", streamlit_key_suffix)` for the same effect.

  Much like .get(), which is better than . and [], this function will never throw an error (unless you make it visit an object that has no .get() method but is not None), only ever return None if something is not found. Note that there is no indication of where in the chain the None is coming from.

  You may also use the base case of get as a simple shorthand for the longer st.session_state.get, which all will agree is much longer to type.

  "Y-combinatorally" refers to https://en.wikipedia.org/wiki/Fixed-point_combinator#Y_combinator , which is not actually important to understand. It's just the concept of a loop, really. Really this function is more like a fixed-point operator with limited depth than anything having to do with the lambda calculus. But whatever.

  get is a particular type of safe navigation operator, which you can read the wikipedia page about. https://en.wikipedia.org/wiki/Safe_navigation_operator

  Needing this whole thing is very silly. But that's the Python way!"""
  x = st.session_state.get(string_to_get_from_streamlit_session_state)
  if x is None:
    return None
  else:
    for a in args:
      x = x.get(a)
      if x is None:
        return None
  return x

def ssset(string_to_get_from_streamlit_session_state: str, *additional_args_ending_with_payload: Any) -> None:
  """Like ssget, but setting a value. Note that this means that if a None is encountered along the way, it will be replaced with a {}; much like the behavior of a defaultdict, in a way. Also note that payload must be given as a keyword argument, like payload=whatever, because of how variadic arguments work in python."""
  a = list(additional_args_ending_with_payload)
  if len(a) == 1: # I'm fairly certain this is redundant given the general case handled below. But it's nice to spell things out sometimes.
    st.session_state[string_to_get_from_streamlit_session_state] = a[0]
  else:
    x = st.session_state
    s = string_to_get_from_streamlit_session_state
    while len(a) >= 2:
      if x[s] is None:
        x[s] = {}
      # Set up the arguments for the next iteraton of the loop:
      x = x[s]
      s = a.pop(0)
    x[s] = a.pop(0)

def st_print(*args: Any) -> None:
  print(*args)
  st.write(*args)

def get_base_url() -> str:
  """Gets the url where the streamlit app is currently running, not including any page paths underneath. In testing, for example, this value is probably http://localhost:8501 . This function is from BramVanroy https://github.com/streamlit/streamlit/issues/798#issuecomment-1647759949 , with modifications. “WARNING: I found that in multi-page apps, this will always only return the base url and not the sub-page URL with the page appended to the end.”"""
  try:
    session = runtime.get_instance()._session_mgr.list_active_sessions()[0] # There's occasionally a harmless IndexError: list index out of range from this line of code on Streamlit Community Cloud, which I'd like to suppress via this try-catch for the convenience of the reader of the logs.
    r = session.client.request #type: ignore[attr-defined] #MYPY-BUG-WORKAROUND mypy has various bugs about abstract classes and dataclasses, possibly this one: https://github.com/python/mypy/issues/16613
    if r.protocol == "http" and not r.host.startswith("localhost:"): # STREAMLIT-BUG-WORKAROUND (?) for some reason even when we're in an https connection the r.protocol is http. https://github.com/streamlit/streamlit/issues/8600
      r.protocol = "https"
    return str(
      urllib.parse.urlunparse([r.protocol, r.host, "", "", "", ""])# see also: https://github.com/python/mypy/issues/17082
    )
  except IndexError as e:
    return str(e)

def consul_show(x: Any) -> None:
  """Show some debug-like information in the sidebar. Often best used with f"{foo=}" in the calling code, which will become the name and also the value of the variable, such as foo=2 (naturally, this must be done at the calling site (I assume))."""
  if st.session_state.get("developer_mode"):
    st.sidebar.caption(f"Developer (“Consul”) mode diagnostic: {x}")

def exit_error(exit_code: int) -> NoReturn:
  st.write("*Ego vero consisto. Accede, veterane, et, si hoc saltim potes recte facere, incide cervicem.*")
  exit(exit_code)

@st.dialog("Database error")
def die_with_database_error_popup(e_args: tuple[Any, ...]) -> NoReturn:
  print("Database error", e_args)
  st.write("There was a database error, and the application could not continue. Sorry.")
  st.code(e_args)
  exit_error(4)

def popup(title: str, body: str) -> None:
  """This makes a simple modal dialog box in streamlit. It eschews the advanced functionality of the dialog, which usually allows arbitrary code to run. But we haven't needed that so far. (It could probably be done by allowing body to be a callable.)"""
  @st.dialog(title)
  def _() -> None:
    st.write(body)
    st.caption("Press enter or click the ❌︎ in the upper-right corner to close this message.")
  _()


def ensure_existence_of_activity_log() -> None:
  """Run this code before accessing the activity log. If the activity log doesn't exist, this function call will create it.
  Note that if the table exists, this sql call will not check if it has the right columns (names or types), unfortunately."
  Note that this table uses a real timestamp datatype. You can `SET TIME ZONE "US/Eastern";` in sql to get them to output as strings in US Eastern time, instead of the default UTC."""
  sql_call("CREATE TABLE IF NOT EXISTS cicero.default.activity_log (timestamp timestamp, user_email string, user_pod string, prompter_or_chatbot string, prompt_sent string, response_given string, model_name string, model_url string, model_parameters string, system_prompt string, base_url string, user_feedback string)")

@st.cache_data(show_spinner=False)
def sql_call(query: str, sql_params_dict:dict[str, Any]|None=None) -> list[Row]:
  """This is a wrapper function for sql_call_cacheless that *is* cached. See that other function for more information about the actual functionality."""
  return sql_call_cacheless(query, sql_params_dict)

def sql_call_cacheless(query: str, sql_params_dict:dict[str, Any]|None=None) -> list[Row]:
  """Make a call to the database, returning a list of Rows. The returned values within the Rows are usually str, but occasionally might be int (as when getting the count) or float or perhaps any of these https://docs.databricks.com/en/dev-tools/python-sql-connector.html#type-conversions"""
  # COULD: (but probably won't) there is a minor problem where we'd like to ensure that a query to a table x only occurs after a call to CREATE TABLE IF NOT EXISTS x (parameters of x). Technically, we could ensure this by creating a new function ensure_table(table_name, table_types) which then returns an TableEnsurance object, which then must be passed in as a parameter to SQL call. However, then we would want to check if it were the correct table (and possibly the right parameter types) which would greatly complicate the function signature of sql_call, because we'd have to pass the table name(s) in too, and then string-replace them into the query(?). So, doesn't seem worth it.
  try:
    with sql.connect(server_hostname=st.secrets["DATABRICKS_HOST"], http_path=st.secrets["DATABRICKS_HTTP_PATH"], access_token=st.secrets["DATABRICKS_TOKEN"]) as connection: #These secrets should be in the root level of the .streamlit/secrets.toml
      with connection.cursor() as cursor:
        return cursor.execute(query, sql_params_dict).fetchall()
  except Exception as e:
    die_with_database_error_popup(e.args)

@st.cache_data(show_spinner=False)
def load_account_names() -> list[str]:
  return [row[0] for row in sql_call("SELECT DISTINCT rollup_name FROM cicero.ref_tables.ref_account_rollup WHERE visible_frontend ORDER BY rollup_name ASC")]

def assert_always(x: Any, message_to_assert: str|None = None) -> None | NoReturn: #COULD: currently this enjoys no type-narrowing properties, alas.
  """This function is equivalent to assert, but cannot be disabled by -O"""
  if not x:
    raise AssertionError(message_to_assert or x)
  return None

T = TypeVar('T')
def typesafe_selectbox(label: str, options: Sequence[T], default: T|None = None, **kwargs: Any) -> T:
  """Call `st.selectbox` but don't pollute your type with `None` in the process;
  if the selectbox would return `None`, return the value passed in as `default`.
  If `default` is `None` (eg: not passed in), the value of `options[0]` is used.
  The value of `default` (unless `None`) must be in `options`, on pain of runtime error;
  and, furthermore, `options` must not be empty.

  `options` is also a `Sequence` type rather than the broader `Iterable`
  to ensure it isn't an exhaustible iterator that would be harmed by a call to `.index()`

  `default` is named in analogy to a parameter in `st.multiselect`.
  But there are other widgets, like `st.text_input`, that have an analogous parameter named `value` 🤷.

  All arguments, including kwargs, are passed on to st.selectbox, either directly or indirectly.
  It's not clear to me if there's a better & concise way to do the type signature of kwargs here.

  Note that if you use st.session_state to set the value of the key of the selectbox, that takes priority over the `default` argument.
  However, if you set the value of said key to `None`, this function will still return `options[0]`."""
  #STREAMLIT-BUG-WORKAROUND: every time I use this instead of st.selectbox I think this is technically working around a bug in streamlit, although it's a typing bug and might be impossible for them to fix: https://github.com/streamlit/streamlit/issues/8717
  i = 0 if default is None else options.index(default)
  x = st.selectbox(label, options, index=i, **kwargs)
  return x if x is not None else options[i]

# This is the 'big' of topics, the authoritative record of various facts and mappings about topics.
Topics_Big_Payload = TypedDict("Topics_Big_Payload", {'color': str, 'internal name': str, 'show in prompter?': bool})
topics_big: dict[str, Topics_Big_Payload] = {
  'All': {'color': '#61A5A2', 'internal name': 'all', 'show in prompter?': False},
  "’murica": {'color': '#F0D0E8', 'internal name': 'murica', 'show in prompter?': True}, #for SQL syntax reasons, this has to be a typographic apostrophe instead of a straight apostrophe. (’ instead of ')
  '2A': {'color': '#6B747D', 'internal name': 'sec_amend', 'show in prompter?': True},
  'America Wrong Track': {'color': '#658AB2', 'internal name': 'america_wrong_track', 'show in prompter?': True},
  'Announcement': {'color': '#FDB0A1', 'internal name': 'announcement', 'show in prompter?': True},
  'Biden Impeachment': {'color': '#F58271', 'internal name': 'biden_impeach', 'show in prompter?': True},
  'Big Tech': {'color': '#EF6862', 'internal name': 'big_tech', 'show in prompter?': True},
  'Bio': {'color': '#FFF', 'internal name': 'bio', 'show in prompter?': True},
  'Birthday': {'color': '#E24F59', 'internal name': 'birthday', 'show in prompter?': True},
  'Border': {'color': '#CF3D54', 'internal name': 'border', 'show in prompter?': True},
  'Breaking News': {'color': '#B93154', 'internal name': 'breaking_news', 'show in prompter?': True},
  'Campaign Message / Memo': {'color': '#FFF021', 'internal name': 'campaign_msg', 'show in prompter?': True},
  'China': {'color': '#F5E721', 'internal name': 'china', 'show in prompter?': True},
  'Climate Change': {'color': '#000', 'internal name': 'climate_change', 'show in prompter?': True},
  'Communism / Socialism': {'color': '#E3D321', 'internal name': 'commie', 'show in prompter?': True},
  'Contest': {'color': '#DBC628', 'internal name': 'contest', 'show in prompter?': True},
  'Control of Congress': {'color': '#CBB828', 'internal name': 'control_of_congress', 'show in prompter?': True},
  'Control of WH': {'color': '#C7BC42', 'internal name': 'control_of_wh', 'show in prompter?': True},
  'Covid': {'color': '#A69F56', 'internal name': 'covid', 'show in prompter?': True},
  'Crime': {'color': '#A6A633', 'internal name': 'crime', 'show in prompter?': True},
  'DC Statehood': {'color': '#BDE4B2', 'internal name': 'dc_state', 'show in prompter?': True},
  'Deadline': {'color': '#85C37B', 'internal name': 'deadline', 'show in prompter?': True},
  'Deep State / Corruption': {'color': '#5CA065', 'internal name': 'deep_state', 'show in prompter?': True},
  'Dems': {'color': '#407D56', 'internal name': 'dems', 'show in prompter?': True},
  'Donald Trump': {'color': '#F49D70', 'internal name': 't_djt', 'show in prompter?': True},
  'Education': {'color': '#ABD1E9', 'internal name': 'education', 'show in prompter?': True},
  'Election Integrity': {'color': '#95BFDD', 'internal name': 'election_integrity', 'show in prompter?': True},
  'Endorsement for Principal': {'color': '#888', 'internal name': 'endorse_for_principal', 'show in prompter?': True},
  'Endorsement from Donor': {'color': '#83AECF', 'internal name': 'endorse_from_donor', 'show in prompter?': True},
  'Endorsement from Principal': {'color': '#729DC2', 'internal name': 'endorse_from_principal', 'show in prompter?': True},
  'Energy / Oil': {'color': '#628CB4', 'internal name': 'energy', 'show in prompter?': True},
  'Event Debate': {'color': '#547DA4', 'internal name': 'event_debate', 'show in prompter?': True},
  'Event Speech / Rally': {'color': '#466D93', 'internal name': 'event_speech', 'show in prompter?': True},
  'Faith': {'color': '#4F60C7', 'internal name': 'faith', 'show in prompter?': True},
  'GA Runoff': {'color': '#444', 'internal name': 'ga_runoff', 'show in prompter?': True},
  'GOP': {'color': '#BBB', 'internal name': 'gop', 'show in prompter?': True},
  'Gender': {'color': '#6B55DB', 'internal name': 'gender', 'show in prompter?': True},
  'Hamas': {'color': '#8D4EE6', 'internal name': 'hamas', 'show in prompter?': True},
  'Iran': {'color': '#A547F6', 'internal name': 'iran', 'show in prompter?': True},
  'Israel': {'color': '#C839F0', 'internal name': 'israel', 'show in prompter?': True},
  'Joe Biden': {'color': '#FB9A86', 'internal name': 'biden', 'show in prompter?': True},
  'Kamala Harris': {'color': '#FB9A87', 'internal name': 'kamala', 'show in prompter?': True},
  'Kimberly Cheatle': {'color': '#FB9A88', 'internal name': 'kimberly_cheatle', 'show in prompter?': True},
  'Matching': {'color': '#916990', 'internal name': 'matching', 'show in prompter?': True},
  'Media Conservative': {'color': '#DBC921', 'internal name': 'con_media', 'show in prompter?': True},
  'Media Mainstream': {'color': '#8D648A', 'internal name': 'main_media', 'show in prompter?': True},
  'Membership': {'color': '#966F96', 'internal name': 'membership', 'show in prompter?': True},
  'Merch Book': {'color': '#B8A', 'internal name': 'merch_book', 'show in prompter?': True},
  'Merch Koozie': {'color': '#B8F', 'internal name': 'merch_koozie', 'show in prompter?': True},
  'Merch Mug': {'color': '#B587AA', 'internal name': 'merch_mug', 'show in prompter?': True},
  'Merch Ornament': {'color': '#BAA', 'internal name': 'merch_ornament', 'show in prompter?': True},
  'Merch Shirt': {'color': '#D8A', 'internal name': 'merch_shirt', 'show in prompter?': True},
  'Merch Sticker': {'color': '#D1A4C1', 'internal name': 'merch_sticker', 'show in prompter?': True},
  'Merch Wrapping Paper': {'color': '#D8F', 'internal name': 'merch_wrapping_paper', 'show in prompter?': True},
  'Military': {'color': '#E4BCD8', 'internal name': 'military', 'show in prompter?': True},
  'National Security': {'color': '#CDCFCE', 'internal name': 'nat_sec', 'show in prompter?': True},
  'Non-Trump MAGA': {'color': '#BFC2C2', 'internal name': 'non_trump_maga', 'show in prompter?': True},
  'North Korea': {'color': '#DADADA', 'internal name': 'n_korea', 'show in prompter?': True},
  'Parental Rights': {'color': '#ABA', 'internal name': 'parental_rights', 'show in prompter?': True},
  'Pro-Life': {'color': '#A5ABAD', 'internal name': 'pro_life', 'show in prompter?': True},
  'Pro-Trump': {'color': '#CF693F', 'internal name': 't_pro', 'show in prompter?': True},
  'Race Update': {'color': '#97A0A4', 'internal name': 'race_update', 'show in prompter?': True},
  'Radical DAs / Judges': {'color': '#8B959A', 'internal name': 'radical_judge', 'show in prompter?': True},
  'Russia': {'color': '#7F8A91', 'internal name': 'russia', 'show in prompter?': True},
  'SCOTUS': {'color': '#757E88', 'internal name': 'scotus', 'show in prompter?': True},
  'State of the Union': {'color': '#FF0', 'internal name': 'sotu', 'show in prompter?': True},
  'Swamp': {'color': '#616873', 'internal name': 'swamp', 'show in prompter?': True},
  'Taxes / Economy': {'color': '#C2E1F3', 'internal name': 'economy', 'show in prompter?': True},
  'Trump America First': {'color': '#F9BD74', 'internal name': 't_af', 'show in prompter?': False},
  'Trump Arrest': {'color': '#F6AB57', 'internal name': 't_arrest', 'show in prompter?': True},
  'Trump Contest': {'color': '#F49648', 'internal name': 't_contest', 'show in prompter?': False},
  'Trump MAGA': {'color': '#EF823D', 'internal name': 't_maga', 'show in prompter?': False},
  'Trump Mar-a-Lago Raid': {'color': '#E1743D', 'internal name': 't_mal_raid', 'show in prompter?': False},
  'Trump Supporter': {'color': '#BD6040', 'internal name': 't_supporter', 'show in prompter?': False},
  'Trump Witchhunt': {'color': '#AB563F', 'internal name': 't_witchhunt', 'show in prompter?': True},
  'Ukraine': {'color': '#0056B9', 'internal name': 'ukraine', 'show in prompter?': True},
}
