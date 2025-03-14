# Cicero

## Cicero use and infrastructure

> Lorem ipsum dolor sit amet, consectetur
>
> —Cicero

Cicero (pronounced "KICKer owe"¹) is an app we built² using, and currently hosted by, streamlit; it's a frontend that we use to construct and send prompts to our backend. It should hopefully be easy to use for an end-user who doesn't know much about technology but is familiar with this industry. It's currently available on https://cicero.streamlit.app/ although this may not be true later.

UPDATE/TODO: we should add a section to this document explaining cicero.targetedvictory.com and cicero-dev.targetedvictory.com; the trgdv-msvc stuff; the secrets in the secrets-toml (and how you need to ask SMC to get added to the list of people who can view and edit the secrets); how you have to ask Maxwell Oppong to add people to okta app access so they can get there; and maybe how the docker file works; and maybe all the knowledge transfer stuff Sean talked about in the recorded meeting; and, once it settles, all the different branches and repos we keep track of, and how the deploys to tv.com are so long that if you deploy to tv prod during business hours this causes people random errors ("This page does not exist, redirecting you to the main page" or something like that) for like the following hour. Don't deploy to prod during business hours 9am-5pm ET (unless there's a crucial error in prod and someone asks you to); push to prod on like thursdays after work, usually. You can look at the build history using https://console.cloud.google.com/cloud-build/builds;region=us-central1?project=trgdv-shared-ci-shared , and the logs at https://console.cloud.google.com/run/detail/us-central1/cicero/logs?project=trgdv-shared-msvc-prod

Currently, you need to have git installed to properly set up this program (since the requirements.txt specifies a git repo dependency that is a hotfix we need, of a different dependency). This is unfortunate. However, the repo is already a git repo so you probably have git installed anyway hopefully?

To host Cicero, you will need a file, secrets.toml, to be placed in the .streamlit/ folder in this repo. This tells the code what the DATABRICKS_HOST, DATABRICKS_HTTP_PATH, and DATABRICKS_TOKEN (the databricks api access token) are, as well as the aud value for google iap. It would also contain google sign-in information if we ever implemented that again. Since this secrets file is basically a password, it shall not be checked into git. You will have to ask someone with the file, or generate your own (see https://docs.streamlit.io/library/advanced-features/secrets-management for details on the later option). Note that you do NOT need such a file to merely use an instance of Cicero that someone else is running and serving to you as a webpage. But also, you don't need to read this readme if you just want to use someone else's Cicero. This readme is about running Cicero. Also, if you're hosting Cicero on Streamlit (Streamlit Community Cloud), which we are, you don't use a file to enter the secrets, you enter them this other way, and will not need to create a file yourself: https://docs.streamlit.io/streamlit-community-cloud/deploy-your-app/secrets-management

Access to the version of Cicero hosted on the Streamlit Community Cloud on https://cicero.streamlit.app/ is controlled through a whitelist of emails that you can ask to be added to. After a user is added to this, or given okta access through Maxwell Oppong, then you should add an entry to the user_pod table saying what "pod" they are in (this is some kind of business thing, like a group, that I don't really understand. I just input what the boss tells me.). You can use the databricks sql query composer to do this, or you can use New Pod Key tool in the Cicero app (which you can see iff you're in admin mode), which will give you enticing buttons to click, and is a slightly more comfortable experience, although it is also extremely developer-internal-tool-y.

There are a number of databases on the backend Cicero relies on. Sometimes, like the activity log, Cicero will create the table if it doesn't exist. Sometimes, you must manually create the table in your backend, because that data is crucial and Cicero has no way to create the data itself (Cicero the app, just being the frontend, doesn't have any way to tell you who the permitted user accounts are, for example). Some (most?) of the code that implements our backend is in https://github.com/targeted-victory/cicero-backend . Our code-organizational structure was heavily influenced by https://en.wikipedia.org/wiki/Conway%27s_law . That's why it took us a month to move a dict from one repo to another once. But, both pieces of code need to run in different places, so, it's not insane to have 2 repos. Although they could totally just be one repo. Like two folders in the same repo, for example. Well, whatever, it's chill; it's fine this way as well.

Local development on cicero uses the following three batch scripts, which are also working bash scripts:
* run.bat (installs requirements and launches the program. Quick, and with minimal hassle!)
* typecheck.bat (typechecks the project)
* reqcheck.bat (tries to check if we have any spurious dependencies in our requirements.txt)

