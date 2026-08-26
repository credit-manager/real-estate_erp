import os
import re

# Fix datetime.utcnow -> datetime.now(timezone.utc) in all .py files
# Need to also add 'from datetime import timezone' if not present

files_to_fix = [
    'models/license.py',
    'routes/license.py',
    'utils/workflow.py',
]

for filename in files_to_fix:
    path = os.path.join('D:\\EOS\\DynamicPro-ERP\\DynamicPro-ERP', filename)
    print(f'Fixing {filename}...')
    
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        content = fh.read()
    
    # Check if timezone is already imported
    has_timezone = 'from datetime import' in content and 'timezone' in content
    has_import_timezone = 'import timezone' in content
    
    # Replace datetime.utcnow with datetime.now(timezone.utc)
    new_content = content.replace('datetime.utcnow()', 'datetime.now(timezone.utc)')
    
    # If we replaced anything, also ensure timezone is imported
    if new_content != content:
        # Add timezone import if not present
        if not has_timezone and not has_import_timezone:
            # Find the existing from datetime import line and add timezone
            import_line_pattern = 'from datetime import'
            if import_line_pattern in new_content:
                # Add timezone to the import
                new_content = new_content.replace(
                    'from datetime import',
                    'from datetime import timezone'
                )
            else:
                # Add new import at the top
                # Find a good place - after other imports
                lines = new_content.split('\n')
                # Find first non-empty, non-comment line after imports
                new_lines = []
                imported = False
                for line in lines:
                    if not imported and line.strip().startswith('from ') or line.strip().startswith('import '):
                        imported = True
                        new_lines.append(line)
                    elif not imported and line.strip() and not line.strip().startswith('#'):
                        # First non-import, non-comment line - add import before it
                        new_lines.append('from datetime import timezone')
                        new_lines.append(line)
                        imported = True
                    else:
                        new_lines.append(line)
                new_content = '\n'.join(new_lines)
        
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(new_content)
        print(f'  -> Fixed')
    else:
        print(f'  -> No changes needed')

print('\\nDone fixing datetime.utcnow')