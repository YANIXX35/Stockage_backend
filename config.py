import os

# Email admin — priorité à l'env var, sinon valeur par défaut
ADMIN_EMAIL = os.getenv("FIRST_ADMIN_EMAIL", "kyliyanisse@gmail.com").strip().lower()
ADMIN_QUOTA = 100 * 1024 * 1024 * 1024  # 100 Go