The python version Cicero currently uses in production is 3.12 , specifically 3.12.6 . It can probably run in any version 3.12+ as well. The production app is up at https://cicero.streamlit.app/ . There is also a staging/active-development version up at https://cicero-dev.streamlit.app/ . This also has its own repo (a fork) that development is done in, instead of developing directly in prod. This would be a branch but streamlit community cloud only allows one deployment per repo. (We also would have called it cicero-staging, because it's our [staging environment](https://en.wikipedia.org/wiki/Deployment_environment#Staging), but curiously streamlit community cloud has the rule "Custom subdomains can't include the term 'staging'.") It's good to upgrade our version of streamlit periodically; but, given that that's our production environment, the version is pinned in the requirements.txt to prevent surprises. Dev is also a proving ground, and typically it's a couple commits ahead of prod, just to give those commits a little extra time to have their flaws detected by users (some users use dev) if flaws there be, and then I push dev to prod and then work on a new batch of dev changes.

The current development workflow for this project is that changes are made in the dev(elopment) repo, and then once OK'd, that entire history is pushed to the prod(uction) repo. Patch notes may be created. If you are in dev, have the OK, and want to do the push to prod, here are the steps:

```
git remote add prod https://github.com/achangtv/cicero # Set prod as an additional upstream in my local-machine version of dev. Only have to do this once.
git push prod # This will push the current history to prod (instead of the default `git push`, which will still push to dev). If you need to push to a branch on prod with a different name than the local branch, you can use git push prod local_branch_name:remote_branch_name, where local_branch_name is probably master.
```

You can also use the appropriate scripts in push_scripts/

Note that the git history of this project is basically a straight line. As God intended. Unfortunately, I don't have the time/space here to explain the various git commands that allow you to keep on the right history, here. (Then again, you can always look up how to abandon your git history and use the upstream one...) Wyatt will usually be able to fix history for you. You may also try playing https://ohmygit.org/ and/or https://learngitbranching.js.org/ to get a handle on git. There is also a forthcoming blogpost from Wyatt about why you should rebase instead of merging in most cases (assuming you can't fast-forward (ff); ff is usually the right thing to do when you can).

Edit `cicero.py` to customize this app to your heart's desire. However, it should be pretty much entirely as customized as we need it to be, at this point. Maybe a couple features left.

For compatibility reasons, NEVER use \ as a file path delimiter (example: "assets\CiceroChat_800x800.jpg"); ALWAYS use / (example: "assets/CiceroChat_800x800.jpg"). Forward slash ( / ) is supported on more systems, and backslash ( \ ) is also the string escape character in Python, which means if you use it your file paths might get messed up.

## Type signatures and typechecking

