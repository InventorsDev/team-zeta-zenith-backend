#!/usr/bin/env python3
"""Create a default organization for testing"""

import sys
import os
sys.path.append('.')

from app.database.connection import SessionLocal
from app.database.repositories.organization_repository import OrganizationRepository
from app.database.repositories.user_repository import UserRepository
from app.core.security import get_password_hash

def create_default_organization():
    """Create a default organization and admin user for testing"""
    db = SessionLocal()
    
    try:
        org_repo = OrganizationRepository(db)
        user_repo = UserRepository(db)
        
        # Check if default organization already exists
        existing_org = org_repo.get_by_slug("default-org")
        if existing_org:
            print(f"Default organization already exists: {existing_org.name} (ID: {existing_org.id})")
            return existing_org.id
        
        # Create default organization
        org_data = {
            "name": "Default Organization",
            "slug": "default-org",
            "description": "Default organization for testing and development",
            "email": "admin@default-org.com",
            "plan": "pro",
            "max_users": 50,
            "max_tickets_per_month": 10000,
            "is_active": True,
            "settings": {
                "theme": "light",
                "notifications_enabled": True,
                "auto_assign": True
            }
        }
        
        organization = org_repo.create_organization(org_data)
        print(f"✓ Created default organization: {organization.name} (ID: {organization.id})")
        
        # Create default admin user
        existing_admin = user_repo.get_by_email("admin@default-org.com")
        if not existing_admin:
            hashed_password = get_password_hash("AdminPassword123")
            admin_user = user_repo.create_user(
                email="admin@default-org.com",
                hashed_password=hashed_password,
                full_name="Default Admin",
                organization_id=organization.id,
                role="admin",
                is_verified=True
            )
            print(f"✓ Created default admin user: {admin_user.email} (ID: {admin_user.id})")
            print("  Default admin credentials:")
            print("  Email: admin@default-org.com")
            print("  Password: AdminPassword123")
        else:
            print(f"✓ Default admin user already exists: {existing_admin.email}")
        
        return organization.id
        
    except Exception as e:
        print(f"Error creating default organization: {e}")
        db.rollback()
        return None
    finally:
        db.close()

if __name__ == "__main__":
    print("Creating default organization and admin user...")
    org_id = create_default_organization()
    if org_id:
        print(f"\n✓ Setup completed successfully!")
        print(f"Default organization ID: {org_id}")
        print("\nYou can now:")
        print("1. Start the server: python app/main.py")
        print("2. Login with admin@default-org.com / AdminPassword123")
        print("3. Or register a new user and create your own organization")
    else:
        print("\n✗ Setup failed!")
        sys.exit(1)