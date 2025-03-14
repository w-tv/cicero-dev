#!/usr/bin/env -S streamlit run
"""If something is used in more than one cicero file, typically put it in this file and import it into the other files.
It's useless to run this stand-alone. But I guess I won't stop you."""

from databricks import sql # Spooky that this is not the same name as the pypi package databricks-sql-connector, but is the way to refer to the same thing.
from databricks.sql.types import Row
from databricks.sql.parameters.native import TParameterCollection
import streamlit as st
from streamlit import runtime
from typing import Any, Callable, NoReturn, TypedDict
import urllib.parse
import re

def labeled_table(rows: list[Row]) -> None:
  st.table([x.asDict() for x in rows]) # for some reason, the asDict puts it in the right form to display the column headers. # possibly a streamlit-bug-workaround, although I've never looked into it.

def catstr(*strables: object) -> str:
  """Not to be confused with its C-language cousin, `strcat()`."""
  return "".join([str(x) for x in strables])

def ssget(string_to_get_from_streamlit_session_state: str, *additional_args: object) -> Any:
  """This function repeatedly retrieves things from things using `.get()`. Starting with the first argument from st.session_state, and then all the subsequent args from the preceding result, in order. This loses type-safety, in a way, since it just returns Any, but st.session_state already didn't have type-safety (Could: figure out how to TypedDict the session_state? Doesn't seem worth it.) because it always just returns `Any | None`. This function also returns `Any | None`. However, long get chains on things taken from session_state like `st.session_state.get("chat").get(streamlit_key_suffix)` get you errors like `error: Item "None" of "Any | None" has no attribute "get"  [union-attr]` — and quite likely so, because that could give you a type error at runtime! You also can't do the ol' `if st.session_state.get("messages") and st.session_state.get("messages").get(streamlit_key_suffix)` "shortcut"-`and` trick, because there might be side-effects between the first and second call of the function. So you'd have to do something crazy like `if m := st.session_state.get("messages") and m.get(streamlit_key_suffix)` (actually, that leads to a type error `error: Name "m" is used before definition  [used-before-def]`). Or break up the clauses or use a variable. Or, you can simply call `ssget("messages", streamlit_key_suffix)` for the same effect.

  Much like .get(), which is better than . and [], this function will never throw an error (unless you make it visit an object that has no .get() method but is not None), only ever return None if something is not found. Note that there is no indication of where in the chain the None is coming from.

  You may also use the base case of get as a simple shorthand for the longer st.session_state.get, which all will agree is much longer to type.

  This function is also called ".get() all Y-combinatorally". "Y-combinatorally" refers to https://en.wikipedia.org/wiki/Fixed-point_combinator#Y_combinator , which is not actually important to understand. It's just the concept of a loop, really. Really this function is more like a fixed-point operator with limited depth than anything having to do with the lambda calculus. But whatever.

  get is a particular type of safe navigation operator, which you can read the wikipedia page about. https://en.wikipedia.org/wiki/Safe_navigation_operator

  Needing this whole thing is very silly. But that's the Python way!"""
  # Although lambda x: x should be a no-op anyway, we *also* specify dont_actually_set_the_value=True to avoid any crazy subtle side-effects.
  return ssmut(lambda x: x, string_to_get_from_streamlit_session_state, *additional_args, dont_actually_set_the_value=True)

def ssdrill[T](anonymous_function: Callable[[Any, Any], T], string_to_get_from_streamlit_session_state: str, *additional_args: Any, dont_actually_set_the_value: bool = False) -> T:
  """The final form of ss-manipulation functions, in terms of which everything else is implemented. It is like ssmut except that the function it takes takes the container and accessor; this is so you can support .pop() (for example)"""
  a = list(additional_args)
  x = st.session_state
  s = string_to_get_from_streamlit_session_state
  while len(a) >= 1:
    if x.get(s) is None:
      x[s] = {} #the fact that we create these is maybe unfortunate...
    # Set up the arguments for the next iteraton of the loop:
    x = x[s]
    s = a.pop(0)
  value = anonymous_function(x,s) #this is purposefully evaluated only once, so the user doesn't have to worry about making f a pure function.
  if not dont_actually_set_the_value:
    x[s] = value
  return value

def ssmut[T](f: Callable[[Any], T], string_to_get_from_streamlit_session_state: str, *additional_args: Any, dont_actually_set_the_value: bool = False) -> T:
  """Like ssset, but the value is set to the value of f(its current value). Hence, it is Session State MUTate. Note that the current value may be None; f must handle this case. This also means the *additional_args does not end in the payload like ssset; instead, it's just all the accessor arguments. Returns the new value, as well as setting it. If dont_actually_set_the_value is True, don't actually set the value, just return it."""
  return ssdrill(lambda container, accessor: f(container.get(accessor)), string_to_get_from_streamlit_session_state, *additional_args, dont_actually_set_the_value=dont_actually_set_the_value)