This project is typechecked! You can run typecheck.bat to check the types. If you are a novice python programmer or don't like types, don't worry; python is gradually typed so you can just ignore the types and it will be fine (typecheck.bat will probably fail for a while, however, until someone fixes it; but nothing relies on typecheck.bat passing). This project primarily uses mypy, and satisfies mypy --strict. This project also uses and passes pyright (also found in pylance and many configurations of VS Code), which provides slightly different coverage and thus is also good to have. (You can technically set pyright to strict mode using a `{"typeCheckingMode": "strict",}` pyrightconfig.json file, but this complains about things that are unrealistic for us to fix, so we don't do that.) This project also almost satisfies ultrastrict, a typechecking mode I made up where you aren't allowed to use typing.cast, type:ignore comments, nor the no_type_check and no_type_check_decorator decorators — the idea is that your types are then entirely statically verified, with a guarantee that your types are correct at runtime. There are a few places where we violate ultrastrict mode, but they are all bugs in something else that we are working around... sometimes the typechecker (sometimes our deps' type signatures).

The project has now adopted python-3.12-standard parameter type syntax, so it may be a while before any typecheckers other that pyright and mypy support those.

When a typechecker works for our purposes, we add it to typecheck.bat, and have a party. This project also evaluated using pytype (via wsl), which has the apparent benefit of being able to deduce all types for you without annotations (?!) (can pyright also do this? --createstub? ... I guess both of these are just "first draft" auto stubs, like everything else with that feature...) but it has some weird errors and is a couple minor python versions behind so eh maybe someday. Basedmypy also seems cool, but I worry it's too advanced, and its good feature might make the type signatures of this project too bespoke to it; maybe we'll use it some day anyway. Basedpyright seems about equivalent to pyright, but at least it installs its deps properly! (Edit: basedpyright has different features than pyright so we don't satisfy it so we aren't using it for now.) Haven't successfully used pyre yet; also, it doesn't support PEP 695 Type Parameter Syntax yet, apparently, based on trying that in https://pyre-check.org/play/ . Astral's [Red Knot](https://github.com/astral-sh/ruff/issues?q=is%3Aopen+label%3Ared-knot+is%3Aissue) isn't released yet. Pyanalyze seems promising, as you can write custom type checking in it, but when I tried it out I found a number of confusing false-positives and/or found it difficult to get it to look at the right files.

A lot of static typing in this project is, as it were, lost, on the barrier between us and our database (sql_call). But it's probably ultimately fine. I mean, it causes some errors... but it's fine. I mean, we can't really do anything about it, anyway. We could probably, at best, throw an error on mis-match between expected an recieved type from the database. But that's what we already do, anyway.

Typechecking serves two, related purposes:
1. Code quality (in the present). Typechecking prevents type errors from occurring at runtime, and bothering our users.
2. Maintainability (in the future). Type annotations are one of the best tools we have, currently, against the degradation of code quality. It is the hope of this author that Cicero will be easy to maintain and extend in the future — as easy as possible (but no easier). The main way we achieve this is by cleverly writing less code, so there is less to go wrong later. But type annotations are another way. Now, unfortunately, the type annotations themselves are going to require maintenance, and this will be especially difficult if you are a novice python programmer — as most python programmers are. (Although maybe in an absolute sense it will remain easy.) So, if you find yourself unable to maintain the type annotations, you can let them go. This will decrease the future maintainability of the project, but can be a calculated sacrifice.

About 50% of the type errors we find are spurious and busywork and 50% are legitimate weird edge cases that it was good to alter the code to protect against. So, that's a pretty good ratio.

The python type system is relatively recent and not entirely complete, so sometimes it's impossible or very convenient to do something with the type signatures that we would like to do. Oh well.

In part, we try to be rigorous about typechecking because we are very lax about testing. We currently subscribe to the [raw code](https://x.com/qntm/status/949070111083778050) ideology. It's been working fairly well. Ideally, we will change that soon.

## Labels of irksomeness

Various ridiculous workarounds in the code have been labeled FOO-BUG-WORKAROUND, where FOO is the name of the dependency to blame, in comments in the code. Eventually you may have the pleasure of removing these! You can grep for these. (Remember: git has a grep, called git grep, so you can use that if you don't have grep (eg because you are on windows).)

Various things in this project have been labeled TO⁠DO, to eventually be dealt with. You can also grep for this. There is something weaker than a TO⁠DO, which is a Could, which just notes the possibility of developing in a different direction in the future. The idea is that all TO⁠DOs must be dealt with (even the ones that are just "figure out if we need to do this") and the sooner the better; Coulds can hang around indefinitely.

Incidentally, all times the text "TO⁠DO" is mentioned but does not actually mark a TO⁠DO I need to deal with, such as in the above paragraph, I use a unicode character U+2060 WORD JOINER in the middle, which generally stops grep-like tools from picking up on that string. You should also do this, as it will make your grep results cleaner.

## Additional information about streamlit

If you have any questions about streamlit, checkout its [documentation](https://docs.streamlit.io) and [community forums](https://discuss.streamlit.io). If you have any questions about Cicero, he wrote some books you can read.

On an architectural note, we probably should not have used streamlit. It's a fine library, but it just abstracts over, and therefore repackages, html. This means using streamlit does not reduce the final complexity of our project. It also means that as we desire features that would be somewhat trivial in html+js, we have to wait for streamlit to provide those features to us (sometimes you can embed html+js into the streamlit page, but sometimes something about how streamlit works breaks this). The streamlit ImGui flow is also not trivial to reason about, which means that, to some extent, you have to "learn streamlit", much as you might "learn html". In the famous words of somebody or other, "Any problem can be solved with another layer of indirection. Except of course for the problem of too many layers of indirection."

## On variables

Regular variables are to be preferred over session state variables, because static analysis tools work better with the former than the latter. That said, sometimes you need to use session state variables; that's why it's even a feature. In a similar vein, unless it's absolutely necessary (when? I can't think of anything like that), you should use the ssget, ssset, sspop, ssmut functions instead of accessing streamlit's session_state directly.

Additionally, the use of fewer variables is preferred over the use of a greater number of variables — but not as strongly as the use of fewer magic values or computations is preferred over the use of a greater number of magic values or computations!

## is_admin and are_experimental_features_enabled

Certain features of the app, such as the performance information, are only available to be seen by admins. These are known as "admin mode" features, and you should always use is_admin to check if someone is an admin — or one of the other specialized functions with admin in the name, like admin_box.

Other features of the app are experimental, and are only available to be seen by admins, but on a temporary basis — they will eventually be approved for normal users as well, or scrapped. You should use the function are_experimental_features_enabled for these. Technically, these are all "to⁠do" items, in that eventually they should all be turned into some other type of feature, or removed, and you can grep for are_experimental_features_enabled in the code to find out which ones need to be approved or whatever. Please note that a possible future for an experimental feature is being turned into a permanent, admin-only feature; you **can** have the "best" of both worlds 🥳, if you want.

## Nulls in the database

Cicero endeavors to never write any nulls to the database. Since null is the implicit value in the database, writing explicit values instead (usually a string like "not asked" or something) lets us know that absences are intentional. This allows for easier detection of bugs in code that writes to the database, or erroneous data entry. (If you see a null? That's a bug.) As of 2025-03-12 (update this number when necessary 🙂) this should be true, so new entries can be expected to enjoy this property, but the database has not been fixed retroactively, unless it was extremely easy to do so.

Typically, new nulls are introduced in huge chunks of a column at a time, when we extend the table: everything cell before when we start generating and storing the new value is just going to be null; that's basically just how databases work 🤷.

## Certain points of code style.

This codebase almost never uses Exceptions. Python has multiple-return so we would just return error codes if need be (which is a rare need, anyway). This is because Exceptions are bad and make control-flow confusing. The two places we do use Exceptions are (1) code we depend on uses it, in which case we just handle and deal with the exception and (2) we intend to just crash the program (ie: end the page run) with an informative error message (the control flow is not complicated here, because it's just: over). Note that technically any line of code in python could throw an Exception at any time, because the host machine could run out of memory. But, you know, that's fine I guess. It's not like there's any computer system that's immune to running out of memory on arbitrary tasks.

This codebase is not very object-oriented. Unless we need to use dependency code that is object-oriented, or we need to do some kind of type syntax that is technically a class, we don't have or use any classes. In part this is because we don't deal with phenomena that are naturally modelable as Objects (we mostly just deal with strings and floats). In part it's because I don't personally like objects. I'm much more of a types-and-primitives guy than an objects guy. I don't have much of a use for objects. Unless I wanted to make a new class of primitive with special infix operators, I guess, or a suite of related manipulation functions. Cicero_chat is the thing we have that is most like an object-oriented subject, because it has associated state an manipulations, but I still decided to use plain old functions and variable for that. Not using object-oriented methods means there's a whole panoply of things the maintainer of this code doesn't have to learn or worry about (class semantics); this is, of course, at the cost of learning about and worrying about a whole other category of thing (type semantics).

All Code Is Liability. ACIL. I'm constantly trying to engineer myself out of a job. Unfortunately, it is very difficult.

All Email Is Spam. AEIS. —Alex Chang

All Type-ignores Are Errors. ATAE. (Usually errors in the typechecker that aren't worth the time to fix. Or maybe in your code, but also not worth.)

## An annoyance: dapi

dapi360d025c9e135c809de05abbf3196a06 is an old token we invalidated, and in fact put into source control because we knew we were going to do that, so it would be ok. Regardless, github secrets scanning will probably bug you about objects such as 29f0ba44c73d10d7955d22666561c91caad45350 because they contain this. But you can just do the bypass, it's fine.

## Signoff

And remember: the first thing to do is get the best of both worlds. You can!

## Footnotes

¹ Scholars debate whether the i in Cicero's name would have been pronounced like the i in igloo or the ee in eek. Personally, I find the ee idea more plausible. However, all scholars agree that the Cs in Cicero's name are pronounced like Ks. In contrast, the conventional english name for Cicero is pronounced as though they were Ss. All of these variations may acceptably be used to refer to this project.

² And for any future developers: Alex Chang worked on this project!
