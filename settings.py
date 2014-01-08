from django.conf import settings

# This settings.py file will be imported AFTER settings
# have been initialised in omeroweb/settings.py

# We can directly manipulate the settings
# E.g. add plugins to RIGHT_PLUGINS list
import django
if django.VERSION < (1, 6):
    settings.RIGHT_PLUGINS.append([
            "Searcher",
            "searcher/plugin_config/right_search_form.js.html",
            "right_search_form"])

# OMERO 5: Need to manually configure:
# omero config set omero.ui.right_plugins '[[...], ... ["Searcher", "searcher/plugin_config/right_search_form.js.html", "right_search_form"]]'