def ssset(string_to_get_from_streamlit_session_state: str, *additional_args_ending_with_payload: Any) -> None:
  """Like ssget, but setting a value. Note that this means that if a None is encountered along the way, it will be replaced with a {}; much like the behavior of a defaultdict, in a way."""
  ssmut(lambda x: additional_args_ending_with_payload[-1], string_to_get_from_streamlit_session_state, *additional_args_ending_with_payload[:-1])

def sspop(string_to_get_from_streamlit_session_state: str, *additional_args: Any) -> Any:
  """Like ssget, but delete the value we find from its container.""" #could alias ssdel to this I guess.
  return ssdrill(lambda container, accessor: container.pop(accessor) if accessor in container else None, string_to_get_from_streamlit_session_state, *additional_args, dont_actually_set_the_value=True)

def is_admin() -> bool:
  """Return true if admin mode is active and false if it is inactive."""
  return bool(ssget("admin_mode"))

def are_experimental_features_enabled() -> bool:
  """Return true if experimental features are enabled and false if they are not, so as to gate experimental features only to the right users. Since the right users are just admins, this just checks if admin mode is active."""
  return is_admin()

def admin_str(value: object) -> str:
  """Return a value, converted to a string, if admin_mode is active. Otherwise return an empty string.
  This function would ideally return the value untouched (of the input type), and None if admin mode is false, but the fact that str(`None`) becomes "None" in python makes that a footgun waiting to happen :(.
    (You see, you would obviously want to write admin_str("some string") and expect it to not appear if admin mode is off. But instead the word "None" would appear!) """
  return str(value) if is_admin() else ""

def admin_box(expander_box_title: str, contents: object, caption_mode: bool = False) -> None:
  if is_admin():
    expander = st.expander("Ⓐ "+expander_box_title)
    if caption_mode:
      expander.caption(contents)
    else:
      expander.write(contents)

def st_print(*args: object) -> None:
  print(*args)
  st.write(*args)

def st_admin_print(*args: object) -> None:
  print(*args) # the user won't be able to see the print output anyway, so it's inherently limited to admins.
  if is_admin():
    st.write(*args)

def get_base_url() -> str:
  """Gets the url where the streamlit app is currently running, not including any page paths underneath. In testing, for example, this value is probably http://localhost:8501 . This function is from BramVanroy https://github.com/streamlit/streamlit/issues/798#issuecomment-1647759949 , with modifications. “WARNING: I found that in multi-page apps, this will always only return the base url and not the sub-page URL with the page appended to the end.”"""
  try:
    session = runtime.get_instance()._session_mgr.list_active_sessions()[0] # There's occasionally a harmless IndexError: list index out of range from this line of code on Streamlit Community Cloud, which I'd like to suppress via this try-catch for the convenience of the reader of the logs.
    r = session.client.request #type: ignore[attr-defined] #pyright: ignore # There's some kind of crazy runtime class-swapping behavior or something here that means both mypy and pyright don't know what to make of this.
    if r.protocol == "http" and not r.host.startswith("localhost:"): # STREAMLIT-BUG-WORKAROUND (?) for some reason even when we're in an https connection the r.protocol is http. https://github.com/streamlit/streamlit/issues/8600
      r.protocol = "https"
    return str(
      urllib.parse.urlunparse([r.protocol, r.host, "", "", "", ""])# see also: https://github.com/python/mypy/issues/17082
    )
  except IndexError as e:
    return str(e)

def admin_sidebar_print(x: object) -> None:
  """Show some debug-like information in the sidebar. Often best used with f"{foo=}" in the calling code, which will become the name and also the value of the variable, such as foo=2 (naturally, this must be done at the calling site (I assume))."""
  if is_admin():
    st.sidebar.caption(f"Ⓐ Admin mode diagnostic: {x}")

# COULD: use an on_exit thing, and maybe counsel the user that they can usually refresh and retry if they hit an error?
def exit_error(exit_code: int) -> NoReturn:
  st.write("*Ego vero consisto. Accede, veterane, et, si hoc saltim potes recte facere, incide cervicem.*")
  exit(exit_code)

@st.dialog("Database error")
def die_with_database_error_popup(e_args: tuple[object, ...]) -> NoReturn:
  print("Database error", e_args)
  st.write("There was a database error, and the application could not continue. Sorry. Try refreshing the page and trying again.")
  st.write(e_args)
  exit_error(4)

