import os
import sys
import pkgutil
import importlib
import keyword
import re
import threading
import urllib.request
from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.application.current import get_app

# --- CONFIGURATION ---
GITHUB_RAW_URL = "https://github.com/ibrahim443213/nans/blob/main/nans.py"  # CHANGE THIS!

# --- FILE SETUP ---
filename = sys.argv[1] if len(sys.argv) > 1 else 'hello.txt'
target_name = "nans.py"

if os.path.exists(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        text = f.read()
else:
    text = ''

def get_installed_packages():
    return set([m.name for m in pkgutil.iter_modules()])

def get_module_attributes(module_name):
    try:
        mod = importlib.import_module(module_name)
        return dir(mod)
    except Exception:
        return []

def get_object_attributes(obj_path):
    """Get attributes for a dotted object path, e.g. colorama.Fore"""
    try:
        parts = obj_path.split('.')
        mod = importlib.import_module(parts[0])
        obj = mod
        for part in parts[1:]:
            obj = getattr(obj, part)
        return dir(obj), obj
    except Exception:
        return [], None

class PythonAndImportCompleter(Completer):
    def __init__(self):
        self.words = set(keyword.kwlist)
        self.words.update(dir(__builtins__))
        self.packages = get_installed_packages()
        self.aliases = {}  # alias -> module name or object path

    def update_aliases(self, text):
        # import ... as ...
        for match in re.finditer(r'^\s*import\s+([a-zA-Z0-9_]+)\s+as\s+([a-zA-Z0-9_]+)', text, re.MULTILINE):
            module, alias = match.groups()
            self.aliases[alias] = module
        # from ... import ... as ...
        for match in re.finditer(r'^\s*from\s+([a-zA-Z0-9_\.]+)\s+import\s+([a-zA-Z0-9_]+)\s+as\s+([a-zA-Z0-9_]+)', text, re.MULTILINE):
            module, obj, alias = match.groups()
            self.aliases[alias] = f"{module}.{obj}"
        # from ... import ...
        for match in re.finditer(r'^\s*from\s+([a-zA-Z0-9_\.]+)\s+import\s+([a-zA-Z0-9_]+)', text, re.MULTILINE):
            module, obj = match.groups()
            self.aliases[obj] = f"{module}.{obj}"

    def get_completions(self, document, complete_event):
        self.update_aliases(document.text)
        text_before = document.text_before_cursor.lstrip()
        word = document.get_word_before_cursor(WORD=True)
        # Chained attribute completion: e.g. Fore., ca., colorama.Fore.
        m = re.search(r'([a-zA-Z_][a-zA-Z0-9_\.]*)\.$', text_before)
        if m:
            obj_path = m.group(1)
            # Try alias first
            if obj_path in self.aliases:
                attrs, obj = get_object_attributes(self.aliases[obj_path])
            else:
                attrs, obj = get_object_attributes(obj_path)
            for attr in sorted(attrs, key=lambda x: x.lower()):
                doc = ''
                if obj:
                    try:
                        doc = getattr(obj, attr).__doc__ or ''
                        doc = doc.strip().split('\n')[0]
                    except Exception:
                        doc = ''
                display = f"{attr} - {doc}" if doc else attr
                yield Completion(attr, start_position=0, display=display)
            return
        # Import/from completion
        if text_before.startswith('import ') or text_before.startswith('from '):
            import_prefix = text_before.split()[-1] if len(text_before.split()) > 1 else ''
            matches = [p for p in self.packages if p.lower().startswith(import_prefix.lower())]
            for m in sorted(matches, key=lambda x: x.lower()):
                yield Completion(m, start_position=-len(word))
            return
        # Python keywords and built-ins
        matches = [w for w in self.words if w.lower().startswith(word.lower())]
        if 'print' in matches:
            matches.remove('print')
            matches = ['print'] + sorted(matches, key=lambda x: x.lower())
        else:
            matches = sorted(matches, key=lambda x: x.lower())
        for m in matches:
            yield Completion(m, start_position=-len(word))

buffer = Buffer(completer=PythonAndImportCompleter(), complete_while_typing=True)
buffer.text = text

nansup_message = [None]  # Mutable container to allow modification in closure

def show_nansup_message(msg):
    nansup_message[0] = msg
    get_app().invalidate()
    def clear():
        import time
        time.sleep(2)
        nansup_message[0] = None
        get_app().invalidate()
    threading.Thread(target=clear, daemon=True).start()

def nansup_update():
    try:
        show_nansup_message("Updating from GitHub...")
        with urllib.request.urlopen(GITHUB_RAW_URL) as response:
            new_code = response.read().decode('utf-8')
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(new_code)
        os.rename(filename, target_name)
        show_nansup_message(f"Updated and renamed to {target_name}!")
    except Exception as e:
        show_nansup_message(f"Update failed: {e}")

class StatusBar:
    def __pt_container__(self):
        msg = nansup_message[0] or f"^O Save  ^X Save+Exit  ^C Exit  F2:NANSUP  File: {filename}"
        return Window(content=FormattedTextControl(msg), height=1, style='reverse')

kb = KeyBindings()

@kb.add('c-x')
def _(event):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(buffer.text)
    event.app.exit()

@kb.add('c-o')
def _(event):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(buffer.text)

@kb.add('c-c')
def _(event):
    event.app.exit()

@kb.add('f2')
def _(event):
    threading.Thread(target=nansup_update, daemon=True).start()

root_container = HSplit([
    Window(height=1, content=FormattedTextControl(f"-- {filename} --")),
    Window(BufferControl(buffer=buffer), wrap_lines=True),
    CompletionsMenu(max_height=8, scroll_offset=1),
    StatusBar(),
])

layout = Layout(root_container)

app = Application(layout=layout, key_bindings=kb, full_screen=True)

def main():
    app.run()

if __name__ == '__main__':
    main()
