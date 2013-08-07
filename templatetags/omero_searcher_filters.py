from django import template

register = template.Library()

@register.filter
def escape_csv(value):
    """
    Escape double quotes in a CSV file by replacing it with a pair of quotes
    http://stackoverflow.com/questions/769621/dealing-with-commas-in-a-csv-file
    """
    return value.replace('"', '""')
