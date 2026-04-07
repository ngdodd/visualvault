# Alembic Migrations: Database Version Control

## Why Migrations?

Imagine this scenario:

1. You add a `phone` column to your User model
2. Your code works locally (you manually added the column)
3. You deploy to production
4. **CRASH** - production database doesn't have the column

**Migrations solve this** by tracking database schema changes in code:

```
Migration 001: Create users table
Migration 002: Add phone column to users
Migration 003: Add api_keys table
```

Each migration describes what changed. Apply them in order to any database.

---

## What is Alembic?

Alembic is SQLAlchemy's migration tool. It:

- Tracks schema changes in Python files
- Supports upgrade and downgrade
- Auto-generates migrations by comparing models to database
- Handles multiple databases and branching

---

## Project Structure

```
alembic/
├── env.py              # Configuration (connects models to DB)
├── script.py.mako      # Template for new migrations
└── versions/           # Migration files
    ├── 001_create_users.py
    ├── 002_add_api_keys.py
    └── ...

alembic.ini             # Main config file
```

---

## Key Configuration

### alembic.ini

```ini
[alembic]
script_location = alembic
# Database URL is set in env.py from our Settings
```

### env.py

```python
# Import your models' Base
from app.models import Base

# Import settings for database URL
from app.config import get_settings

# Set URL from settings
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database.url_sync)

# Point to your models' metadata
target_metadata = Base.metadata
```

**Important:** Alembic needs to see all your models to detect changes. That's why `app/models/__init__.py` imports everything:

```python
# app/models/__init__.py
from app.models.user import User, APIKey  # Must import all models!
```

---

## Common Commands

### Create a Migration

```bash
# Auto-generate based on model changes
alembic revision --autogenerate -m "Add phone column to users"

# Create empty migration (for manual edits)
alembic revision -m "Add custom index"
```

### Apply Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Apply next migration only
alembic upgrade +1

# Apply specific migration
alembic upgrade abc123
```

### Rollback Migrations

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific migration
alembic downgrade abc123

# Rollback all migrations
alembic downgrade base
```

### View Status

```bash
# Show current revision
alembic current

# Show migration history
alembic history

# Show pending migrations
alembic history --indicate-current
```

---

## Anatomy of a Migration

```python
"""Add phone column to users

Revision ID: abc123
Revises: def456
Create Date: 2024-01-15 10:00:00
"""

from alembic import op
import sqlalchemy as sa

# Identifiers
revision = 'abc123'
down_revision = 'def456'  # Previous migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the migration."""
    op.add_column('users', sa.Column('phone', sa.String(20), nullable=True))


def downgrade() -> None:
    """Reverse the migration."""
    op.drop_column('users', 'phone')
```

---

## Migration Operations

### Tables

```python
def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False),
        sa.UniqueConstraint('email', name='uq_users_email'),
    )

def downgrade():
    op.drop_table('users')
```

### Columns

```python
def upgrade():
    # Add column
    op.add_column('users', sa.Column('phone', sa.String(20)))

    # Alter column
    op.alter_column('users', 'email', type_=sa.String(500))

    # Rename column
    op.alter_column('users', 'name', new_column_name='full_name')

def downgrade():
    op.alter_column('users', 'full_name', new_column_name='name')
    op.alter_column('users', 'email', type_=sa.String(255))
    op.drop_column('users', 'phone')
```

### Indexes and Constraints

```python
def upgrade():
    # Create index
    op.create_index('ix_users_email', 'users', ['email'])

    # Create unique constraint
    op.create_unique_constraint('uq_users_email', 'users', ['email'])

    # Create foreign key
    op.create_foreign_key(
        'fk_api_keys_user_id',
        'api_keys', 'users',
        ['user_id'], ['id'],
        ondelete='CASCADE'
    )

def downgrade():
    op.drop_constraint('fk_api_keys_user_id', 'api_keys')
    op.drop_constraint('uq_users_email', 'users')
    op.drop_index('ix_users_email', 'users')
```

### Data Migrations

```python
def upgrade():
    # Add column
    op.add_column('users', sa.Column('role', sa.String(20)))

    # Populate with data
    op.execute("UPDATE users SET role = 'user' WHERE role IS NULL")

    # Make non-nullable
    op.alter_column('users', 'role', nullable=False)

def downgrade():
    op.drop_column('users', 'role')
```

---

## Auto-Generate Tips

Alembic can detect these changes automatically:
- ✅ New tables
- ✅ Dropped tables
- ✅ New columns
- ✅ Dropped columns
- ✅ Column type changes
- ✅ Nullable changes
- ✅ New indexes
- ✅ New constraints

Alembic **cannot** detect:
- ❌ Table or column renames (looks like drop + create)
- ❌ Data changes
- ❌ Some constraint changes

**Always review auto-generated migrations before applying!**

---

## Our Initial Migration

```python
# alembic/versions/001_create_users_and_api_keys.py

def upgrade() -> None:
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False, default=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_email", "users", ["email"])

    # Create api_keys table
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("key_prefix", sa.String(12), nullable=False),
        sa.Column("key_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_api_keys_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_api_keys"),
    )


def downgrade() -> None:
    op.drop_table("api_keys")
    op.drop_index("ix_email", "users")
    op.drop_table("users")
```

---

## Running in Docker

```bash
# Run migrations
docker-compose exec api alembic upgrade head

# Create new migration
docker-compose exec api alembic revision --autogenerate -m "Description"

# Check current state
docker-compose exec api alembic current
```

---

## Best Practices

### 1. One Migration Per Change
```bash
# Good: Focused migrations
alembic revision -m "Add phone to users"
alembic revision -m "Add addresses table"

# Bad: Giant migration
alembic revision -m "Add phone, addresses, and refactor everything"
```

### 2. Always Write Downgrades
Even if you never rollback in production, downgrades help in development.

### 3. Test Migrations Locally
```bash
alembic upgrade head    # Apply
alembic downgrade -1    # Rollback
alembic upgrade head    # Apply again
```

### 4. Review Auto-Generated Code
Auto-generate is a starting point, not the final answer.

### 5. Don't Edit Applied Migrations
Once a migration is applied to any database, create a new migration for changes.

### 6. Use Meaningful Messages
```bash
# Good
alembic revision -m "Add email verification token to users"

# Bad
alembic revision -m "Update"
```

### 7. Handle Data Carefully
```python
def upgrade():
    # Add column allowing NULL first
    op.add_column('users', sa.Column('role', sa.String(20), nullable=True))

    # Backfill data
    op.execute("UPDATE users SET role = 'user'")

    # Then make NOT NULL
    op.alter_column('users', 'role', nullable=False)
```

---

## Common Issues

### "Target database is not up to date"
```bash
# Check current state
alembic current

# Apply missing migrations
alembic upgrade head
```

### "Can't locate revision"
A migration was deleted. Either restore it or:
```bash
# Stamp database at a known revision
alembic stamp <revision_id>
```

### Migration Conflicts
Two developers created migrations from the same base:
```bash
# Merge the migrations
alembic merge -m "Merge abc123 and def456"
```

### Auto-Generate Sees No Changes
- Check that models are imported in `app/models/__init__.py`
- Verify `target_metadata` points to your `Base.metadata`

---

## Further Reading

- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Auto-Generating Migrations](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
- [Operation Reference](https://alembic.sqlalchemy.org/en/latest/ops.html)
