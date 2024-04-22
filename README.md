# Cicero

> Lorem ipsum dolor sit amet, consectetur
>
> —Cicero

Cicero (pronounced "KICKer owe"¹) is an app we built using, and currently hosted by, streamlit; it's a frontend that we use to construct and send prompts to our backend. It should hopefully be easy to use for an end-user who doesn't know much about technology but is familiar with this industry. It's currently available on https://cicero.streamlit.app/ although this may not be true later.

To host Cicero, you will need a file, secrets.toml, to be placed in the .streamlit/ folder in this repo. This tells the code what the model_uri and databricks_api_token we're contacting are. Since this is basically a password, it shall not be checked into git. You will have to ask someone with the file, or generate your own (see https://docs.streamlit.io/library/advanced-features/secrets-management for details on the later option). Note that you do NOT need such a file to merely use an instance of Cicero that someone else is running and serving to you as a webpage. Also, you don't need to read this readme if you just want to use someone else's Cicero. This readme is about running Cicero. Also, if you're hosting Cicero on Streamlit (Streamlit Community Cloud), which we are, you don't use a file to enter the secrets, you enter them this other way, and will not need to create a file yourself: https://docs.streamlit.io/streamlit-community-cloud/deploy-your-app/secrets-management

Access to the version of Cicero hosted on the Streamlit Community Cloud on https://cicero.streamlit.app/ is controlled through a whitelist of emails that you can ask to be added to.

Local development on cicero uses the following three batch scripts, which are also working bash scripts:
* run.bat (installs requirements and launches the program. Quick, and with minimal hassle!)
* typecheck.bat (typechecks the project)
* reqcheck.bat (tries to check if we have any spurious dependencies in our requirements.txt)

The python version Cicero currently uses in production is 3.11 , specifically 3.11.7 . It can probably run in 3.10 and 3.12+ as well, but not 3.9 because we elected to use a feature from after python 3.9 . The production app is up at https://cicero.streamlit.app/ . There is also a staging/active-development version up at https://cicero-dev.streamlit.app/ . This also has its own repo (a fork) that development is done in, instead of developing directly in prod. This would be a branch but streamlit community cloud only allows one deployment per repo. (We also would have called it cicero-staging, because it's our [staging environment](https://en.wikipedia.org/wiki/Deployment_environment#Staging), but curiously streamlit community cloud has the rule "Custom subdomains can't include the term 'staging'.") We require streamlit >= 1.31.0 in requirements.txt because we use a feature from 1.30.0. We probably get the latest production version of streamlit on the community cloud on deployment, but locally I test with 1.31.0 at the moment.

The current development workflow for this project is that changes are made in the dev(elopment) repo, and then once OK'd, that entire history is pushed to the prod(uction) repo. Patch notes may be created. If you are in dev, have the OK, and want to do the push to prod, here are the steps:

```
git remote add prod https://github.com/achangtv/cicero # Set prod as an additional upstream in my local-machine version of dev. Only have to do this once.
git push prod # This will push the current history to prod (instead of the default `git push`, which will still push to dev)
```

Edit `cicero.py` to customize this app to your heart's desire. However, it should be pretty much entirely as customized as we need it to be, at this point. Maybe a couple features left.

We have all the subpages listed as cicero_\*.py files instead of pages/ because the default behavior of losing all widget state on page switch was undesireable, so we just use tabs for that functionality instead.

This project is typechecked! You can run typecheck.bat to check the types. If you are a novice python programmer or don't like types, don't worry; python is gradually typed so you can just ignore the types and it will be fine (typecheck.bat will probably fail for a while, however, until someone fixes it; but nothing relies on typecheck.bat passing). This project primarily uses mypy, and satisfies mypy --strict. It also almost satisfies ultrastrict, a typechecking mode I made up where you aren't allowed to use typing.cast, type:ignore comments, nor the no_type_check and no_type_check_decorator decorators — the idea is that your types are then entirely statically verified, with a guarantee that your types are correct at runtime. There are a few places where we violate ultrastrict mode, but they are all bugs in something else that we are working around... currently the typechecker (although it used to be our deps' type signatures).

Anyhow, this project also evaluated using pyright, especially pyright --skipunannotated, but found it had a few too many confusing false-positive errors. We also evaluated pytype (via wsl), which has the apparent benefit of being able to deduce all types for you without annotations (can pyright also do this?) but are waiting on this issue to be resolved https://github.com/google/pytype/issues/1545 to accommodate our big dict. So, so far we are sticking with mypy. Once all of them work for our use case, we will probably add them all into typecheck.bat, and have a party.

Various ridiculous workarounds in the code have been labeled FOO-BUG-WORKAROUND, where FOO is the name of the dependency to blame, in comments in the code. Eventually you may have the pleasure of removing these!

If you have any questions about streamlit, checkout its [documentation](https://docs.streamlit.io) and [community forums](https://discuss.streamlit.io). If you have any questions about Cicero, he wrote some books you can read.

And remember: the first thing to do is get the best of both worlds. You can!

―

¹ Scholars debate whether the i in Cicero's name would have been pronounced like the i in igloo or the ee in eek. Personally, I find the ee idea more plausible. However, all scholars agree that the Cs in Cicero's name are pronounced like Ks. In contrast, the conventional english name for Cicero is pronounced as though they were Ss. All of these variations may acceptably be used to refer to this project.