def popup(title: str, body: str, show_x_instruction: bool = True) -> None:
  """This makes a simple modal dialog box in streamlit. It eschews the advanced functionality of the dialog, which usually allows arbitrary code to run. But we haven't needed that so far. (It could probably be done by allowing body to be a callable.)"""
  @st.dialog(title)
  def _() -> None:
    st.write(body)
    if show_x_instruction:
      st.caption("Press enter or click the ❌︎ in the upper-right corner to close this message.")
  _()

def ensure_existence_of_activity_log(dont_complain_about_the_fake_email_its_ok_im_just_reading: bool = False) -> None:
  """Run this code before accessing the activity log. If the activity log doesn't exist, this function call will create it.
  We also check if you're faking being a user, and end the program, so as to refuse to write, if so. You can disable that by passing a flag, in case you're just reading not writing.
  Note that if the table exists, this sql call will not check if it has the right columns (names or types), unfortunately.
  Note that this table uses a real timestamp datatype. You can `SET TIME ZONE "US/Eastern";` in sql to get them to output as strings in US Eastern time, instead of the default UTC."""
  if fe := ssget("fake_email") and not dont_complain_about_the_fake_email_its_ok_im_just_reading:
    popup("You are fake!", f"You are using the fake email {fe}, so I won't write to the activity log, as that would be impolite to the real user of that email.")
    exit()
  sql_call("CREATE TABLE IF NOT EXISTS cicero.default.activity_log (timestamp timestamp, user_email STRING, user_pod STRING, prompter_or_chatbot STRING, prompt_sent STRING, response_given STRING, model_name STRING, model_url STRING, model_parameters STRING, system_prompt STRING, base_url STRING, user_feedback STRING, user_feedback_satisfied STRING, used_similarity_search_backup STRING, hit_readlink_time_limit BOOLEAN, pii_concern BOOLEAN, fec_concern BOOLEAN, winred_concern BOOLEAN, voice STRING, account STRING)")

@st.cache_data(show_spinner=False)
def sql_call(query: str, sql_params_dict: TParameterCollection|None = None) -> list[Row]:
  """This is a wrapper function for sql_call_cacheless; the difference is that this one *is* cached. See that other function for more information about the actual functionality."""
  return sql_call_cacheless(query, sql_params_dict)

def sql_call_cacheless(query: str, sql_params_dict: TParameterCollection|None = None) -> list[Row]:
  """Make a call to the database, returning a list of Rows. The returned values within the Rows are usually str, but occasionally might be int (as when getting the count) or float or perhaps any of these https://docs.databricks.com/en/dev-tools/python-sql-connector.html#type-conversions .
  TParameterCollect is basically dict[str,Any], although it's a bit more complicated, limited, and flexible than that."""
  # COULD: (but probably won't) there is a minor problem where we'd like to ensure that a query to a table x only occurs after a call to CREATE TABLE IF NOT EXISTS x (parameters of x). Technically, we could ensure this by creating a new function ensure_table(table_name, table_types) which then returns an TableEnsurance object, which then must be passed in as a parameter to SQL call. However, then we would want to check if it were the correct table (and possibly the right parameter types) which would greatly complicate the function signature of sql_call, because we'd have to pass the table name(s) in too, and then string-replace them into the query(?). So, doesn't seem worth it. ALSO: sometimes we don't have the code to create the table. Some tables have to be created and populated by the team in other ways.
  try:
    with sql.connect(server_hostname=st.secrets["DATABRICKS_HOST"], http_path=st.secrets["DATABRICKS_HTTP_PATH"], access_token=st.secrets["DATABRICKS_TOKEN"]) as connection: #These secrets should be in the root level of the .streamlit/secrets.toml
      with connection.cursor() as cursor:
        return cursor.execute(query, sql_params_dict).fetchall()
  except Exception as e:
    die_with_database_error_popup(e.args)

def get_value_of_column_in_table(column: str, table: str) -> Any | None:
  """This returns one value. This is cacheless, by the way, because we mostly use it for access, and access not updating promptly is a minefield of user-hostile interactions.
  Please note that the column and table are just f-stringed in, so to avoid sql injection you should not let the user set them directly. This is a program-internal function ONLY!!! It should only be used on fixed, known values, & is only for the purpose of abstraction."""
  result = sql_call_cacheless(
    f"SELECT {column} FROM {table} WHERE user_email == :user_email",
    {"user_email": ssget('email')}
  )
  try:
    return result[0][0] # list of Rows, get 0th Row, get 0th entry (contents of column).
  except IndexError:
      return None

def get_list_value_of_column_in_table(column: str, table: str) -> list[Any]:
  """Same as get_value_of_column_in_table, but also converts None to [], and also converts the np.array we get here to a plain ol' python list."""
  result = get_value_of_column_in_table(column, table)
  return result.tolist() if result is not None else [] # Unfortunately, it could be None, and thus not iterable, and the typechecker is no help here (since the database read loses type information). So, we have to do this awkward little dance.

