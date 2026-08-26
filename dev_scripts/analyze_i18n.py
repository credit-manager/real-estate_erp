import ast
import os

path = r'D:\EOS\DynamicPro-ERP\DynamicPro-ERP\i18n.py'
with open(path, 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

lines = content.split('\n')
print(f'Total lines: {len(lines)}')

# Simple count of translation patterns
ar_count = content.count('\"ar\"')
en_count = content.count('\"en\"')
print(f'Arabic occurrences: {ar_count}')
print(f'English occurrences: {en_count}')

# Check for TRANSLATIONS dict
try:
    tree = ast.parse(content)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == 'TRANSLATIONS':
                    print(f'TRANSLATIONS dict has {len(node.value.keys)} keys')
                    break
except:
    print('Could not parse TRANSLATIONS dict structure')

# Show first few lines
print('\\nFirst 10 lines:')
for i, line in enumerate(lines[:10], 1):
    print(f'{i}: {line[:80]}')