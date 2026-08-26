import re, os, glob

template_keys = set()
for f in glob.glob('templates/**/*.html', recursive=True):
    with open(f, 'r', encoding='utf-8') as fh:
        content = fh.read()
    for m in re.findall(r"t\(['\"]([^'\"]+)['\"]\)", content):
        template_keys.add(m)

i18n_keys = set()
with open('i18n.py', 'r', encoding='utf-8') as fh:
    content = fh.read()
for m in re.findall(r'"([^"]+)":\s*"', content):
    i18n_keys.add(m)

missing = sorted(template_keys - i18n_keys)
if missing:
    print(f"MISSING I18N KEYS ({len(missing)}):")
    for k in missing:
        print(f"  - {k}")
else:
    print("All template i18n keys exist in i18n.py")

unused_i18n = sorted(i18n_keys - template_keys)
print(f"\nUNUSED I18N KEYS ({len(unused_i18n)}): (keys in i18n.py but not in templates)")
for k in unused_i18n[:20]:
    print(f"  - {k}")
if len(unused_i18n) > 20:
    print(f"  ... and {len(unused_i18n) - 20} more")
