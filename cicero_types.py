#!/usr/bin/env -S streamlit run
"""This is like cicero_shared, but specifically for types (and type-based machinery. We'll see if it's useful, and if not we might merge it back in. It's useless to run this stand-alone. But I guess you can."""

from typing import Any, Literal, get_args, TypeAliasType

def aa(t: TypeAliasType) -> tuple[Any, ...]:
  "“aa”, “alias' args”: get the type arguments of the type within a TypeAlias. (Usually, we have a lot of Literal types, that are aliased, and this gets you the values from those types.) Pronounced like a quiet startled yelp."
  return get_args(t.__value__) # We only need .__value__ here because of the type keyword.

# The `type` keyword here, used for defining type alias, is completely optional, but seems like a good idea. (Note: the resulting types are TypeAlias objects now, instead of their original types, so some indirection may be required, like using `aa` instead of `get_args`.) It was added to python in 3.12, so it's quite recent. It's also rather hard to check for the necessity of adding a `type` keyword, although it's theoretically automatically detectable. I think you need to do `ruff check --select PYI026`, and even then it only works on .pyi files. So, we might not have complete strictness on marking every type alias as `type` yet. See also, https://github.com/astral-sh/ruff/issues/8704 " Add rule to encourage using type aliases (generalize PYI026) #8704 "
#See https://stackoverflow.com/questions/64522040/dynamically-create-literal-alias-from-list-of-valid-values for an explanation of what we're doing here with the Literal types and get_args (here, `aa`).
type Short_Model_Name = Literal["Llama-3.1-405b-Instruct", "DBRX-Instruct", "Llama-3.1-70b-Instruct", "Mixtral-8x7b-Instruct"]
type Long_Model_Name = Literal["databricks-meta-llama-3-1-405b-instruct", "databricks-dbrx-instruct", "databricks-meta-llama-3-1-70b-instruct", "databricks-mixtral-8x7b-instruct"] #IMPORTANT: the cleanest way of implementing this REQUIRES that short_model_names and long_model_names entries correspond via index. This is an unfortunate burden, since it cannot be enforced automatically, but it's better than the other ways I tried...
short_model_names: tuple[Short_Model_Name, ...] = aa(Short_Model_Name)
long_model_names: tuple[Long_Model_Name, ...] = aa(Long_Model_Name)
short_model_name_default = short_model_names[0] #this doesn't have to be the first value, but I find it more convenient to have that line up like that.

def short_model_name_to_long_model_name(short_model_name: Short_Model_Name) -> Long_Model_Name:
  return long_model_names[short_model_names.index(short_model_name)]

type Voice_Corporate = Literal["Default", "A16Z", "WCW", "TASC", "1870", "CRES", "Better Solutions", "Highland Fleets", "HAN", "Meta"]
type Voice_Noncorporate = Literal["Default", "NRCC", "AFPI", "Vivek", "Kiggans", "Arvind", "Joni Journal", "CLF", "RJC", "Crane", "Professor", "Tenney"]
type Voice = Voice_Corporate | Voice_Noncorporate
voices_corporate: tuple[Voice_Corporate, ...] = aa(Voice_Corporate)
voices_noncorporate: tuple[Voice_Noncorporate, ...] = aa(Voice_Noncorporate)
voice_default: Voice = "Default" # Technically we could DRY the this, but we might have to use something like https://github.com/jorenham/optype/blob/master/README.md#optypeinspect 's get_args if we do so.

type Chat_Suffix = Literal["", "_corporate", "_prompter", "_video_brief"]
chat_suffixes: tuple[Chat_Suffix, ...] = aa(Chat_Suffix)
chat_suffix_default = chat_suffixes[0]
