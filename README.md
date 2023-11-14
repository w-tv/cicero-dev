# Cicero

> Lorem ipsum dolor sit amet, consectetur
>
> —Cicero

Cicero (pronounced "KICK arrow") is an app we built using, and currently hosted by, streamlit; it's a frontend that we use to construct and send prompts to our backend. It should hopefully be easy to use for an end-user who doesn't know much about technology but is familiar with this industry. It's currently available on https://cicero.streamlit.app/ although this may not be true later.

To host Cicero, you will need a file, secrets.toml, to be placed in the .streamlit/ folder in this repo. This tells the code what the model_uri and databricks_api_token we're contacting are. Since this is basically a password, it shall not be checked into git. You will have to ask someone with the file, or generate your own (see https://docs.streamlit.io/library/advanced-features/secrets-management for details on the later option). Note that you do NOT need such a file to merely use an instance of Cicero that someone else is running and serving to you as a webpage. Also, you don't need to read this readme if you just want to use someone else's Cicero. This readme is about running Cicero. Also, if you're hosting Cicero on Streamlit (Streamlit Community Cloud), which we are, you don't use a file to enter the secrets, you enter them this other way, and will not need to create a file yourself: https://docs.streamlit.io/streamlit-community-cloud/deploy-your-app/secrets-management

Access to the version of Cicero hosted on the Streamlit Community Cloud on https://cicero.streamlit.app/ is controlled through a whitelist of emails that you can ask to be added to.

The python version Cicero currently uses in production is 3.9. The production app is up at https://cicero.streamlit.app/ . There is also a staging/active-development version up at https://cicero-dev.streamlit.app/ . This also has its own repo that development is done in, instead of developing directly in prod. This would be a branch, and for that matter we would be using a later version of python, but ehhhh streamlit community cloud has weird constraints ehhhh don't worry about it.

Edit `streamlit_app.py` to customize this app to your heart's desire. However, it should be pretty much entirely as customized as we need it to be, at this point. Maybe a couple features left.

If you have any questions about streamlit, checkout its [documentation](https://docs.streamlit.io) and [community
forums](https://discuss.streamlit.io). If you have any questions about Cicero, he wrote some books you can read.

And remember: the first thing to do is get the best of both worlds. You can!
