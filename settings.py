from django.conf import settings

# This settings.py file will be imported AFTER settings
# have been initialised in omeroweb/settings.py

# We can directly manipulate the settings
# E.g. add plugins to RIGHT_PLUGINS list
settings.RIGHT_PLUGINS.append(["Searcher",
    "searcher/plugin_config/right_search_form.js.html", "right_search_form"])
