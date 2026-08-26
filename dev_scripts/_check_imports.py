import ast, sys, os

checks = [
    'app.py', 'config.py', 'ai_engine.py', 'i18n.py',
    'db_indexes.py', 'helpers.py', 'models.py',
]

for fname in checks:
    if not os.path.exists(fname):
        continue
    try:
        with open(fname, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source, filename=fname)
    except SyntaxError as e:
        print(f"SYNTAX ERROR in {fname}: {e}")
        continue

    # Collect imported names
    imported = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name
                imported[name] = alias.name
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname or alias.name
                imported[name] = f"{node.module}.{alias.name}"

    # Collect used names
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            # walk up to get root name
            n = node
            while isinstance(n, ast.Attribute):
                n = n.value
            if isinstance(n, ast.Name):
                used.add(n.id)

    unused = {name: mod for name, mod in imported.items() if name not in used}
    if unused:
        print(f"\n{fname} - POTENTIALLY UNUSED IMPORTS:")
        for name, mod in unused.items():
            print(f"  - '{name}' from {mod}")
    else:
        print(f"{fname} - all imports appear used")
