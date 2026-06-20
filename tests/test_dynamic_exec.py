import sys
from types import ModuleType

# Setup dummy modules in sys.modules
requests_mock = ModuleType('requests')
requests_mock.exceptions = ModuleType('requests.exceptions')
class RequestException(Exception): pass
requests_mock.exceptions.RequestException = RequestException
sys.modules['requests'] = requests_mock

feedparser_mock = ModuleType('feedparser')
class CharacterEncodingOverride(Exception): pass
feedparser_mock.CharacterEncodingOverride = CharacterEncodingOverride
sys.modules['feedparser'] = feedparser_mock

# Read parser.py
with open("parser.py", "r") as f:
    code = f.read()

# Replace static imports with pass
code = code.replace("import requests", "pass")
code = code.replace("import feedparser", "pass")

# Execute in custom namespace
namespace = {
    '__name__': 'parser',
    'requests': requests_mock,
    'feedparser': feedparser_mock,
    'sys': sys,
}
exec(code, namespace)
print("parser executed successfully!")
