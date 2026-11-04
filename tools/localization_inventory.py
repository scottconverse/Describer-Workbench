"""Enumerate maintained literal UI text and its actual English fallbacks.

Run from the checkout with: python -m tools.localization_inventory
Dynamic messages, model/user content and interpolated text are not a complete
localization catalogue and are explicitly outside this static inventory.
"""
import ast
import hashlib
import json
from pathlib import Path

from describer.i18n import LANGUAGES,translate


def inventory(root):
    strings={};hashes={}
    for name in ('app.py','desktop.py','model_picker.py'):
        path=root/'describer'/name;text=path.read_text(encoding='utf-8-sig');hashes[str(path.relative_to(root))]=hashlib.sha256(text.encode('utf-8')).hexdigest()
        tree=ast.parse(text)
        def add(node):
            if isinstance(node,ast.Constant) and isinstance(node.value,str) and node.value.strip():
                strings.setdefault(node.value,set()).add(f'describer/{name}:{node.lineno}')
        for node in ast.walk(tree):
            if isinstance(node,ast.Call):
                function=node.func.id if isinstance(node.func,ast.Name) else node.func.attr if isinstance(node.func,ast.Attribute) else ''
                index=1 if function in ('button','addTab') else 0
                if function in ('button','QLabel','QPushButton','QCheckBox','QRadioButton','QGroupBox','QAction','QMenu','setText','setWindowTitle','setPlaceholderText','setAccessibleName','setToolTip','addTab','addRow') and len(node.args)>index:add(node.args[index])
                if function=='addItems' and node.args and isinstance(node.args[0],(ast.List,ast.Tuple)):
                    for item in node.args[0].elts:add(item)
            if isinstance(node,ast.For) and isinstance(node.iter,(ast.List,ast.Tuple)):
                for row in node.iter.elts:
                    if isinstance(row,ast.Tuple) and len(row.elts)>1 and isinstance(row.elts[0],ast.Constant) and isinstance(row.elts[0].value,str):
                        # Settings field tuples (key, visible label, constraints).
                        if row.elts[0].value.isidentifier() and row.elts[0].value.islower():add(row.elts[1])
    entries=[]
    for text,locations in sorted(strings.items()):
        entries.append({'text':text,'sources':sorted(locations),
                        'english_fallback_languages':[language for language in LANGUAGES[1:] if translate(text,language)==text]})
    return {'coverage':'Literal control text, form-field labels and static item lists in the maintained desktop modules. Excludes dynamic/interpolated messages, user/model content and unrendered runtime-only text. Not a full-localization claim.',
            'source_hash_format':'UTF-8 text with LF newlines, without BOM; independent of Git checkout line-ending conversion.',
            'source_sha256':hashes,'language_fallback_counts':{language:sum(language in row['english_fallback_languages'] for row in entries) for language in LANGUAGES[1:]},'entries':entries}


if __name__=='__main__':
    root=Path(__file__).resolve().parents[1];data=inventory(root)
    target=root/'docs'/'LOCALIZATION-GAPS.json';target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'literal_texts':len(data['entries']),'fallback_counts':data['language_fallback_counts']}))
