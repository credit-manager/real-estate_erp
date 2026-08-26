import os

files = ['models/license.py', 'routes/license.py', 'utils/workflow.py']
for f in files:
    path = os.path.join('D:\\EOS\\DynamicPro-ERP\\DynamicPro-ERP', f)
    print(f'=== {f} ===')
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            content = fh.read()
        for i, line in enumerate(content.split('\n'), 1):
            if 'utcnow' in line:
                print(f'  line {i}: {line.strip()[:120]}')
    except Exception as e:
        print(f'Error: {e}')
    print()