@st.cache_data(show_spinner=False)
def load_account_names() -> tuple[str, ...]:
  return tuple(row[0] for row in sql_call("SELECT DISTINCT rollup_name FROM cicero.ref_tables.ref_account_rollup WHERE visible_frontend ORDER BY rollup_name ASC"))

def assert_always(x: object, message_to_assert: str|None = None) -> None | NoReturn: #COULD: currently this enjoys no type-narrowing properties, alas. Possibly TypeIs does what we want here? #TODO: actually the whole point of this is to try to provide an assert() that can be used for static typing that won't fail at runtime if python optimization is ever turned on. But this seems like something to take up with the python community and possibly the typing guy (make them add an assert_always, basically).
  """This function is equivalent to assert, but cannot be disabled by -O"""
  if not x:
    raise AssertionError(message_to_assert or x)
  return None

# This is the 'big' of topics, the authoritative record of various facts and mappings about topics.
Topics_Big_Payload = TypedDict("Topics_Big_Payload", {'color': str, 'show in prompter?': bool, 'regex': str})
topics_big: dict[str, Topics_Big_Payload] = (
  {name: Topics_Big_Payload({"color":color, "show in prompter?": visible_frontend, "regex": regex})
  for name, color, visible_frontend, regex
  in sql_call_cacheless('SELECT tag_name, color, visible_frontend, regex_pattern FROM cicero.ref_tables.ref_tags WHERE tag_type == "Topic" AND enabled ORDER BY tag_name ASC')}
)

def possibly_pluralize(quantity: float, label: str) -> str:
  """ Return a label with the quantity either pluralized or kept singular, as appropriate (iff == 1). This only covers the "dumb plural", just adding s. Haven't needed more yet. """
  return f"{quantity} {label}{'' if quantity == 1 else 's'}"

def pii_detector(input: str) -> dict[str, list[object]]:
  """Check for phone numbers, email addresses, credit card numbers, and street addresses in the text, and return true/false for if we've found anything and a dict of what of those we've found.
  It's important, for the assumptions of the caller of this function, that if no pii is found, then this function returns an empty (and thus falsy) dict. Therefore, you can use the return value of this function in an if, and a bool().
  re.findall seems to be declared (in typeshed I guess) with a return type of `list[Any]`, which I consider ultimately bad practice although there are probably overwhelming practical reasons in this case to declare it so. So, anyway, that's why we treat it (and, therefore, this function) as though it returns `list[object]`. Possibly you could consider this a TYPESHED-BUG-WORKAROUND, although it would probably take multiple typing PEPs to fix the assumptions of the type system that produce this corner case. Possibly even dependent typing (but probably not). We could also have done some str calls to return list[str], but it didn't end up mattering.
  Actually checking for all phone number types ( such as those covered by https://en.wikipedia.org/wiki/List_of_country_calling_codes ) would be extremely arduous and possibly lead to unwanted to false-positives with other numbers. So we basically just check for american phone numbers and maybe some other ones that happen to have a similar form. (We also don't check for phone numbers that exclude area code.) Similar story with credit card numbers and the various forms in https://en.wikipedia.org/wiki/Payment_card_number#Structure . We also purposefully do not exclude the non-issuable Social Security numbers ( https://en.wikipedia.org/wiki/Social_Security_number#Valid_SSNs ), so that example SSNs can be detected for testing purposes."""
  phone = re.findall(r"(?<!\d)\d?[- ]?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}(?!\d)", input)
  email = re.findall(
    r"([a-z0-9!#$%&'*+\/=?^_`{|.}~-]+@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)",
    input,
    re.IGNORECASE,
  )
  credit_card = re.findall(r"(?<!\d)(?:(?:\d{4}[- ]?){3}\d{4}|\d{15,16})(?!\d)", input)
  street_address = re.findall(
    r"\d{1,4} (?:\w+ ){0,4}(?:street|st|avenue|ave|road|rd|highway|hwy|square|sq|trail|trl|drive|dr|court|ct|park|parkway|pkwy|circle|cir|boulevard|blvd)\b",
    input,
    re.IGNORECASE,
  )
  ssn = re.findall(r"(?<!\d)\d{3}[- ]?\d{2}?[- ]?\d{4}(?!\d)", input)
  return (    
    {}
    | {'phone': phone} if phone else {}
    | {'email': email} if email else {}
    | {'credit card': credit_card} if credit_card else {}
    | {'street address': street_address} if street_address else {}
    | {'social security number': ssn} if ssn else {}
  )
