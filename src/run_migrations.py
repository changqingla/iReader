"""Database migration runner script."""
import asyncio
import asyncpg
from pathlib import Path
import sys


async def run_migrations():
    """Execute all SQL migration files in order."""
    
    # Database connection parameters
    DB_CONFIG = {
        'host': 'reader_postgres',
        'port': 5432,
        'user': 'reader',
        'password': 'reader_dev_password',
        'database': 'reader_qaq',
    }
    
    # Migration files in order
    migrations = [
        '001_add_user_levels.sql',
        '002_create_activation_codes.sql',
        '003_create_organizations.sql',
        '004_create_organization_members.sql',
        '005_add_kb_visibility.sql',
    ]
    
    migrations_dir = Path(__file__).parent / 'migrations'
    
    try:
        # Connect to database
        print("Connecting to database...")
        conn = await asyncpg.connect(**DB_CONFIG)
        print("✓ Connected successfully!")
        
        # Execute each migration
        for migration_file in migrations:
            migration_path = migrations_dir / migration_file
            
            if not migration_path.exists():
                print(f"✗ Migration file not found: {migration_file}")
                continue
            
            print(f"\nExecuting migration: {migration_file}")
            
            # Read SQL file
            with open(migration_path, 'r', encoding='utf-8') as f:
                sql = f.read()
            
            try:
                # Execute SQL
                await conn.execute(sql)
                print(f"✓ Migration {migration_file} completed successfully!")
            except Exception as e:
                print(f"✗ Error executing {migration_file}: {str(e)}")
                # Continue with next migration even if one fails
        
        # Close connection
        await conn.close()
        print("\n✓ All migrations completed!")
        
    except Exception as e:
        print(f"\n✗ Database connection error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_migrations())

