import sys; sys.path.insert(0, '.')
from app import create_app
from database import db
app = create_app()
with app.app_context():
    from security.rbac import user_permissions, has_permission
    perms = user_permissions(1)
    print('Permissions count:', len(perms))
    print('trials.extend:', 'trials.extend' in perms)
    print('plans.create:', 'plans.create' in perms)
    print('has_permission(1, trials.extend):', has_permission(1, 'trials.extend'))
    print('has_permission(1, plans.create):', has_permission(1, 'plans.create'))
